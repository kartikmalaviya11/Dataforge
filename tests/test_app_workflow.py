import pytest
import os
from pathlib import Path
import collections
from streamlit.testing.v1 import AppTest

def test_streamlit_initial_state():
    """Test A: Fresh upload clears state / App initializes correctly"""
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert at.session_state.analysis_results is None
    
def test_streamlit_workflow_mocked(tmp_path):
    """Test the tabs and interactions using a mock session state."""
    at = AppTest.from_file("../app.py", default_timeout=30)
    
    # We must populate session_state manually to avoid long processing time 
    # during UI tests and to avoid upload widget limitations in AppTest
    import pandas as pd
    from src.ingestion import DatasetProfile
    from src.proposal_generator import RepairProposal, ApprovalState
    from src.issue_manager import StandardizedIssue, IssueClassification
    from src.revalidation import ValidationSnapshot
    
    df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
    
    # Mock some data
    mock_issues = [
        StandardizedIssue("ID1", "SOURCE", "DUPLICATE_ROW", "Duplicate Check", 0, "A", "val", "No duplicate", "CRITICAL", "Msg", "Rec")
    ]
    mock_issues[0].classification = IssueClassification.AUTO_FIXABLE
    
    mock_proposals = [
        RepairProposal("P1", "ID1", 0, "A", 1, None, "DROP_ROW", "Drop row", IssueClassification.AUTO_FIXABLE)
    ]
    
    # Run the app first to initialize state
    at.run()
    
    # Inject state
    class MockReadiness:
        overall_score = 85.0
        dimension_scores = {"A": 100}
        
    class MockProfile:
        row_count = 100
        column_count = 5
        column_names = ["A", "B"]
        
    class MockColProfile:
        name = "A"
        null_count = 0
        null_percentage = 0.0
        unique_percentage = 100.0
        
    class MockTypeResult:
        column_name = "A"
        storage_type = "int64"
        detected_type = "Numeric"
        confidence = 1.0
        status = "MATCH"
        
    class MockKPI:
        kpi_name = "K1"
        category = "C1"
        priority = "High"
        status = "AVAILABLE"
        calculation_logic = "L1"
        explanation = "E1"
        required_columns = ["A"]
        available_columns = ["A"]
        
    class MockDAX:
        measure_name = "M1"
        kpi_name = "K1"
        status = "AVAILABLE"
        dax_expression = "DAX1"
        
    class MockSQL:
        query_name = "Q1"
        python_result = 1
        sql_result = 1
        difference = 0
        match_status = "MATCH"
        sql = "SELECT 1"

    # Create dummy report
    dummy_report = tmp_path / "report_dummy.csv"
    dummy_report.write_text("dummy,data\n1,2", encoding="utf-8")

    at.session_state.analysis_results = {
        "df": df,
        "profile": MockProfile(),
        "col_profiles": [MockColProfile()],
        "type_results": [MockTypeResult()],
        "all_issues": mock_issues,
        "proposals": mock_proposals,
        "readiness": MockReadiness(),
        "kpis": [MockKPI()],
        "dax": [MockDAX()],
        "sql_results": [MockSQL()],
        "out_dir": tmp_path,
        "filename": "test.csv",
        "raw_bytes": b"mock",
        "filesize": 100,
        "elapsed": 1.0,
        "before_snapshot": ValidationSnapshot(mock_issues, MockReadiness(), [MockColProfile()], [MockTypeResult()]),
        "repaired_df": None,
        "repair_results": None,
        "after_snapshot": None,
        "comparison_result": None
    }
    
    at.run()
    assert not at.exception
    
    # Tab 0: Overview
    assert "Overview Summary" in at.markdown[4].value
    
    # Let's try to click "Approve All AUTO_FIXABLE" on the Suggested Fixes tab
    # It's a button.
    approve_button = [btn for btn in at.button if btn.label == "Approve All AUTO_FIXABLE"]
    if approve_button:
        approve_button[0].click()
        at.run()
        # Verify state updated
        assert at.session_state.analysis_results["proposals"][0].approval_state == ApprovalState.APPROVED
        
    # Let's try to click Analyze New
    analyze_new_btn = [btn for btn in at.button if btn.label == "Analyze New"]
    if analyze_new_btn:
        analyze_new_btn[0].click()
        at.run()
        assert at.session_state.analysis_results is None
