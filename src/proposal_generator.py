from dataclasses import dataclass
from typing import Any, List, Optional
from enum import Enum
import pandas as pd

from .issue_manager import StandardizedIssue, IssueClassification
from .repair_engine import RepairInstruction

class ApprovalState(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

@dataclass
class RepairProposal:
    proposal_id: str
    issue_id: str
    row_index: Optional[Any]
    column: Optional[str]
    old_value: Optional[Any]
    proposed_value: Optional[Any]
    action: str
    reason: str
    classification: IssueClassification
    approval_state: ApprovalState = ApprovalState.PENDING
    
    def to_repair_instruction(self) -> RepairInstruction:
        return RepairInstruction(
            action=self.action,
            classification=self.classification,
            column=self.column,
            row_index=self.row_index,
            expected_state=None,
            proposed_value=self.proposed_value,
            reason=self.reason,
            approved=(self.approval_state == ApprovalState.APPROVED)
        )

class ProposalGenerator:
    """
    Generates RepairProposals from StandardizedIssues without mutating the DataFrame.
    (Phase 3)
    """
    def __init__(self):
        self._counter = 0
        
    def _next_id(self) -> str:
        self._counter += 1
        return f"PROP-{self._counter:04d}"
        
    def generate_proposals(self, df: pd.DataFrame, issues: List[StandardizedIssue]) -> List[RepairProposal]:
        proposals = []
        
        for issue in issues:
            if issue.classification == IssueClassification.UNSAFE_TO_FIX:
                continue
                
            prop = self._generate_single_proposal(df, issue)
            if prop:
                proposals.append(prop)
                
        # Also check for column whitespace (which isn't a row-level issue)
        for col in df.columns:
            if isinstance(col, str):
                new_col = col.strip()
                if new_col != col:
                    proposals.append(RepairProposal(
                        proposal_id=self._next_id(),
                        issue_id="COL-WS",
                        row_index=None,
                        column=col,
                        old_value=col,
                        proposed_value=new_col,
                        action="normalize_column_name_whitespace",
                        reason="Remove leading/trailing whitespace from column name",
                        classification=IssueClassification.AUTO_FIXABLE
                    ))
                    
        return proposals

    def _generate_single_proposal(self, df: pd.DataFrame, issue: StandardizedIssue) -> Optional[RepairProposal]:
        if issue.issue_type == "WHITESPACE":
            if issue.column and issue.row_index is not None and issue.column in df.columns:
                old_val = issue.actual_value
                if isinstance(old_val, str):
                    new_val = old_val.strip()
                    if old_val != new_val:
                        return RepairProposal(
                            proposal_id=self._next_id(),
                            issue_id=issue.issue_id,
                            row_index=issue.row_index,
                            column=issue.column,
                            old_value=old_val,
                            proposed_value=new_val,
                            action="trim_whitespace",
                            reason="Remove leading/trailing whitespace",
                            classification=issue.classification
                        )
                        
        elif issue.issue_type == "INCONSISTENT_CASE":
            if issue.column and issue.row_index is not None and issue.column in df.columns:
                old_val = issue.actual_value
                if isinstance(old_val, str):
                    # Deterministic normalization strategy: Title Case for names/cities.
                    new_val = old_val.strip().title()
                    if old_val != new_val:
                        return RepairProposal(
                            proposal_id=self._next_id(),
                            issue_id=issue.issue_id,
                            row_index=issue.row_index,
                            column=issue.column,
                            old_value=old_val,
                            proposed_value=new_val,
                            action="normalize_case",
                            reason="Normalize casing to Title Case",
                            classification=issue.classification
                        )
                        
        elif issue.issue_type == "DUPLICATE_ROW":
            return RepairProposal(
                proposal_id=self._next_id(),
                issue_id=issue.issue_id,
                row_index=issue.row_index,
                column=None,
                old_value="Entire Row",
                proposed_value="Removed",
                action="remove_exact_duplicates",
                reason="Remove exact duplicate row",
                classification=issue.classification
            )
            
        elif issue.issue_type == "INVALID_NUMERIC":
            if issue.column and issue.row_index is not None and issue.column in df.columns:
                old_val = issue.actual_value
                if isinstance(old_val, str):
                    val_strip = old_val.strip()
                    
                    # Identifiers protection
                    col_lower = issue.column.lower()
                    if any(kw in col_lower for kw in ["id", "code", "reference", "ref", "guid", "uuid"]):
                        return None
                        
                    # Special floats protection
                    if val_strip.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
                        return None
                        
                    # Leading zeros protection
                    if val_strip.startswith("0") and len(val_strip) > 1 and not val_strip.startswith("0."):
                        return None
                    if val_strip.startswith("-0") and len(val_strip) > 2 and not val_strip.startswith("-0."):
                        return None
                        
                    try:
                        new_val = float(val_strip)
                        if new_val.is_integer() and '.' not in val_strip:
                            new_val = int(new_val)
                            
                        return RepairProposal(
                            proposal_id=self._next_id(),
                            issue_id=issue.issue_id,
                            row_index=issue.row_index,
                            column=issue.column,
                            old_value=old_val,
                            proposed_value=new_val,
                            action="convert_obvious_numeric",
                            reason="Convert obvious string to numeric",
                            classification=issue.classification
                        )
                    except ValueError:
                        pass
                        
        elif issue.issue_type == "INVALID_DATE":
            if issue.column and issue.row_index is not None and issue.column in df.columns:
                old_val = issue.actual_value
                if isinstance(old_val, str):
                    unambiguous_formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"]
                    new_val = None
                    for fmt in unambiguous_formats:
                        try:
                            parsed = pd.to_datetime(old_val, format=fmt, exact=True)
                            if not pd.isna(parsed):
                                new_val = parsed
                                break
                        except (ValueError, TypeError):
                            continue
                            
                    if new_val is not None:
                        return RepairProposal(
                            proposal_id=self._next_id(),
                            issue_id=issue.issue_id,
                            row_index=issue.row_index,
                            column=issue.column,
                            old_value=old_val,
                            proposed_value=new_val,
                            action="normalize_obvious_date",
                            reason="Convert obvious string to datetime",
                            classification=issue.classification
                        )
                        
        return None
