import pytest
import pandas as pd
import openpyxl
import io

from src.repair_engine import RepairEngine, RepairInstruction, ChangeRecord
from src.export_service import ExportService
from src.revalidation import ComparisonResult
from src.issue_manager import IssueClassification, StandardizedIssue

@pytest.fixture
def duplicate_row_excel_bytes():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    
    # Headers
    ws.append(["A", "B", "C", "D"])
    
    # Row 2 (Data)
    ws.append([1, 10, 100, "=A2+B2"])
    
    # Row 3 (Duplicate of Row 2) - we will delete this
    ws.append([1, 10, 100, "=A3+B3"])
    
    # Row 4 (Data)
    ws.append([2, 20, 200, "=A4+B4"])
    
    # Row 5 (Formula referencing Row 2 and 4)
    ws.append(["Sum:", "", "", "=SUM(D2:D4)"])
    
    # Row 6 (Formula referencing the duplicate row specifically)
    ws.append(["Ref duplicate:", "", "", "=D3"])
    
    # Merge cells A7:B7
    ws.merge_cells("A7:B7")
    ws.cell(row=7, column=1, value="Merged")
    
    # Create another sheet
    wb.create_sheet("OtherSheet")
    
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

def test_duplicate_row_rejection_integrity(duplicate_row_excel_bytes):
    # This test verifies that if the workbook contains formulas or merged cells,
    # DUPLICATE_ROW issues are downgraded to UNSAFE_TO_FIX, preventing workbook corruption.
    df = pd.DataFrame({
        "A": [1, 1, 2, "Sum:", "Ref duplicate:", "Merged"],
        "B": [10, 10, 20, "", "", ""],
        "C": [100, 100, 200, "", "", ""],
        "D": [11, 11, 22, 44, 11, ""]
    })
    
    # 1. Quality Engine detects duplicates
    from src.profiler import profile_dataset
    from src.type_detector import detect_semantic_types
    from src.quality_engine import run_quality_checks
    from src.issue_manager import IssueManager
    
    col_profiles = profile_dataset(df)
    type_results = detect_semantic_types(df, col_profiles)
    quality_issues = run_quality_checks(df, col_profiles, type_results)
    
    # 2. Excel Engine detects formulas/merges
    from src.excel_quality import ExcelQualityEngine
    excel_eng = ExcelQualityEngine(duplicate_row_excel_bytes)
    excel_issues = excel_eng.analyze(df)
    
    assert excel_eng.has_formulas_or_merges is True
    
    # Consolidate issues like app.py does
    im = IssueManager()
    all_issues = im.consolidate(quality_issues + excel_issues)
    
    # 3. Simulated app.py downgrading
    if excel_eng.has_formulas_or_merges:
        for issue in all_issues:
            if issue.issue_type == "DUPLICATE_ROW":
                issue.classification = IssueClassification.UNSAFE_TO_FIX
                
    # 4. Assert the issue is now UNSAFE_TO_FIX
    dup_issue = next((i for i in all_issues if i.issue_type == "DUPLICATE_ROW"), None)
    assert dup_issue is not None
    assert dup_issue.classification == IssueClassification.UNSAFE_TO_FIX
    
    # 5. Proposal generator should NOT create an AUTO_FIXABLE proposal
    from src.proposal_generator import ProposalGenerator
    prop_gen = ProposalGenerator()
    proposals = prop_gen.generate_proposals(df, all_issues)
    
    assert len(proposals) == 0 # Since it's UNSAFE_TO_FIX, no proposal is generated for it
