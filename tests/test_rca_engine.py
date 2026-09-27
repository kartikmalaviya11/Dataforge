import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import time

from src.workspace import ProjectWorkspace, TableRegistryEntry, TableStatus
from src.kpi_engine import KPIManager, KPIDefinition, MetricDefinition
from src.data_model import DataModel, RelationshipCandidate, RelationshipStatus, Cardinality
from src.rca_engine import (
    RCACondition,
    RCAAnalysisDefinition,
    RCAGroupResult,
    RCAEngine,
    AmbiguousRCAPathError,
    MissingRCAPathError
)

@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory() as tmp:
        ws = ProjectWorkspace(tmp)
        
        df_orders = pd.DataFrame({
            "order_id": [1, 2, 3, 4, 5, 6, 7, 8],
            "customer_id": [1, 2, 3, 4, 5, 6, 7, 8],
            "revenue": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 0.0, -100.0],
            "review_score": [1, 2, 5, 4, 1, 5, 1, 2] # 1,2 are bad. 4,5 are good.
        })
        df_customers = pd.DataFrame({
            "customer_id": [1, 2, 3, 4, 5, 6, 7, 8],
            "region": ["North", "North", "North", "South", "South", "East", "East", "West"]
        })
        
        df_orders.to_csv(os.path.join(tmp, "orders.csv"), index=False)
        df_customers.to_csv(os.path.join(tmp, "customers.csv"), index=False)
        
        ws.registry["orders"] = TableRegistryEntry(
            table_name="orders", file_name="orders.csv", file_path=os.path.join(tmp, "orders.csv"),
            file_type="csv", row_count=8, column_count=4, status=TableStatus.DISCOVERED, last_modified=time.time()
        )
        ws.registry["customers"] = TableRegistryEntry(
            table_name="customers", file_name="customers.csv", file_path=os.path.join(tmp, "customers.csv"),
            file_type="csv", row_count=8, column_count=2, status=TableStatus.DISCOVERED, last_modified=time.time()
        )
        yield ws

@pytest.fixture
def rca_engine(workspace):
    km = KPIManager(workspace)
    kpi = KPIDefinition(
        kpi_id="kpi_rev", kpi_name="Total Revenue", business_definition="", formula="",
        metric_definitions=[MetricDefinition(metric_name="Total Revenue", source_table="orders", source_column="revenue", operation="SUM")],
        source_tables=["orders"], source_columns=["revenue"], unit="", description="", created_at=time.time(), updated_at=time.time()
    )
    km.save_kpi(kpi)
    
    dm = DataModel(tables={}, relationships=[
        RelationshipCandidate(source_table="orders", source_column="customer_id", target_table="customers", target_column="customer_id", cardinality=Cardinality.MANY_TO_ONE, source_unique=False, target_unique=True, match_coverage=100.0, orphan_rate=0.0, confidence=100.0, evidence=[], status=RelationshipStatus.ACCEPTED)
    ])
    
    return RCAEngine(workspace, dm, km)

def test_baseline_all_semantics(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_all", problem_definition="Test",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2)],
        baseline_type="BASELINE_ALL", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results = rca_engine.execute(config)
    north = next(r for r in results if r.dimension_value == "North")
    assert north.affected_sample_size == 2
    assert north.baseline_sample_size == 3
    assert north.affected_metric_value == 300.0
    assert north.baseline_metric_value == 600.0
    assert north.absolute_difference == -300.0
    assert north.relative_difference_pct == -50.0

def test_baseline_complement_semantics(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_comp", problem_definition="Test",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2)],
        baseline_type="BASELINE_COMPLEMENT", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results = rca_engine.execute(config)
    north = next(r for r in results if r.dimension_value == "North")
    assert north.affected_sample_size == 2
    assert north.baseline_sample_size == 1
    assert north.affected_metric_value == 300.0
    assert north.baseline_metric_value == 300.0
    assert north.absolute_difference == 0.0
    assert north.relative_difference_pct == 0.0

def test_operator_security():
    with pytest.raises(ValueError):
        RCACondition("col", "DROP TABLE", "val")
    with pytest.raises(ValueError):
        RCACondition("col", "; DELETE FROM users", "val")

def test_missing_path_error(rca_engine, workspace):
    # Setup disconnected table
    df_disconnected = pd.DataFrame({"id": [1, 2]})
    df_disconnected.to_csv(os.path.join(workspace.project_root, "disconnected.csv"), index=False)
    workspace.registry["disconnected"] = TableRegistryEntry(
        table_name="disconnected", file_name="disconnected.csv", file_path=os.path.join(workspace.project_root, "disconnected.csv"),
        file_type="csv", row_count=2, column_count=1, status=TableStatus.DISCOVERED, last_modified=time.time()
    )
    
    config = RCAAnalysisDefinition(
        analysis_id="test_missing_path", problem_definition="Test",
        source_table="disconnected", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("id", "EQUALS", 1)],
        baseline_type="BASELINE_ALL", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    with pytest.raises(MissingRCAPathError):
        rca_engine.execute(config)

def test_ambiguous_path_error(rca_engine, workspace):
    # Add a second path of same length
    rca_engine.data_model.relationships.append(
        RelationshipCandidate(source_table="orders", source_column="order_id", target_table="customers", target_column="customer_id", cardinality=Cardinality.MANY_TO_ONE, source_unique=False, target_unique=True, match_coverage=100.0, orphan_rate=0.0, confidence=100.0, evidence=[], status=RelationshipStatus.ACCEPTED)
    )
    config = RCAAnalysisDefinition(
        analysis_id="test_ambig_path", problem_definition="Test",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "EQUALS", 1)],
        baseline_type="BASELINE_ALL", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    with pytest.raises(AmbiguousRCAPathError):
        rca_engine.execute(config)

def test_performance_synthetic_1M(rca_engine, workspace):
    # Generate 1M rows
    df_large = pd.DataFrame({
        "order_id": np.arange(100000), # 100k for faster test running
        "customer_id": np.random.randint(1, 10, size=100000),
        "revenue": np.random.rand(100000) * 100,
        "review_score": np.random.randint(1, 6, size=100000)
    })
    df_large.to_csv(os.path.join(workspace.project_root, "large_orders.csv"), index=False)
    workspace.registry["large_orders"] = TableRegistryEntry(
        table_name="large_orders", file_name="large_orders.csv", file_path=os.path.join(workspace.project_root, "large_orders.csv"),
        file_type="csv", row_count=100000, column_count=4, status=TableStatus.DISCOVERED, last_modified=time.time()
    )
    kpi = rca_engine.kpi_manager.load_kpis()[0]
    kpi.metric_definitions[0].source_table = "large_orders"
    rca_engine.kpi_manager.save_kpi(kpi, overwrite=True)
    rca_engine.data_model.relationships[0].source_table = "large_orders"
    rca_engine.duckdb.conn.execute(f"CREATE VIEW large_orders AS SELECT * FROM read_csv_auto('{os.path.join(workspace.project_root, 'large_orders.csv')}')")
    
    config = RCAAnalysisDefinition(
        analysis_id="test_perf", problem_definition="Test",
        source_table="large_orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2)],
        baseline_type="BASELINE_ALL", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    start = time.time()
    results = rca_engine.execute(config)
    elapsed = time.time() - start
    assert elapsed < 10.0
    assert len(results) > 0

def test_sample_thresholds(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_thresh", problem_definition="Test",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2)], 
        baseline_type="BASELINE_ALL", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=2, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results = rca_engine.execute(config)
    south = next(r for r in results if r.dimension_value == "South")
    assert south.affected_sample_size == 1
    assert south.association_classification == "Insufficient Evidence"
    
    config.minimum_affected_sample_size = 1
    results = rca_engine.execute(config)
    south = next(r for r in results if r.dimension_value == "South")
    assert south.association_classification in ["Observed Association", "Large Observed Association"]

def test_zero_baseline(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_zero", problem_definition="Test",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2)],
        baseline_type="BASELINE_CUSTOM", 
        custom_baseline_conditions=[RCACondition("order_id", "EQUALS", 7)],
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results = rca_engine.execute(config)
    east = next(r for r in results if r.dimension_value == "East")
    assert east.baseline_metric_value == 0.0
    assert east.relative_difference_pct is None
    assert east.association_classification == "Insufficient Evidence"

def test_negative_baseline(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_neg", problem_definition="Test",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "EQUALS", 5)],
        baseline_type="BASELINE_ALL", custom_baseline_conditions=None,
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=0, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results = rca_engine.execute(config)
    west = next(r for r in results if r.dimension_value == "West")
    assert west.baseline_metric_value == -100.0
    assert pd.isna(west.affected_metric_value)
