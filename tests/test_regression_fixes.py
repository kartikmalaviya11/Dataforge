import pandas as pd
import pytest
from src.quality_engine import check_case_inconsistencies, check_whitespace_issues
from src.profiler import profile_dataset
from src.proposal_generator import ProposalGenerator
from src.repair_engine import RepairEngine
from src.issue_manager import IssueClassification
from src.quality_engine import QualityIssue
from src.export_service import ExportService
import os

def test_whitespace_vs_case_separation():
    data = pd.DataFrame({
        "Name": ["Priya Patel", " Priya Patel ", "priya patel"],
        "Status": ["Active", "active", "ACTIVE"]
    })
    
    profiles = profile_dataset(data)
    
    # 1. Whitespace check
    ws_issues = check_whitespace_issues(data, profiles)
    ws_rows = [i.row_index for i in ws_issues if i.column == "Name"]
    assert 1 in ws_rows, "Whitespace should be detected for row 1"
    
    # 2. Case inconsistency check
    case_issues = check_case_inconsistencies(data, profiles)
    case_rows_name = [i.row_index for i in case_issues if i.column == "Name"]
    
    data_only_ws = pd.DataFrame({
        "Name": ["Priya Patel", " Priya Patel "]
    })
    profiles_only_ws = profile_dataset(data_only_ws)
    case_issues_only_ws = check_case_inconsistencies(data_only_ws, profiles_only_ws)
    assert len(case_issues_only_ws) == 0, "Should not flag case inconsistency if only whitespace differs"
    
    # But Status should have case issues
    case_rows_status = [i.row_index for i in case_issues if i.column == "Status"]
    assert len(case_rows_status) == 2, "All Status rows should be flagged for case inconsistency"

def test_normalize_case_export(tmp_path):
    data = pd.DataFrame({
        "City": ["Surat", "surat", "SURAT", "surat"]
    })
    
    # Manually create issue and proposal
    issue = QualityIssue(
        row_index=0,
        column="City",
        issue_type="INCONSISTENT_CASE",
        check_name="test",
        actual_value="Surat",
        description="Inconsistent"
    )
    
    from src.issue_manager import IssueManager
    im = IssueManager()
    std_issues = im.consolidate([issue])
    
    gen = ProposalGenerator()
    proposals = gen.generate_proposals(data, std_issues)
    
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.proposed_value == "surat", "Canonical value 'surat' (most freq) should be chosen"
    
    
    from src.proposal_generator import ApprovalState
    proposal.approval_state = ApprovalState.APPROVED
    instruction = proposal.to_repair_instruction()

    
    engine = RepairEngine()
    repaired_df, result = engine.apply(data, [instruction])
    
    assert result["instruction_0"].success
    assert len(result["instruction_0"].change_records) == 1
    record = result["instruction_0"].change_records[0]
    
    # Must be a ChangeRecord object
    from src.repair_engine import ChangeRecord
    assert isinstance(record, ChangeRecord)
    
    # Export it
    exporter = ExportService()
    
    excel_bytes = exporter.export_excel(
        df=repaired_df, 
        repair_results={'instruction_0': result['instruction_0']},
        proposals=[proposal],
        comparison_result=None,
        after_issues=[]
    )
    
    assert len(excel_bytes) > 0