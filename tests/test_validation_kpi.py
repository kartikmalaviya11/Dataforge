import os
import json
import pytest
import pandas as pd
import numpy as np
from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine
from src.kpi_engine import (
    MetricDefinition, KPIDefinition, PandasValidator, SQLValidator,
    CrossValidator, FilterDefinition, KPIManager, KPISemanticChecker
)

@pytest.fixture
def workspace(tmp_path):
    ws = ProjectWorkspace(str(tmp_path))
    
    # Create a test dataset
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7, 8],
        "category": ["A", "B", "A", "B", "A", "C", None, "A"],
        "revenue": [100.0, 200.5, None, 0.0, 300.0, 150.0, None, 100.0],
        "qty": [1, 2, 0, 1, 3, 1, None, 1],
        "small_float": [1e-6, 2e-6, 0, 1e-7, None, 0, 0, 0],
        "large_float": [1e6, 1e6 + 0.01, 1e6, 1e6, 1e6, 1e6, 1e6, 1e6]
    })
    
    csv_path = os.path.join(str(tmp_path), "sales.csv")
    df.to_csv(csv_path, index=False)
    
    ws.discover_datasets()
    return ws

@pytest.fixture
def engine(workspace):
    eng = DuckDBEngine(workspace)
    return eng

@pytest.fixture
def kpi_manager(workspace):
    return KPIManager(workspace)

def test_sql_pandas_match_aggregations(engine):
    sql_val = SQLValidator(engine)
    pd_val = PandasValidator(engine)
    cross = CrossValidator(sql_val, pd_val)
    
    metrics = ["COUNT", "SUM", "AVG", "MIN", "MAX"]
    for m in metrics:
        metric = MetricDefinition(
            metric_name=f"test_{m}",
            operation=m,
            source_table="sales",
            source_column="revenue",
            filters=None
        )
        res = cross.validate(metric)
        assert res["status"] == "MATCH", f"{m} failed to match: {res}"

def test_count_distinct_semantics(engine):
    sql_val = SQLValidator(engine)
    pd_val = PandasValidator(engine)
    cross = CrossValidator(sql_val, pd_val)
    
    # COUNT DISTINCT on category (A, B, C, None) -> expected 3
    metric = MetricDefinition(
        metric_name="dist_cat",
        operation="COUNT_DISTINCT",
        source_table="sales",
        source_column="category",
        filters=None
    )
    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == 3
    
    # COUNT DISTINCT on revenue (100, 200.5, 0, 300, 150, None) -> 5
    metric.source_column = "revenue"
    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == 5

def test_cross_validation_nulls_and_zeros(engine):
    sql_val = SQLValidator(engine)
    pd_val = PandasValidator(engine)
    cross = CrossValidator(sql_val, pd_val)
    
    # Filter to only NULL rows
    metric = MetricDefinition(
        metric_name="null_only_sum",
        operation="SUM",
        source_table="sales",
        source_column="revenue",
        filters=[FilterDefinition(column="id", operator="==", value=7)]
    )
    
    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == "MISSING"
    assert res["pandas_result"] == "MISSING"
    
    metric.operation = "COUNT"
    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == 0
    
    # Zero values
    metric.filters = [FilterDefinition(column="id", operator="==", value=4)] # revenue = 0
    metric.operation = "SUM"
    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == 0

def test_cross_validation_float_tolerance(engine):
    sql_val = SQLValidator(engine)
    pd_val = PandasValidator(engine)
    cross = CrossValidator(sql_val, pd_val)
    
    metric = MetricDefinition(
        metric_name="large_float",
        operation="AVG",
        source_table="sales",
        source_column="large_float",
        filters=None
    )
    res = cross.validate(metric)
    assert res["status"] == "MATCH"

def test_validation_filtered(engine):
    sql_val = SQLValidator(engine)
    pd_val = PandasValidator(engine)
    cross = CrossValidator(sql_val, pd_val)
    
    metric = MetricDefinition(
        metric_name="filtered_sum",
        operation="SUM",
        source_table="sales",
        source_column="revenue",
        filters=[
            FilterDefinition(column="category", operator="==", value="A"),
            FilterDefinition(column="qty", operator=">=", value=1)
        ]
    )
    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == 500.0
    
def test_filter_semantics(engine):
    sql_val = SQLValidator(engine)
    pd_val = PandasValidator(engine)
    cross = CrossValidator(sql_val, pd_val)
    
    # Invalid operator
    with pytest.raises(ValueError):
        FilterDefinition(column="category", operator="INVALID", value="A")
        
    # Col == NULL is blocked
    with pytest.raises(ValueError):
        FilterDefinition(column="category", operator="==", value=None)
        
    # Incompatible type comparison - SQL engine will fail typecast, we catch it
    metric = MetricDefinition(
        metric_name="bad_filter",
        operation="SUM",
        source_table="sales",
        source_column="revenue",
        filters=[FilterDefinition(column="revenue", operator="==", value="INVALID_STRING")]
    )
    with pytest.raises(Exception):
        cross.validate(metric)

def test_kpi_persistence(kpi_manager):
    metric = MetricDefinition(
        metric_name="Total Revenue",
        operation="SUM",
        source_table="sales",
        source_column="revenue",
        filters=[]
    )
    kpi = KPIDefinition(
        kpi_id="kpi_1",
        kpi_name="Total Revenue KPI",
        business_definition="Sum of all revenue",
        formula="SUM(revenue)",
        metric_definitions=[metric],
        source_tables=["sales"],
        source_columns=["revenue"],
        unit="currency",
        description="Total money",
        version=1,
        created_at=0.0,
        updated_at=0.0
    )
    
    kpi_manager.save_kpi(kpi)
    
    loaded = kpi_manager.load_kpis()
    assert len(loaded) == 1
    assert loaded[0].kpi_name == "Total Revenue KPI"
    
    # Duplicate
    with pytest.raises(ValueError, match="Duplicate"):
        kpi_manager.save_kpi(kpi)
        
    kpi.description = "Updated"
    kpi_manager.save_kpi(kpi, overwrite=True)
    assert kpi_manager.get_kpi_by_name("Total Revenue KPI").description == "Updated"

def test_kpi_safety_rejection():
    with pytest.raises(ValueError):
        MetricDefinition(
            metric_name="bad",
            operation="DROP TABLE",
            source_table="sales",
            source_column="revenue"
        )

def test_consistency_checker():
    metric = MetricDefinition(
        metric_name="rev",
        operation="SUM",
        source_table="sales",
        source_column="revenue",
        filters=[FilterDefinition(column="category", operator="==", value="A")]
    )
    checker = KPISemanticChecker()
    res = checker.check_consistency(metric)
    
    assert "SUM" in res["sql_representation"]
    assert "revenue" in res["sql_representation"]
    assert "A" in res["sql_representation"]
    
    assert "sum" in res["pandas_representation"].lower()
    
    assert "SUM" in res["powerbi_representation"]
    assert "sales" in res["powerbi_representation"].lower()
    
    assert res["status"] == "CONSISTENT"

def test_1m_row_large_validation(tmp_path):
    import time
    import hashlib
    
    # Create 1M rows
    df = pd.DataFrame({
        "id": np.arange(1000000),
        "val": np.ones(1000000)
    })
    csv_path = os.path.join(str(tmp_path), "large.csv")
    df.to_csv(csv_path, index=False)
    
    with open(csv_path, "rb") as f:
        orig_hash = hashlib.sha256(f.read()).hexdigest()
        
    ws = ProjectWorkspace(str(tmp_path))
    ws.discover_datasets()
    eng = DuckDBEngine(ws)
    
    cross = CrossValidator(SQLValidator(eng), PandasValidator(eng))
    metric = MetricDefinition(
        metric_name="large_sum",
        operation="SUM",
        source_table="large",
        source_column="val",
        filters=None
    )
    
    t0 = time.time()
    res = cross.validate(metric)
    t1 = time.time()
    
    assert res["status"] == "MATCH", res
    assert res["sql_result"] == 1000000.0
    
    with open(csv_path, "rb") as f:
        new_hash = hashlib.sha256(f.read()).hexdigest()
    
    assert orig_hash == new_hash

def test_kpi_filter_single_quote_escaping(tmp_path):
    # Test that filter values with single quotes (e.g. O'Connor) are properly escaped in SQL and handled in Pandas
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "customer": ["O'Connor", "Smith", "O'Reilly"],
        "amount": [100.0, 200.0, 300.0]
    })
    csv_path = os.path.join(str(tmp_path), "quotes.csv")
    df.to_csv(csv_path, index=False)

    ws = ProjectWorkspace(str(tmp_path))
    ws.discover_datasets()
    eng = DuckDBEngine(ws)

    metric = MetricDefinition(
        metric_name="oconnor_sum",
        operation="SUM",
        source_table="quotes",
        source_column="amount",
        filters=[FilterDefinition(column="customer", operator="==", value="O'Connor")]
    )

    sql_val = SQLValidator(eng)
    pd_val = PandasValidator(eng)
    cross = CrossValidator(sql_val, pd_val)

    res = cross.validate(metric)
    assert res["status"] == "MATCH"
    assert res["sql_result"] == 100.0
    assert res["pandas_result"] == 100.0

    checker = KPISemanticChecker()
    check_res = checker.check_consistency(metric)
    assert "''" in check_res["sql_representation"] or "O''Connor" in check_res["sql_representation"]
    assert "O'Connor" in check_res["pandas_representation"]

def test_defect_rate_calculation_distinct_affected_records():
    from src.issue_manager import StandardizedIssue
    from src.kpi_engine import KPIEngine
    engine = KPIEngine()

    # 3 total rows. Row 0 has 2 issues on 'price', Row 1 has 1 issue on 'price'.
    # Total distinct affected rows for 'price' = 2 -> defect rate should be 2/3 = 0.6667, NOT 3/3 or > 1.0
    issues = [
        StandardizedIssue(
            issue_id="ISSUE-1", source="rules", issue_type="NEGATIVE_VALUE",
            rule_or_check_name="check_positive", row_index=0, column="price",
            actual_value=-5, expected_condition="> 0", severity="HIGH",
            message="negative", recommendation="fix"
        ),
        StandardizedIssue(
            issue_id="ISSUE-2", source="quality", issue_type="OUTLIER",
            rule_or_check_name="zscore", row_index=0, column="price",
            actual_value=-5, expected_condition="normal", severity="MEDIUM",
            message="outlier", recommendation="review"
        ),
        StandardizedIssue(
            issue_id="ISSUE-3", source="rules", issue_type="INVALID_TYPE",
            rule_or_check_name="check_num", row_index=1, column="price",
            actual_value="abc", expected_condition="numeric", severity="HIGH",
            message="invalid", recommendation="fix"
        ),
    ]

    # 3 total rows, 2 unique affected rows on 'price' (Row 0 has 2 issues, Row 1 has 1 issue)
    # -> defect rate is 2 / 3 = 0.6667, NOT 3/3 (100%) or > 1.0
    rates = engine._calculate_defect_rates(issues, total_rows=3)
    assert "price" in rates
    assert rates["price"] <= 1.0
    assert round(rates["price"], 4) == round(2 / 3, 4)

    # 5 issues on 3 rows -> rate is strictly capped at 1.0 (100%), not 166.7%
    more_issues = issues + [
        StandardizedIssue(
            issue_id="ISSUE-4", source="rules", issue_type="FORMAT_ERROR",
            rule_or_check_name="format", row_index=2, column="price",
            actual_value="xyz", expected_condition="valid", severity="LOW",
            message="format", recommendation="fix"
        ),
        StandardizedIssue(
            issue_id="ISSUE-5", source="quality", issue_type="OUTLIER",
            rule_or_check_name="zscore", row_index=2, column="price",
            actual_value=9999, expected_condition="normal", severity="MEDIUM",
            message="outlier", recommendation="review"
        )
    ]
    rates_capped = engine._calculate_defect_rates(more_issues, total_rows=3)
    assert rates_capped["price"] == 1.0
    assert rates_capped["price"] <= 1.0
