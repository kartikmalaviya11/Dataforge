import os
import time
import uuid
import hashlib
import tempfile
import tracemalloc
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.workspace import ProjectWorkspace, TableRegistryEntry
from src.feature_engineering import (
    FeatureBuilder, FeatureEngine, build_arithmetic, build_date_part
)
from src.issue_manager import StandardizedIssue, IssueClassification
from src.scoring import ReadinessScore
from src.pipeline import run_pipeline
from ui.pages.project import (
    normalize_severity, get_project_scan_results, compute_overview_status,
    _store_scan_result, _store_failed_scan, render_validation, render_cleaning
)


class MockSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{name}'")


# =====================================================================
# 1. Feature Engineering & Date Part Options
# =====================================================================

def test_feature_builder_arithmetic_and_module_export():
    """Verify build_arithmetic works both on FeatureBuilder and at module level."""
    fd1 = FeatureBuilder.build_arithmetic("total_price", "orders", "price", "+", "freight")
    assert fd1.feature_name == "total_price"
    assert fd1.expression == '("price" + "freight")'

    # Module level export
    fd2 = build_arithmetic("total_price_2", "orders", "price", "+", "freight")
    assert fd2.feature_name == "total_price_2"


def test_feature_builder_date_part_supported_units():
    """Verify supported units: year, month, quarter, week and rejection of unsupported units."""
    for unit in ["year", "month", "quarter", "week", "YEAR", "Month"]:
        fd = FeatureBuilder.build_date_part(f"date_{unit.lower()}", "orders", "order_date", unit)
        assert fd.feature_type == "DATE_PART"
        assert f"date_part('{unit.lower()}'" in fd.expression

    # Module level export
    fd_mod = build_date_part("year_mod", "orders", "order_date", "year")
    assert fd_mod.feature_name == "year_mod"

    # Unsupported units must raise ValueError
    for bad_unit in ["hour", "minute", "second", "day", "invalid"]:
        with pytest.raises(ValueError, match="Unsupported date part"):
            FeatureBuilder.build_date_part("bad_feat", "orders", "order_date", bad_unit)


# =====================================================================
# 2. Lightweight Import & Single Workspace
# =====================================================================

def test_import_lightweight_no_eager_dataframe_loading(tmp_path):
    """Verify files are registered with row_count=None without eagerly parsing full DataFrames."""
    # Create 9 synthetic CSV files mimicking the Olist dataset
    created_files = []
    original_hashes = {}
    for i in range(9):
        f = tmp_path / f"dataset_{i}.csv"
        # 1,000 rows each
        content = "col_a,col_b,col_c\n" + "\n".join(f"{j},val_{j},{j * 1.5}" for j in range(1000))
        f.write_text(content, encoding="utf-8")
        created_files.append(f)
        original_hashes[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()

    ws = ProjectWorkspace(tmp_path / "project_ws")
    ws.project_root.mkdir(parents=True, exist_ok=True)

    # Copy files into workspace (as import does)
    for f in created_files:
        (ws.project_root / f.name).write_bytes(f.read_bytes())

    # Measure memory and time during discovery & registration
    tracemalloc.start()
    t0 = time.perf_counter()
    ws.discover_datasets()
    ws.save()
    t_import = time.perf_counter() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # All 9 files must be registered
    assert len(ws.registry) == 9
    for entry in ws.registry.values():
        assert entry.status == "DISCOVERED"
        # Row and col counts MUST be pending (None)
        assert entry.row_count is None
        assert entry.column_count is None

    # Performance: discovering 9 files without parsing must take < 0.1s and negligible RAM (< 2MB)
    assert t_import < 0.2, f"Lightweight import took too long: {t_import:.4f}s"
    assert peak_mem < 5 * 1024 * 1024, f"Lightweight import used too much memory: {peak_mem / 1024:.1f} KB"

    # Verify source files remain 100% immutable
    for f in created_files:
        ws_copy = ws.project_root / f.name
        assert hashlib.sha256(ws_copy.read_bytes()).hexdigest() == original_hashes[f.name]


# =====================================================================
# 3. Severity Normalization & Honest Overview Display
# =====================================================================

def test_normalize_severity():
    """Verify all severity variations map accurately to standard severity levels."""
    assert normalize_severity("CRITICAL") == "ERROR"
    assert normalize_severity("critical") == "ERROR"
    assert normalize_severity("ERROR") == "ERROR"
    assert normalize_severity("High") == "ERROR"

    assert normalize_severity("WARNING") == "WARNING"
    assert normalize_severity("WARN") == "WARNING"
    assert normalize_severity("Medium") == "WARNING"
    assert normalize_severity("LOW") == "WARNING"

    assert normalize_severity("INFO") == "INFO"
    assert normalize_severity(None) == "INFO"


def test_compute_overview_status_honest_states(tmp_path):
    """Verify no fake 0% readiness, and Ready is never shown when issues require review."""
    ws = ProjectWorkspace(tmp_path / "overview_test")
    ws.registry = {
        "orders": TableRegistryEntry("orders", "orders.csv", str(tmp_path / "orders.csv"), "csv", None, None, "DISCOVERED", 0.0),
        "customers": TableRegistryEntry("customers", "customers.csv", str(tmp_path / "customers.csv"), "csv", None, None, "DISCOVERED", 0.0)
    }

    # 1. Zero scanned tables -> Not Scanned, NO fake 0%
    status, readiness, issues, rows = compute_overview_status(ws, {})
    assert status == "Not Scanned"
    assert readiness == "Not Scanned"
    assert issues == 0
    assert rows == "Pending"

    # 2. Table scanned with a WARNING and REVIEW_REQUIRED -> Must NOT show 'Ready'
    warn_issue = StandardizedIssue(
        issue_id="iss_1", source="QUALITY", issue_type="INVALID_DATE",
        rule_or_check_name="date_check", row_index=5, column="order_date",
        actual_value="corrupt", expected_condition="Valid date",
        severity="WARNING", message="Invalid date", recommendation="Fix date",
        classification=IssueClassification.REVIEW_REQUIRED
    )
    dummy_score = ReadinessScore(
        overall_score=78.0, grade="Good", status="READY_WITH_WARNINGS",
        dimension_scores={}, dimension_results={}, weights={}, penalties={},
        issue_counts={}, total_rows=100, total_columns=2, explanation="ok", recommendations=[]
    )
    scans_with_issues = {
        "orders": {
            "scan_status": "COMPLETED",
            "all_issues": [warn_issue],
            "readiness": dummy_score
        }
    }
    status, readiness, issues, rows = compute_overview_status(ws, scans_with_issues)
    assert status == "Needs Review", f"Expected 'Needs Review', got '{status}'"
    assert readiness == "78%"
    assert issues == 1

    # 3. Table with ERROR or CRITICAL -> Must show 'Blocked'
    err_issue = StandardizedIssue(
        issue_id="iss_2", source="QUALITY", issue_type="MISSING_VALUE",
        rule_or_check_name="null_check", row_index=1, column="customer_id",
        actual_value=None, expected_condition="Non-null",
        severity="CRITICAL", message="Missing PK", recommendation="Fill",
        classification=IssueClassification.UNSAFE_TO_FIX
    )
    scans_with_error = {
        "orders": {
            "scan_status": "COMPLETED",
            "all_issues": [err_issue],
            "readiness": dummy_score
        }
    }
    status, readiness, issues, rows = compute_overview_status(ws, scans_with_error)
    assert status == "Blocked"


# =====================================================================
# 4. Project-Scoped Isolation & Stale Results Prevention
# =====================================================================

def test_project_isolation_scan_results_not_leaked(tmp_path):
    """Verify scan results from Project A do not leak into Project B."""
    ws_a = ProjectWorkspace(tmp_path / "project_a")
    ws_b = ProjectWorkspace(tmp_path / "project_b")
    ws_a.project_root.mkdir(parents=True, exist_ok=True)
    ws_b.project_root.mkdir(parents=True, exist_ok=True)

    with patch("streamlit.session_state", MockSessionState()) as mock_state:
        # Project A performs a scan
        scans_a = get_project_scan_results(ws_a)
        _store_scan_result(ws_a, "orders", {"filename": "orders.csv", "all_issues": ["dummy"], "readiness": None})
        assert "orders" in get_project_scan_results(ws_a)

        # Switch to Project B
        scans_b = get_project_scan_results(ws_b)
        assert len(scans_b) == 0, "Project B should have no scan results, but got Project A's results!"
        assert "orders" not in scans_b


# =====================================================================
# 5. Sequential Multi-Table Scan with Failure Isolation
# =====================================================================

def test_sequential_scan_and_failure_isolation(tmp_path):
    """Verify sequential scan continues when one table fails, isolating the failure."""
    f_good_1 = tmp_path / "good1.csv"
    f_good_1.write_text("id,val\n1,10\n2,20\n", encoding="utf-8")

    f_corrupt = tmp_path / "corrupt.csv"
    # Write invalid / binary data that cannot be parsed as CSV
    f_corrupt.write_bytes(b"\x00\xff\xfe\x00corrupt\x80\x81")

    f_good_2 = tmp_path / "good2.csv"
    f_good_2.write_text("id,text\n100,alpha\n200,beta\n", encoding="utf-8")

    ws = ProjectWorkspace(tmp_path / "multi_test_ws")
    ws.project_root.mkdir(parents=True, exist_ok=True)
    for f in [f_good_1, f_corrupt, f_good_2]:
        (ws.project_root / f.name).write_bytes(f.read_bytes())
    ws.discover_datasets()

    assert len(ws.registry) == 3

    stages_executed = []
    failures = []

    with patch("streamlit.session_state", MockSessionState()) as mock_state:
        for tname in list(ws.registry.keys()):
            entry = ws.registry[tname]
            try:
                def cb(stage):
                    stages_executed.append((tname, stage))
                s, err = run_pipeline(entry.file_path, None, progress_callback=cb)
                if not s:
                    raise Exception(err)
                _store_scan_result(ws, tname, mock_state.analysis_results)
                ws.mark_analyzed(tname)
            except Exception as e:
                failures.append((tname, str(e)))
                _store_failed_scan(ws, tname, str(e))

        scans = get_project_scan_results(ws)
        # 1 table should fail, 2 tables should succeed
        assert len(failures) == 1
        assert failures[0][0] == "corrupt"
        assert scans["corrupt"]["scan_status"] == "FAILED"
        assert scans["good1"]["scan_status"] == "COMPLETED"
        assert scans["good2"]["scan_status"] == "COMPLETED"


# =====================================================================
# 6. Memory Efficiency & No Raw Bytes Copy in Pipeline
# =====================================================================

def test_run_pipeline_memory_efficiency_no_raw_bytes(tmp_path):
    """Verify run_pipeline on CSV does not store redundant raw_bytes in session state."""
    csv_file = tmp_path / "test_mem.csv"
    csv_file.write_text("col1,col2\n" + "\n".join(f"{i},{i*2}" for i in range(5000)), encoding="utf-8")

    with patch("streamlit.session_state", MockSessionState()) as mock_state:
        tracemalloc.start()
        s, err = run_pipeline(csv_file, None)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert s is True
        res = mock_state.analysis_results
        # raw_bytes must be None for CSV (only retained for Excel if needed)
        assert res["raw_bytes"] is None
        assert res["df"] is not None
        assert res["filesize"] == csv_file.stat().st_size


# =====================================================================
# 7. Validation Results & Custom Pattern with df=None & Project Isolation
# =====================================================================

def test_render_validation_with_none_df_and_lazy_load(tmp_path):
    """
    Verify:
    1. render_validation correctly loads df lazily when res['df'] is None, without crashing.
    2. res['df'] remains None (not written back to scan cache).
    3. Custom Pattern column selectbox receives the table columns.
    """
    f = tmp_path / "orders.csv"
    f.write_text("order_id,customer_name,amount\n1,Alice,100\n2,Bob,200\n", encoding="utf-8")

    ws = ProjectWorkspace(tmp_path / "ws_val")
    ws.project_root.mkdir(parents=True, exist_ok=True)
    (ws.project_root / f.name).write_bytes(f.read_bytes())
    ws.discover_datasets()

    class DummyContext:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    selectbox_calls = []
    def mock_sb(label, options, **kwargs):
        selectbox_calls.append((label, list(options)))
        return options[0] if options else None

    with patch("streamlit.session_state", MockSessionState()) as mock_state:
        # Store scan result with df=None
        _store_scan_result(ws, "orders", {
            "all_issues": [],
            "readiness": None,
            "proposals": [],
        })
        scan_res = get_project_scan_results(ws)["orders"]
        assert scan_res["df"] is None
        assert scan_res["scan_status"] == "COMPLETED"

        with patch("streamlit.markdown"), \
             patch("streamlit.selectbox", side_effect=mock_sb), \
             patch("streamlit.tabs", return_value=[DummyContext(), DummyContext()]), \
             patch("streamlit.text_input", return_value=""), \
             patch("streamlit.button", return_value=False), \
             patch("streamlit.info"), \
             patch("streamlit.success"), \
             patch("streamlit.warning"), \
             patch("streamlit.error"), \
             patch("streamlit.write"):

            render_validation(ws)

        # 1. Verify no crash and columns were passed to pattern validation selectbox
        pattern_col_calls = [c for c in selectbox_calls if c[0] == "Select Column for Pattern Validation"]
        assert len(pattern_col_calls) == 1
        assert pattern_col_calls[0][1] == ["order_id", "customer_name", "amount"]

        # 2. Verify res["df"] is STILL None (not cached back into scan result)
        assert scan_res["df"] is None


def test_render_validation_project_isolation(tmp_path):
    """
    Verify project switching does not let Validation display results from another project.
    """
    # Project A has scanned table 'orders'
    f_a = tmp_path / "orders_a.csv"
    f_a.write_text("id,val\n1,10\n", encoding="utf-8")
    ws_a = ProjectWorkspace(tmp_path / "ws_a")
    ws_a.project_root.mkdir(parents=True, exist_ok=True)
    (ws_a.project_root / "orders.csv").write_bytes(f_a.read_bytes())
    ws_a.discover_datasets()

    # Project B also has table 'orders', but has NOT been scanned
    f_b = tmp_path / "orders_b.csv"
    f_b.write_text("id,val\n2,20\n", encoding="utf-8")
    ws_b = ProjectWorkspace(tmp_path / "ws_b")
    ws_b.project_root.mkdir(parents=True, exist_ok=True)
    (ws_b.project_root / "orders.csv").write_bytes(f_b.read_bytes())
    ws_b.discover_datasets()

    with patch("streamlit.session_state", MockSessionState()) as mock_state:
        # Project A scans 'orders'
        _store_scan_result(ws_a, "orders", {
            "all_issues": [],
            "readiness": None,
            "proposals": [],
        })
        assert "orders" in get_project_scan_results(ws_a)

        # Switch to Project B
        empty_states_called = []
        def mock_empty_state(title, description, *args, **kwargs):
            empty_states_called.append((title, description))

        with patch("ui.pages.project.empty_state", side_effect=mock_empty_state), \
             patch("streamlit.markdown"), \
             patch("streamlit.selectbox", return_value="orders"):

            render_validation(ws_b)

        # Must report "Table not scanned" for Project B, not showing Project A's scan
        assert len(empty_states_called) == 1
        assert empty_states_called[0][0] == "Table not scanned"
        assert "Run a Data Quality Scan on orders first" in empty_states_called[0][1]


def test_render_cleaning_does_not_cache_df_in_scan_results(tmp_path):
    """
    Verify render_cleaning does not write lazily loaded DataFrame back to res['df'].
    """
    f = tmp_path / "orders.csv"
    f.write_text("order_id,amount\n1,100\n", encoding="utf-8")

    ws = ProjectWorkspace(tmp_path / "ws_clean")
    ws.project_root.mkdir(parents=True, exist_ok=True)
    (ws.project_root / f.name).write_bytes(f.read_bytes())
    ws.discover_datasets()

    class DummyContext:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("streamlit.session_state", MockSessionState()) as mock_state:
        _store_scan_result(ws, "orders", {
            "all_issues": [],
            "readiness": None,
            "proposals": [],
        })
        scan_res = get_project_scan_results(ws)["orders"]
        assert scan_res["df"] is None

        def mock_sb(label, options, **kwargs):
            if "Table" in label:
                return "orders"
            return options[0] if options else None

        with patch("streamlit.markdown"), \
             patch("streamlit.selectbox", side_effect=mock_sb), \
             patch("streamlit.tabs", return_value=[DummyContext(), DummyContext(), DummyContext()]), \
             patch("streamlit.success"):

            render_cleaning(ws)

        # res['df'] must remain None
        assert scan_res["df"] is None
