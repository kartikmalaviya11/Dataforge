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

def test_rca_condition_sql_advanced():
    # Empty IN list returns 1=0
    cond_empty_in = RCACondition("status", "IN", [])
    assert cond_empty_in.to_sql("orders") == "1=0"

    # IN list with values
    cond_in = RCACondition("region", "IN", ["North", "South"])
    assert cond_in.to_sql("customers") == '"customers"."region" IN (\'North\', \'South\')'

    # Single quote escaping
    cond_quote = RCACondition("customer_name", "EQUALS", "O'Reilly")
    assert cond_quote.to_sql("customers") == '"customers"."customer_name" = \'O\'\'Reilly\''

    # Boolean values
    cond_bool = RCACondition("is_active", "EQUALS", True)
    assert cond_bool.to_sql("users") == '"users"."is_active" = TRUE'

    # IS_NULL and IS_NOT_NULL
    cond_null = RCACondition("email", "IS_NULL", None)
    assert cond_null.to_sql("users") == '"users"."email" IS NULL'

    cond_not_null = RCACondition("email", "IS_NOT_NULL", None)
    assert cond_not_null.to_sql("users") == '"users"."email" IS NOT NULL'

def test_multi_condition_chaining_and_or(rca_engine):
    # Test AND chaining
    config_and = RCAAnalysisDefinition(
        analysis_id="test_and", problem_definition="Test AND",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[
            RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2),
            RCACondition("revenue", "GREATER_THAN", 100.0, logical_operator="AND")
        ],
        baseline_type="BASELINE_ALL",
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results_and = rca_engine.execute(config_and)
    assert len(results_and) > 0
    north = next(r for r in results_and if r.dimension_value == "North")
    # In North, review_score <= 2: order 1 (rev=100), order 2 (rev=200). With rev > 100, only order 2 matches
    assert north.affected_sample_size == 1
    assert north.affected_metric_value == 200.0

def test_rca_get_reachable_tables(rca_engine, workspace):
    # orders is connected to customers
    reachable = rca_engine.get_reachable_tables("orders")
    assert "orders" in reachable
    assert "customers" in reachable

    # Add a disconnected table to registry
    df_isolated = pd.DataFrame({"iso_id": [1, 2]})
    df_isolated.to_csv(os.path.join(workspace.project_root, "isolated.csv"), index=False)
    workspace.registry["isolated"] = TableRegistryEntry(
        table_name="isolated", file_name="isolated.csv", file_path=os.path.join(workspace.project_root, "isolated.csv"),
        file_type="csv", row_count=2, column_count=1, status=TableStatus.DISCOVERED, last_modified=time.time()
    )
    # isolated should not be reachable from orders
    reachable_from_orders = rca_engine.get_reachable_tables("orders")
    assert "isolated" not in reachable_from_orders

    # from isolated, only isolated is reachable
    reachable_from_isolated = rca_engine.get_reachable_tables("isolated")
    assert reachable_from_isolated == ["isolated"]

def test_run_analysis_alias_and_save_result(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_alias", problem_definition="Test Alias",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "EQUALS", 1)],
        baseline_type="BASELINE_ALL",
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    results = rca_engine.run_analysis(config)
    assert len(results) > 0

    rca_engine.save_result(results, analysis_id=config.analysis_id)
    saved = rca_engine.load_results()
    assert len(saved) >= 1
    match = next(s for s in saved if s["analysis_id"] == config.analysis_id)
    assert len(match["results"]) == len(results)

def test_rca_save_analysis_idempotence(rca_engine):
    config = RCAAnalysisDefinition(
        analysis_id="test_idemp", problem_definition="Test Idempotence",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "EQUALS", 1)],
        baseline_type="BASELINE_ALL",
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    rca_engine.save_analysis(config)
    assert len([a for a in rca_engine.load_analyses() if a.analysis_id == "test_idemp"]) == 1

    # Save again with same ID (e.g. repeated runs)
    rca_engine.save_analysis(config)
    assert len([a for a in rca_engine.load_analyses() if a.analysis_id == "test_idemp"]) == 1

def test_source_data_immutability(rca_engine, workspace):
    import hashlib
    def hash_file(path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    orders_path = os.path.join(workspace.project_root, "orders.csv")
    customers_path = os.path.join(workspace.project_root, "customers.csv")
    h_orders_before = hash_file(orders_path)
    h_customers_before = hash_file(customers_path)

    config = RCAAnalysisDefinition(
        analysis_id="test_immut", problem_definition="Test Immutability",
        source_table="orders", target_metric_kpi_id="kpi_rev",
        affected_conditions=[RCACondition("review_score", "LESS_THAN_OR_EQUAL", 2)],
        baseline_type="BASELINE_COMPLEMENT",
        dimension_table="customers", dimension_column="region",
        minimum_affected_sample_size=1, minimum_baseline_sample_size=1, created_at=time.time()
    )
    rca_engine.execute(config)

    assert hash_file(orders_path) == h_orders_before
    assert hash_file(customers_path) == h_customers_before

def test_rca_ui_condition_parser_helper():
    from ui.pages.analysis import parse_rca_condition_value
    df = pd.DataFrame({
        "int_col": [10, 20, 30],
        "float_col": [1.5, 2.5, 3.5],
        "str_col": ["alpha", "beta", "gamma"],
        "bool_col": [True, False, True]
    })

    # Unary operators
    val, err = parse_rca_condition_value(df, "int_col", "IS_NULL", None)
    assert val is None and err is None

    val, err = parse_rca_condition_value(df, "int_col", "IS_NOT_NULL", "")
    assert val is None and err is None

    # Empty value error
    val, err = parse_rca_condition_value(df, "int_col", "EQUALS", "")
    assert val is None and "cannot be empty" in err

    val, err = parse_rca_condition_value(df, "int_col", "EQUALS", None)
    assert val is None and "cannot be empty" in err

    # Integer parsing
    val, err = parse_rca_condition_value(df, "int_col", "EQUALS", "25")
    assert val == 25 and err is None

    val, err = parse_rca_condition_value(df, "int_col", "EQUALS", "not_a_number")
    assert val is None and "must be an integer" in err

    # Float parsing
    val, err = parse_rca_condition_value(df, "float_col", "GREATER_THAN", "3.14")
    assert val == 3.14 and err is None

    val, err = parse_rca_condition_value(df, "float_col", "GREATER_THAN", "xyz")
    assert val is None and "must be a number" in err

    # Boolean parsing
    val, err = parse_rca_condition_value(df, "bool_col", "EQUALS", "True")
    assert val is True and err is None

    val, err = parse_rca_condition_value(df, "bool_col", "EQUALS", "0")
    assert val is False and err is None

    val, err = parse_rca_condition_value(df, "bool_col", "EQUALS", "maybe")
    assert val is None and "must be True or False" in err

    # String parsing
    val, err = parse_rca_condition_value(df, "str_col", "EQUALS", "  delta  ")
    assert val == "delta" and err is None

    # IN operator parsing
    val, err = parse_rca_condition_value(df, "int_col", "IN", "10, 20, 30")
    assert val == [10, 20, 30] and err is None

    val, err = parse_rca_condition_value(df, "int_col", "IN", "10, abc, 30")
    assert val is None and "must be integers" in err

    val, err = parse_rca_condition_value(df, "str_col", "IN", "alpha, beta")
    assert val == ["alpha", "beta"] and err is None

    val, err = parse_rca_condition_value(df, "str_col", "IN", " , , ")
    assert val is None and "requires at least one comma-separated value" in err

    val, err = parse_rca_condition_value(df, "str_col", "IN", "   ")
    assert val is None and "cannot be empty" in err

def test_render_rca_empty_workspace_and_no_kpis(workspace):
    from unittest.mock import patch
    from ui.pages.analysis import render_rca
    import streamlit as st

    # Empty workspace test
    empty_ws = ProjectWorkspace(os.path.join(workspace.project_root, "empty_ws"))
    with patch("streamlit.markdown") as mock_md, patch("ui.components.empty_state") as mock_empty:
        render_rca(empty_ws)
        mock_empty.assert_called_once()
        assert "No tables available" in mock_empty.call_args[0][0]

    # Workspace with tables but no KPIs test
    with patch("streamlit.markdown") as mock_md, patch("ui.components.empty_state") as mock_empty:
        if "kpis" in st.session_state:
            del st.session_state["kpis"]
        render_rca(workspace)
        mock_empty.assert_called_once()
        assert "No KPIs available" in mock_empty.call_args[0][0]
