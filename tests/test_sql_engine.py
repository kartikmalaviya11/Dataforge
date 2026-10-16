import pytest
import duckdb
import pandas as pd
from pathlib import Path
import json
import uuid
import time
from src.workspace import ProjectWorkspace, TableRegistryEntry, TableStatus
from src.sql_engine import DuckDBEngine, SecurityError

@pytest.fixture
def workspace_with_data(tmp_path):
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create a small CSV
    csv_path = project_root / "test.csv"
    pd.DataFrame({"id": [1, 2, 3], "value": ["a", "b", "c"]}).to_csv(csv_path, index=False)
    
    # Create a small XLSX
    xlsx_path = project_root / "test_excel.xlsx"
    pd.DataFrame({"id": [4, 5], "name": ["foo", "bar"]}).to_excel(xlsx_path, index=False)
    
    # Initialize workspace
    ws = ProjectWorkspace(project_root)
    ws.discover_datasets()
    ws.save()
    return ws

def test_duckdb_initialization(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    assert engine.conn is not None
    # Check if tables are registered
    tables = engine.conn.execute("SHOW TABLES").df()
    table_names = tables["name"].tolist()
    assert "test" in table_names
    assert "test_excel" in table_names
    engine.close()

def test_csv_table_registration(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    # the view should be queryable
    res = engine.execute_query('SELECT * FROM "test" ORDER BY id')
    assert len(res) == 3
    assert res.iloc[0]["value"] == "a"
    engine.close()

def test_xlsx_handling(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    # The xlsx file should have been converted to parquet and queried
    res = engine.execute_query('SELECT * FROM "test_excel" ORDER BY id')
    assert len(res) == 2
    assert res.iloc[0]["name"] == "foo"
    
    # Check that parquet cache exists
    cache_dir = workspace_with_data.project_root / ".dataforge" / "cache"
    assert cache_dir.exists()
    parquet_files = list(cache_dir.glob("*.parquet"))
    assert len(parquet_files) > 0
    engine.close()

def test_multi_table_join(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    sql = '''
    SELECT d.id, d.value, e.name 
    FROM "test" d
    LEFT JOIN "test_excel" e ON d.id = e.id
    '''
    res = engine.execute_query(sql)
    assert len(res) == 3
    engine.close()

def test_temporary_view_and_table(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    engine.execute_query('CREATE TEMP VIEW "my_view" AS SELECT * FROM "test"')
    res = engine.execute_query('SELECT * FROM "my_view"')
    assert len(res) == 3
    
    engine.execute_query('CREATE TEMP TABLE "my_table" AS SELECT * FROM "test_excel"')
    res2 = engine.execute_query('SELECT * FROM "my_table"')
    assert len(res2) == 2
    engine.close()

def test_sql_safety_blocked_operations(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    
    blocked_queries = [
        "INSERT INTO test VALUES (4, 'd')",
        "UPDATE test SET value = 'z' WHERE id = 1",
        "DELETE FROM test WHERE id = 1",
        "DROP VIEW test",
        "DROP TABLE test",
        "ALTER TABLE test ADD COLUMN new_col INT",
        "TRUNCATE TABLE test",
        "ATTACH 'db.sqlite'",
        "COPY test FROM 'other.csv'",
        "COPY (SELECT * FROM test) TO 'out.csv'",
        "   UPDATE test SET value = 'z' ",
        "/* tricky */ DELETE FROM test;"
    ]
    
    for q in blocked_queries:
        with pytest.raises(SecurityError):
            engine.execute_query(q)
            
    engine.close()
    
def test_sql_safety_multiple_statements(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    with pytest.raises(SecurityError, match="Multiple statements"):
        engine.execute_query("SELECT * FROM test; SELECT * FROM test_excel")
    engine.close()

def test_invalid_sql(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    with pytest.raises(Exception):
        engine.execute_query("SELEC * FROM test")
    engine.close()
    
def test_result_preview_limit(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    # We enforce a limit, say 500
    engine.preview_limit = 2
    res = engine.execute_query("SELECT * FROM test")
    assert len(res) == 2
    
    # User limit smaller than our limit
    res2 = engine.execute_query("SELECT * FROM test LIMIT 1")
    assert len(res2) == 1
    engine.close()

def test_large_export(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    out_path = engine.export_query("SELECT * FROM test ORDER BY id")
    assert Path(out_path).exists()
    assert Path(out_path).parent.name == "exports"
    
    # Read the exported file
    df = pd.read_csv(out_path)
    assert len(df) == 3
    engine.close()
    
def test_1m_row_synthetic(tmp_path):
    project_root = tmp_path / "1m_project"
    project_root.mkdir()
    
    # Create 1M row CSV manually (to avoid pandas overhead during creation if possible, but we'll use pandas for brevity in test setup)
    # Actually, 1M rows might be a bit slow for test, maybe 100k for unit tests, but we'll test 1M to satisfy criteria if needed. Let's do 100k here to not bog down test suite too much, or use duckdb to generate it.
    csv_path = project_root / "large.csv"
    duckdb.execute(f"COPY (SELECT range AS id, 'val' || range AS value FROM range(1000000)) TO '{csv_path}' (HEADER, DELIMITER ',')")
    
    # Hash before
    import hashlib
    def get_hash(path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    hash_before = get_hash(csv_path)
    
    ws = ProjectWorkspace(project_root)
    ws.discover_datasets()
    ws.save()
    
    engine = DuckDBEngine(ws)
    start_time = time.time()
    res = engine.execute_query('SELECT COUNT(*) as c FROM "large"')
    duration = time.time() - start_time
    
    assert res.iloc[0]["c"] == 1000000
    
    # Preview limit check
    engine.preview_limit = 500
    res_preview = engine.execute_query('SELECT * FROM "large"')
    assert len(res_preview) == 500
    
    hash_after = get_hash(csv_path)
    assert hash_before == hash_after
    engine.close()

def test_ground_truth_aggregation(workspace_with_data):
    engine = DuckDBEngine(workspace_with_data)
    res = engine.execute_query("SELECT SUM(id) as s, COUNT(*) as c FROM test")
    assert res.iloc[0]["s"] == 6
    assert res.iloc[0]["c"] == 3
    engine.close()

def test_xlsx_null_handling_and_cache_invalidation(tmp_path):
    project_root = tmp_path / "test_xlsx_proj"
    project_root.mkdir()

    # Create Excel file with missing values in object/string column
    excel_path = project_root / "customers.xlsx"
    df = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "notes": ["Active", None, "Pending", float("nan")]
    })
    df.to_excel(excel_path, index=False)

    ws = ProjectWorkspace(project_root)
    ws.discover_datasets()
    ws.save()

    engine = DuckDBEngine(ws)
    # Query with IS NULL - should find rows 2 and 4 (2 rows)
    res_null = engine.execute_query('SELECT * FROM "customers" WHERE notes IS NULL ORDER BY id')
    assert len(res_null) == 2
    assert list(res_null["id"]) == [2, 4]

    # Query with IS NOT NULL - should find rows 1 and 3 (2 rows)
    res_not_null = engine.execute_query('SELECT * FROM "customers" WHERE notes IS NOT NULL ORDER BY id')
    assert len(res_not_null) == 2
    assert list(res_not_null["notes"]) == ["Active", "Pending"]
    engine.close()

    # Modify the excel file and verify cache invalidation
    time.sleep(0.05)  # Ensure mtime tick if needed
    df_new = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "notes": ["Active", "Fixed", "Pending", "Recovered", None]
    })
    df_new.to_excel(excel_path, index=False)

    engine2 = DuckDBEngine(ws)
    res_updated = engine2.execute_query('SELECT * FROM "customers" WHERE notes IS NULL')
    assert len(res_updated) == 1
    assert res_updated.iloc[0]["id"] == 5

    res_all = engine2.execute_query('SELECT COUNT(*) as c FROM "customers"')
    assert res_all.iloc[0]["c"] == 5
    engine2.close()
