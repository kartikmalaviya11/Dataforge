import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import json

from src.workspace import ProjectWorkspace, TableRegistryEntry, TableStatus
from src.sql_engine import DuckDBEngine
from src.anomaly_engine import AnomalyEngine, OutlierAnalysisDefinition, OutlierAnalysisResult, OutlierRecord

@pytest.fixture
def temp_workspace(tmp_path):
    ws = ProjectWorkspace(tmp_path)
    return ws

@pytest.fixture
def duckdb_engine(temp_workspace):
    return DuckDBEngine(temp_workspace)

@pytest.fixture
def anomaly_engine(temp_workspace, duckdb_engine):
    return AnomalyEngine(temp_workspace, duckdb_engine)

def create_table(ws: ProjectWorkspace, engine: DuckDBEngine, table_name: str, data: list, column_name: str = "val"):
    df = pd.DataFrame({column_name: data})
    file_path = ws.project_root / f"{table_name}.csv"
    df.to_csv(file_path, index=False)
    
    ws.registry[table_name] = TableRegistryEntry(
        table_name=table_name,
        file_name=f"{table_name}.csv",
        file_path=str(file_path),
        file_type="csv",
        row_count=len(df),
        column_count=1,
        status=TableStatus.LOADED.value,
        last_modified=file_path.stat().st_mtime
    )
    safe_path = str(file_path).replace("'", "''")
    engine.conn.execute(f"CREATE OR REPLACE VIEW \"{table_name}\" AS SELECT * FROM read_csv_auto('{safe_path}', header=True)")

def test_iqr_basic(temp_workspace, duckdb_engine, anomaly_engine):
    # n=5, median=3, Q1=2, Q3=4. IQR = 2
    # threshold = 1.5. Bounds: 2 - 3 = -1, 4 + 3 = 7
    data = [1, 2, 3, 4, 5, 10, -5] 
    create_table(temp_workspace, duckdb_engine, "test_iqr", data)
    
    # test pandas
    df = pd.DataFrame({"val": data})
    result_pd = anomaly_engine._detect_iqr_pandas(df, "val", 1.5)
    
    # test duckdb
    result_ddb = anomaly_engine._detect_iqr_duckdb("test_iqr", "val", 1.5)
    
    # compare
    assert result_pd.lower_bound == result_ddb.lower_bound
    assert result_pd.upper_bound == result_ddb.upper_bound
    assert len(result_pd.outliers) == len(result_ddb.outliers)
    assert set(o.value for o in result_pd.outliers) == set(o.value for o in result_ddb.outliers)
    assert set(o.value for o in result_pd.outliers) == {10, -5}

def test_zscore_basic(temp_workspace, duckdb_engine, anomaly_engine):
    data = [10, 10, 10, 10, 10, 100]
    create_table(temp_workspace, duckdb_engine, "test_zscore", data)
    
    result_pd = anomaly_engine._detect_zscore_pandas(pd.DataFrame({"val": data}), "val", 2.0)
    result_ddb = anomaly_engine._detect_zscore_duckdb("test_zscore", "val", 2.0)
    
    assert np.isclose(result_pd.lower_bound, result_ddb.lower_bound)
    assert np.isclose(result_pd.upper_bound, result_ddb.upper_bound)
    assert set(o.value for o in result_pd.outliers) == {100}
    assert set(o.value for o in result_ddb.outliers) == {100}

def test_n0_n1_n2(temp_workspace, duckdb_engine, anomaly_engine):
    # n=0
    create_table(temp_workspace, duckdb_engine, "test_n0", [])
    r_iqr_0 = anomaly_engine._detect_iqr_duckdb("test_n0", "val", 1.5)
    r_z_0 = anomaly_engine._detect_zscore_duckdb("test_n0", "val", 3.0)
    assert len(r_iqr_0.outliers) == 0
    assert len(r_z_0.outliers) == 0
    
    # n=1
    create_table(temp_workspace, duckdb_engine, "test_n1", [5])
    r_iqr_1 = anomaly_engine._detect_iqr_duckdb("test_n1", "val", 1.5)
    r_z_1 = anomaly_engine._detect_zscore_duckdb("test_n1", "val", 3.0)
    assert len(r_iqr_1.outliers) == 0
    assert len(r_z_1.outliers) == 0
    
    # n=2
    create_table(temp_workspace, duckdb_engine, "test_n2", [5, 100])
    r_iqr_2 = anomaly_engine._detect_iqr_duckdb("test_n2", "val", 1.5)
    r_z_2 = anomaly_engine._detect_zscore_duckdb("test_n2", "val", 3.0)
    # With n=2, ddof=1 stddev is valid, zscore might flag or not based on threshold.
    # We just ensure it runs without crashing.

def test_constant_values(temp_workspace, duckdb_engine, anomaly_engine):
    create_table(temp_workspace, duckdb_engine, "test_const", [5, 5, 5, 5])
    r_iqr = anomaly_engine._detect_iqr_duckdb("test_const", "val", 1.5)
    r_z = anomaly_engine._detect_zscore_duckdb("test_const", "val", 3.0)
    assert len(r_iqr.outliers) == 0
    assert len(r_z.outliers) == 0

def test_nulls(temp_workspace, duckdb_engine, anomaly_engine):
    data = [1, 2, 3, None, 100, None]
    create_table(temp_workspace, duckdb_engine, "test_nulls", data)
    r_iqr_ddb = anomaly_engine._detect_iqr_duckdb("test_nulls", "val", 1.5)
    r_iqr_pd = anomaly_engine._detect_iqr_pandas(pd.DataFrame({"val": data}), "val", 1.5)
    assert set(o.value for o in r_iqr_ddb.outliers) == {100}
    assert set(o.value for o in r_iqr_pd.outliers) == {100}

def test_decimals_and_negatives(temp_workspace, duckdb_engine, anomaly_engine):
    data = [-1.5, -2.5, -3.5, -100.5, 50.5]
    create_table(temp_workspace, duckdb_engine, "test_dec", data)
    r_z_ddb = anomaly_engine._detect_zscore_duckdb("test_dec", "val", 1.5)
    assert len(r_z_ddb.outliers) > 0

def test_public_analyze_method(temp_workspace, duckdb_engine, anomaly_engine):
    data = [1, 2, 3, 4, 100]
    create_table(temp_workspace, duckdb_engine, "test_pub", data)
    
    defi = OutlierAnalysisDefinition(
        table_name="test_pub",
        column_name="val",
        method="IQR",
        threshold=1.5
    )
    
    # using duckdb
    res1 = anomaly_engine.analyze(defi, use_duckdb=True)
    assert len(res1.outliers) == 1
    
    # using pandas
    res2 = anomaly_engine.analyze(defi, use_duckdb=False)
    assert len(res2.outliers) == 1
    
    # verify persistence
    analyses_file = temp_workspace.project_root / ".dataforge" / "outlier_analyses.json"
    assert analyses_file.exists()
    
    with open(analyses_file, "r") as f:
        saved = json.load(f)
    
    assert len(saved) == 2
    assert saved[0]["definition"]["method"] == "IQR"
