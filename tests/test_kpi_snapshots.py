import pytest
import os
import shutil
from src.workspace import ProjectWorkspace
from src.kpi_engine import KPIManager, KPISnapshot

@pytest.fixture
def workspace():
    ws_dir = ".dataforge_test_kpi"
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)
    os.makedirs(ws_dir, exist_ok=True)
    ws = ProjectWorkspace(ws_dir)
    yield ws
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)

def test_kpi_snapshot_persistence(workspace):
    km = KPIManager(workspace)

    # initially empty
    assert len(km.load_snapshots()) == 0

    # create snapshot
    snap = KPISnapshot(
        snapshot_id="s1",
        kpi_id="k1",
        kpi_name="Test KPI",
        dataset_version_id="v1",
        value=100.5,
        recorded_at="2026-10-08T00:00:00Z"
    )
    km.save_snapshot(snap)

    # test load
    snaps = km.load_snapshots()
    assert len(snaps) == 1
    assert snaps[0].snapshot_id == "s1"
    assert snaps[0].kpi_name == "Test KPI"
    assert snaps[0].value == 100.5

def test_kpi_snapshot_comparison(workspace):
    km = KPIManager(workspace)
    snap1 = KPISnapshot("s1", "k1", "Test", "v1", 100, "2026-10-08")
    snap2 = KPISnapshot("s2", "k1", "Test", "v2", 110, "2026-10-09")
    km.save_snapshot(snap1)
    km.save_snapshot(snap2)

    snaps = km.load_snapshots()
    assert len(snaps) == 2
    assert snaps[1].value > snaps[0].value
    assert snaps[0].dataset_version_id != snaps[1].dataset_version_id

    # Test compare_snapshots using objects and strings
    comp = km.compare_snapshots(snap1, snap2)
    assert comp["snapshot_id_a"] == "s1"
    assert comp["snapshot_id_b"] == "s2"
    assert comp["dataset_version_id_a"] == "v1"
    assert comp["dataset_version_id_b"] == "v2"
    assert comp["versions_distinguishable"] is True
    assert comp["value_a"] == 100
    assert comp["value_b"] == 110
    assert comp["absolute_difference"] == 10.0
    assert comp["relative_change_pct"] == 10.0
    assert comp["status"] == "INCREASED"

    # Compare by snapshot ID from saved data
    comp_by_id = km.compare_snapshots("s1", "s2")
    assert comp_by_id["absolute_difference"] == 10.0
    assert comp_by_id["status"] == "INCREASED"

    # Compare reverse (decrease)
    comp_rev = km.compare_snapshots("s2", "s1")
    assert comp_rev["absolute_difference"] == -10.0
    assert round(comp_rev["relative_change_pct"], 2) == -9.09
    assert comp_rev["status"] == "DECREASED"

def test_kpi_snapshot_compare_errors(workspace):
    km = KPIManager(workspace)
    snap1 = KPISnapshot("s1", "k1", "Test", "v1", 100, "2026-10-08")
    km.save_snapshot(snap1)
    with pytest.raises(ValueError, match="Snapshot not found: nonexistent"):
        km.compare_snapshots("s1", "nonexistent")

def test_kpi_snapshot_zero_baseline_and_negatives(workspace):
    km = KPIManager(workspace)
    s_zero = KPISnapshot("s0", "k1", "Zero", "v1", 0, "2026-10-01")
    s_pos = KPISnapshot("s1", "k1", "Pos", "v2", 50, "2026-10-02")
    s_neg = KPISnapshot("s2", "k1", "Neg", "v3", -30, "2026-10-03")
    s_zero2 = KPISnapshot("s3", "k1", "Zero2", "v4", 0, "2026-10-04")
    s_neg_base = KPISnapshot("s4", "k1", "NegBase", "v5", -100, "2026-10-05")
    s_neg_comp = KPISnapshot("s5", "k1", "NegComp", "v6", -150, "2026-10-06")

    for s in [s_zero, s_pos, s_neg, s_zero2, s_neg_base, s_neg_comp]:
        km.save_snapshot(s)

    # 1. Baseline zero, comparison positive non-zero
    c1 = km.compare_snapshots("s0", "s1")
    assert c1["value_a"] == 0
    assert c1["value_b"] == 50
    assert c1["absolute_difference"] == 50.0
    assert c1["relative_change_pct"] is None  # Never divide by zero
    assert "Undefined (baseline is zero)" in c1["relative_change_note"]
    assert c1["status"] == "INCREASED"

    # 2. Baseline zero, comparison negative non-zero
    c2 = km.compare_snapshots("s0", "s2")
    assert c2["value_a"] == 0
    assert c2["value_b"] == -30
    assert c2["absolute_difference"] == -30.0
    assert c2["relative_change_pct"] is None  # Never divide by zero
    assert "Undefined (baseline is zero)" in c2["relative_change_note"]
    assert c2["status"] == "DECREASED"

    # 3. Both values zero
    c3 = km.compare_snapshots("s0", "s3")
    assert c3["value_a"] == 0
    assert c3["value_b"] == 0
    assert c3["absolute_difference"] == 0.0
    assert c3["relative_change_pct"] == 0.0
    assert c3["status"] == "UNCHANGED"

    # 4. Negative baseline comparison
    c4 = km.compare_snapshots("s4", "s5")
    assert c4["value_a"] == -100
    assert c4["value_b"] == -150
    assert c4["absolute_difference"] == -50.0
    assert c4["relative_change_pct"] == -50.0
    assert c4["status"] == "DECREASED"

def test_kpi_manager_kpi_methods_intact(workspace):
    from src.kpi_engine import KPIDefinition
    km = KPIManager(workspace)
    assert len(km.load_kpis()) == 0

    kpi = KPIDefinition(
        kpi_id="k1",
        kpi_name="Total Revenue",
        business_definition="Sum of all revenue",
        formula="SUM(amount)",
        metric_definitions=[],
        source_tables=["orders"],
        source_columns=["amount"],
        unit="USD",
        description="Total Revenue"
    )
    km.save_kpi(kpi)
    loaded = km.load_kpis()
    assert len(loaded) == 1
    assert loaded[0].kpi_name == "Total Revenue"
    assert km.get_kpi_by_name("Total Revenue") is not None
    assert km.get_kpi_by_name("Nonexistent") is None

def test_calculate_kpi_value_distinct_count_ratio_and_errors(workspace):
    import pandas as pd
    from src.kpi_engine import KPIRecommendation
    from src.sql_engine import DuckDBEngine

    # Create test data: 4 rows, customer_id has 2 unique values, profit and sales
    df = pd.DataFrame({
        "order_id": [101, 102, 103, 104],
        "customer_id": [1, 1, 2, 2],
        "sales": [100.0, 200.0, 300.0, 400.0],
        "profit": [20.0, 40.0, 60.0, 80.0]
    })
    path_csv = workspace.project_root / "orders.csv"
    df.to_csv(path_csv, index=False)
    workspace.discover_datasets()

    km = KPIManager(workspace)

    # 1. Test DISTINCTCOUNT - must be 2, not 4 (len(df))
    kpi_distinct = KPIRecommendation(
        kpi_name="Unique Customers",
        category="Transaction",
        priority="HIGH",
        status="AVAILABLE",
        required_columns=["customer_id"],
        available_columns=["customer_id"],
        calculation_logic="DISTINCTCOUNT(customer_id)",
        explanation="Counts distinct customers"
    )
    val_distinct, status = km.calculate_kpi_value(kpi_distinct)
    assert status == "SUCCESS"
    assert val_distinct == 2.0  # NOT 4.0!

    # 2. Test Ratio: SUM(profit) / SUM(sales) = 200 / 1000 = 0.2
    kpi_ratio = KPIRecommendation(
        kpi_name="Profit Margin",
        category="Ratio",
        priority="HIGH",
        status="AVAILABLE",
        required_columns=["profit", "sales"],
        available_columns=["profit", "sales"],
        calculation_logic="SUM(profit) / SUM(sales)",
        explanation="Profit ratio"
    )
    val_ratio, status = km.calculate_kpi_value(kpi_ratio)
    assert status == "SUCCESS"
    assert val_ratio == 0.2  # NOT 200.0 (profit alone)!

    # 3. Test Unsupported / missing column - must return error status, not a number
    kpi_missing = KPIRecommendation(
        kpi_name="Invalid KPI",
        category="Aggregation",
        priority="LOW",
        status="AVAILABLE",
        required_columns=["nonexistent_col"],
        available_columns=["nonexistent_col"],
        calculation_logic="SUM(nonexistent_col)",
        explanation="Invalid"
    )
    val_missing, err_status = km.calculate_kpi_value(kpi_missing)
    assert val_missing is None
    assert "not found" in err_status.lower()

    # 4. Test UNAVAILABLE status
    kpi_unavail = KPIRecommendation(
        kpi_name="Unavailable KPI",
        category="Aggregation",
        priority="LOW",
        status="UNAVAILABLE",
        required_columns=["missing"],
        available_columns=[],
        calculation_logic="N/A",
        explanation="Unavailable"
    )
    val_unavail, err_unavail = km.calculate_kpi_value(kpi_unavail)
    assert val_unavail is None
    assert "UNAVAILABLE" in err_unavail

    # 5. Test Ratio with division by zero
    df_zero = pd.DataFrame({"a": [10.0], "b": [0.0]})
    df_zero.to_csv(workspace.project_root / "zero_tbl.csv", index=False)
    workspace.discover_datasets()

    kpi_div0 = KPIRecommendation(
        kpi_name="DivZero",
        category="Ratio",
        priority="LOW",
        status="AVAILABLE",
        required_columns=["a", "b"],
        available_columns=["a", "b"],
        calculation_logic="SUM(a) / SUM(b)",
        explanation="Zero div"
    )
    val_div0, err_div0 = km.calculate_kpi_value(kpi_div0)
    assert val_div0 is None
    assert "division by zero" in err_div0.lower()
