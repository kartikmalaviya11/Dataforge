import pytest
import pandas as pd
import io

from src.export_service import ExportService
from src.repair_engine import RepairResult, ChangeRecord
from src.proposal_generator import RepairProposal, ApprovalState
from src.revalidation import ComparisonResult
from src.issue_manager import StandardizedIssue, IssueClassification

@pytest.fixture
def export_service():
    return ExportService()

@pytest.fixture
def sample_data():
    df = pd.DataFrame({"colA": [1, 2], "colB": ["x", "y"]})
    
    comp = ComparisonResult(
        before_issue_count=10, after_issue_count=2, resolved_issue_count=8,
        remaining_issue_count=2, new_issue_count=0,
        before_readiness=80.0, after_readiness=95.0, readiness_change=15.0,
        resolved_issues=[], remaining_issues=[], new_issues=[]
    )
    
    rec = ChangeRecord(row_index=0, column="colA", old_value=" 1 ", new_value=1, action="trim", reason="ws", classification="AUTO_FIXABLE")
    repair_results = {"trim": RepairResult(success=True, affected_rows=1, change_records=[rec], errors=[])}
    
    prop_app = RepairProposal(proposal_id="1", issue_id="i1", row_index=0, column="colA", old_value=" 1 ", proposed_value=1, action="trim", reason="ws", classification=IssueClassification.AUTO_FIXABLE, approval_state=ApprovalState.APPROVED)
    prop_rej = RepairProposal(proposal_id="2", issue_id="i2", row_index=1, column="colB", old_value="z", proposed_value="y", action="fix", reason="err", classification=IssueClassification.REVIEW_REQUIRED, approval_state=ApprovalState.REJECTED)
    proposals = [prop_app, prop_rej]
    
    unsafe_iss = StandardizedIssue(issue_id="i3", source="qc", issue_type="DUPLICATE_ID", rule_or_check_name="chk", row_index=1, column="colA", actual_value=2, expected_condition="", severity="CRITICAL", message="Dup ID", recommendation="", classification=IssueClassification.UNSAFE_TO_FIX)
    after_issues = [unsafe_iss]
    
    return df, repair_results, proposals, comp, after_issues

def test_csv_export(export_service, sample_data):
    df, _, _, _, _ = sample_data
    csv_bytes = export_service.export_csv(df)
    
    # Test A, B, D
    assert isinstance(csv_bytes, bytes)
    df_read = pd.read_csv(io.BytesIO(csv_bytes))
    
    assert list(df_read.columns) == list(df.columns)
    pd.testing.assert_frame_equal(df, df_read)
    
def test_csv_no_mutation(export_service, sample_data):
    df, _, _, _, _ = sample_data
    df_copy = df.copy(deep=True)
    export_service.export_csv(df)
    pd.testing.assert_frame_equal(df, df_copy)

def test_excel_export_structure(export_service, sample_data):
    df, rr, props, comp, ai = sample_data
    excel_bytes = export_service.export_excel(df, rr, props, comp, ai)
    
    # Test E, F, G, H, I
    assert isinstance(excel_bytes, bytes)
    xls = pd.ExcelFile(io.BytesIO(excel_bytes))
    assert 'Cleaned_Data' in xls.sheet_names
    assert 'Changes_Made' in xls.sheet_names
    assert 'Needs_Review' in xls.sheet_names
    assert 'Summary' in xls.sheet_names
    
def test_excel_cleaned_data(export_service, sample_data):
    df, rr, props, comp, ai = sample_data
    excel_bytes = export_service.export_excel(df, rr, props, comp, ai)
    
    # Test J
    df_read = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Cleaned_Data')
    assert list(df_read.columns) == list(df.columns)
    pd.testing.assert_frame_equal(df, df_read)
    
def test_excel_changes_made(export_service, sample_data):
    df, rr, props, comp, ai = sample_data
    excel_bytes = export_service.export_excel(df, rr, props, comp, ai)
    
    # Test K, R
    changes = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Changes_Made')
    assert len(changes) == 1
    assert changes.iloc[0]['Action'] == 'trim'
    # The rejected proposal does not appear here because it wasn't successfully applied by RepairEngine

def test_excel_needs_review(export_service, sample_data):
    df, rr, props, comp, ai = sample_data
    excel_bytes = export_service.export_excel(df, rr, props, comp, ai)
    
    needs_review = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Needs_Review')
    # Should contain prop_rej (status=REJECTED) and unsafe_iss (status=UNSAFE)
    assert len(needs_review) == 2
    statuses = needs_review['Status'].tolist()
    assert 'REJECTED' in statuses
    assert 'UNSAFE' in statuses

def test_excel_summary(export_service, sample_data):
    df, rr, props, comp, ai = sample_data
    excel_bytes = export_service.export_excel(df, rr, props, comp, ai)
    
    # Test M
    summary = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Summary')
    sum_dict = dict(zip(summary['Metric'], summary['Value']))
    
    assert sum_dict['Issues Before'] == 10
    assert sum_dict['Readiness Change'] == '+15.0%'
    assert sum_dict['Repairs Applied'] == 1
    assert sum_dict['Repairs Rejected'] == 1
    assert sum_dict['Unsafe Issues'] == 1

def test_excel_no_mutation(export_service, sample_data):
    # Test N
    df, rr, props, comp, ai = sample_data
    df_copy = df.copy(deep=True)
    export_service.export_excel(df, rr, props, comp, ai)
    pd.testing.assert_frame_equal(df, df_copy)

def test_empty_datasets(export_service):
    # Test L, O, P
    df = pd.DataFrame()
    csv_bytes = export_service.export_csv(df)
    assert len(csv_bytes) > 0
    
    excel_bytes = export_service.export_excel(df, {}, [], None, [])
    xls = pd.ExcelFile(io.BytesIO(excel_bytes))
    
    assert len(pd.read_excel(xls, sheet_name='Cleaned_Data')) == 0
    assert len(pd.read_excel(xls, sheet_name='Changes_Made')) == 0
    assert len(pd.read_excel(xls, sheet_name='Needs_Review')) == 0
    assert 'Summary' not in xls.sheet_names # summary is guarded by if comparison_result

def test_integration_full_flow():
    # Test Q
    from app import run_pipeline
    import streamlit as st
    from unittest.mock import patch, MagicMock
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tmp:
        tmp.write("col\nA\nA\n")
        tmp_name = tmp.name
        
    class MockUploadedFile:
        def __init__(self, name):
            self.name = name
            self.size = 100
        def getvalue(self):
            with open(tmp_name, "rb") as f:
                return f.read()
                
    file = MockUploadedFile("test.csv")
    
    mock_state = MagicMock()
    with patch("streamlit.session_state", mock_state):
        success, _ = run_pipeline(file, None)
        assert success
        
    os.remove(tmp_name)
def test_export_omits_unapproved_proposals_from_changes_made(export_service):
    df = pd.DataFrame({"A": [1]})
    from src.proposal_generator import RepairProposal, ApprovalState
    
    # We create two proposals: one APPROVED, one REJECTED, one PENDING
    prop1 = RepairProposal(proposal_id="1", issue_id="i1", action="test", classification=IssueClassification.AUTO_FIXABLE, row_index=0, column="A", old_value=1, proposed_value=2, reason="Test")
    prop1.approval_state = ApprovalState.APPROVED
    
    prop2 = RepairProposal(proposal_id="2", issue_id="i2", action="test", classification=IssueClassification.REVIEW_REQUIRED, row_index=0, column="A", old_value=1, proposed_value=2, reason="Test")
    prop2.approval_state = ApprovalState.REJECTED
    
    prop3 = RepairProposal(proposal_id="3", issue_id="i3", action="test", classification=IssueClassification.REVIEW_REQUIRED, row_index=0, column="A", old_value=1, proposed_value=2, reason="Test")
    # default is PENDING
    
    proposals = [prop1, prop2, prop3]
    
    # Simulate RepairEngine ONLY processing the APPROVED one
    from src.repair_engine import RepairResult, ChangeRecord
    rr = {
        "inst_0": RepairResult(
            success=True, affected_rows=1, 
            change_records=[ChangeRecord(row_index=0, column="A", old_value=1, new_value=2, action="test", classification="AUTO_FIXABLE", reason="Test")],
            errors=[]
        )
    }
    
    # Generate Excel
    from src.revalidation import ComparisonResult
    comp = ComparisonResult(before_issue_count=10, after_issue_count=9, resolved_issue_count=1, remaining_issue_count=9, new_issue_count=0, before_readiness=90.0, after_readiness=91.0, readiness_change=1.0, resolved_issues=[], remaining_issues=[], new_issues=[])
    
    excel_bytes = export_service.export_excel(df, rr, proposals, comp, [])
    
    # Verify
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    
    # Changes_Made should ONLY contain the 1 executed repair
    ws_changes = wb["Changes_Made"]
    assert ws_changes.max_row == 2 # 1 header + 1 data row
    
    # Needs_Review should contain the REJECTED and PENDING proposals
    ws_review = wb["Needs_Review"]
    assert ws_review.max_row == 3 # 1 header + 2 data rows
