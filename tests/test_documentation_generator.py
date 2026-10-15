
import os
import shutil
import pytest
from src.documentation_generator import DocumentationGenerator

@pytest.fixture
def generator():
    test_dir = ".dataforge_test/docs"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield DocumentationGenerator(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_each_document(generator):
    meta = {
        "columns": [{"name": "id", "type": "int", "description": "ID"}],
        "quality_score": 99,
        "cleaning_logs": ["Cleaned nulls"],
        "relationships": [{"from": "A", "to": "B"}],
        "kpis": {"sales": "Sum of sales"},
        "sql_queries": ["SELECT * FROM A"],
        "findings": ["Sales increased"],
        "summary": "Great project"
    }
    docs = generator.generate_all(meta)
    assert "data_dictionary.md" in docs
    assert "**id** (int): ID" in docs["data_dictionary.md"]
    assert "Score: 99" in docs["data_quality_report.md"]

def test_deterministic_content(generator):
    meta = {
        "columns": [
            {"name": "b", "type": "int"},
            {"name": "a", "type": "int"}
        ]
    }
    doc = generator.generate_data_dictionary(meta)
    assert doc.index("**a**") < doc.index("**b**")

def test_missing_metadata(generator):
    docs = generator.generate_all({})
    assert "No columns metadata provided." in docs["data_dictionary.md"]

def test_persistence(generator):
    generator.generate_all({"summary": "test persist"})
    assert os.path.exists(os.path.join(generator.persistence_dir, "project_summary.md"))

def test_compile_project_metadata_empty(tmp_path, generator):
    from src.workspace import ProjectWorkspace
    ws = ProjectWorkspace(str(tmp_path))
    meta = DocumentationGenerator.compile_project_metadata(ws)
    assert meta["columns"] == []
    assert meta["quality_score"] == 0
    assert meta["cleaning_logs"] == []
    assert meta["relationships"] == []
    assert meta["kpis"] == {}
    assert meta["findings"] == []
    assert "0 registered tables" in meta["summary"]

    docs = generator.generate_all(meta)
    assert "No columns metadata provided." in docs["data_dictionary.md"]
    assert "Score: 0" in docs["data_quality_report.md"]

def test_compile_project_metadata_real_data(tmp_path, generator):
    import json
    import pandas as pd
    from src.workspace import ProjectWorkspace
    from src.run_history import RunHistoryManager
    from src.finding_engine import FindingEngine, FindingDefinition
    from src.kpi_engine import KPIManager, KPIDefinition

    ws = ProjectWorkspace(str(tmp_path))
    # Write a real table
    df = pd.DataFrame({"order_id": [1, 2], "amount": [10.5, 20.0]})
    csv_path = os.path.join(str(tmp_path), "orders.csv")
    df.to_csv(csv_path, index=False)
    ws.discover_datasets()

    # Record a run in RunHistory
    rhm = RunHistoryManager(str(tmp_path))
    run_id = rhm.create_run()
    rhm.update_run(run_id, {"cleaning_summary": {"operation": "Impute Nulls", "affected_rows": 2}})
    rhm.complete_run(run_id)

    # Save a finding
    fe = FindingEngine(ws)
    fe.save_finding(FindingDefinition(
        finding_id="f1",
        problem="High Outlier",
        evidence_statement="Amount has spike above 3 stddev",
        created_at=0.0,
        updated_at=0.0
    ))

    # Save a KPI
    km = KPIManager(ws)
    km.save_kpi(KPIDefinition(
        kpi_id="k1",
        kpi_name="Total Amount",
        business_definition="Sum of amount",
        formula="SUM(amount)",
        metric_definitions=[],
        source_tables=["orders"],
        source_columns=["amount"],
        unit="USD",
        description="Total revenue"
    ))

    # Save a relationship
    os.makedirs(os.path.join(str(tmp_path), ".dataforge"), exist_ok=True)
    with open(os.path.join(str(tmp_path), ".dataforge", "relationships.json"), "w", encoding="utf-8") as f:
        json.dump([{"source_table": "orders", "source_column": "customer_id", "target_table": "customers", "target_column": "id", "status": "ACCEPTED"}], f)

    table_results = {
        "orders": {
            "df": df,
            "quality_score": 92.5,
            "types": {
                "order_id": "Integer ID",
                "amount": "Decimal Currency"
            }
        }
    }

    meta = DocumentationGenerator.compile_project_metadata(ws, table_results=table_results)
    assert len(meta["columns"]) == 2
    assert meta["quality_score"] == 92.5
    assert len(meta["cleaning_logs"]) >= 1
    assert "Impute Nulls" in meta["cleaning_logs"][0]
    assert len(meta["relationships"]) == 1
    assert meta["relationships"][0] == {"from": "orders.customer_id", "to": "customers.id"}
    assert "Total Amount" in meta["kpis"]
    assert len(meta["findings"]) == 1
    assert "High Outlier" in meta["findings"][0]

    docs = generator.generate_all(meta)
    assert "orders.amount" in docs["data_dictionary.md"]
    assert "Score: 92.5" in docs["data_quality_report.md"]
    assert "Impute Nulls" in docs["cleaning_log.md"]
    assert "orders.customer_id -> customers.id" in docs["relationship_report.md"]
    assert "Total Amount" in docs["kpi_dictionary.md"]
    assert "High Outlier" in docs["findings_report.md"]
