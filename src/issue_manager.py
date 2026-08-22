"""
Phase 6: Issue Management

Combines and standardizes Phase 4 QualityIssues and Phase 5 RuleViolations.
Generates deterministic issue IDs, assigns severities to quality issues,
and provides remediation recommendations.
"""

from dataclasses import dataclass
from typing import Any, Optional, List
import hashlib
from enum import Enum

from .quality_engine import QualityIssue
from .rules import RuleViolation

class IssueClassification(Enum):
    AUTO_FIXABLE = "AUTO_FIXABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSAFE_TO_FIX = "UNSAFE_TO_FIX"

@dataclass
class StandardizedIssue:
    issue_id: str
    source: str
    issue_type: str
    rule_or_check_name: str
    row_index: Optional[Any]
    column: Optional[str]
    actual_value: Optional[Any]
    expected_condition: str
    severity: str
    message: str
    recommendation: str
    classification: IssueClassification = IssueClassification.UNSAFE_TO_FIX

def _classify_issue(source: str, issue_type: str, column: Optional[str] = None) -> IssueClassification:
    """
    Deterministic classification of data quality and business rule issues.
    """
    # 1. AUTO_FIXABLE
    if issue_type in ("BLANK_VALUE", "DUPLICATE_ROW"):
        return IssueClassification.AUTO_FIXABLE

    # 3. REVIEW_REQUIRED
    # INVALID_NUMERIC and INVALID_DATE should require user approval since they can alter format or lose data (e.g. leading zeros)
    if issue_type in ("INVALID_NUMERIC", "INVALID_DATE"):
        return IssueClassification.REVIEW_REQUIRED

    # 2. UNSAFE_TO_FIX
    if issue_type == "DUPLICATE_ID":
        return IssueClassification.UNSAFE_TO_FIX
        
    if issue_type == "INVALID_EMAIL":
        return IssueClassification.UNSAFE_TO_FIX

    if issue_type == "MISSING_VALUE":
        if column:
            col_lower = column.lower()
            if "email" in col_lower or "id" in col_lower or "guid" in col_lower or "uuid" in col_lower:
                return IssueClassification.UNSAFE_TO_FIX
        return IssueClassification.REVIEW_REQUIRED

    # 3. REVIEW_REQUIRED
    if issue_type in ("INVALID_CATEGORY", "OUT_OF_RANGE", "CONSISTENCY_VIOLATION"):
        return IssueClassification.REVIEW_REQUIRED

    if source == "business_rule":
        if issue_type in ("range", "allowed_values", "comparison"):
            return IssueClassification.REVIEW_REQUIRED
        elif issue_type in ("uniqueness", "referential_integrity", "required_column", "regex", "custom"):
            return IssueClassification.UNSAFE_TO_FIX
            
    # Conservative fallback
    return IssueClassification.UNSAFE_TO_FIX

_QUALITY_SEVERITY_MAP = {
    "MISSING_VALUE": "LOW",
    "BLANK_VALUE": "LOW",
    "DUPLICATE_ROW": "MEDIUM",
    "DUPLICATE_ID": "CRITICAL",
    "INVALID_EMAIL": "MEDIUM",
    "INVALID_DATE": "HIGH",
    "INVALID_NUMERIC": "HIGH",
    "INVALID_CATEGORY": "MEDIUM",
    "OUT_OF_RANGE": "HIGH",
    "CONSISTENCY_VIOLATION": "HIGH"
}

_QUALITY_RECOMMENDATION_MAP = {
    "MISSING_VALUE": "Impute missing value or drop row if critical.",
    "BLANK_VALUE": "Trim whitespace or treat as missing.",
    "DUPLICATE_ROW": "Review and deduplicate exact row matches.",
    "DUPLICATE_ID": "Investigate ID generation or deduplicate entities.",
    "INVALID_EMAIL": "Correct email format or flag user for update.",
    "INVALID_DATE": "Standardize date format or fix data entry issue.",
    "INVALID_NUMERIC": "Remove non-numeric characters or correct data type.",
    "INVALID_CATEGORY": "Map to an allowed category or expand allowed list.",
    "OUT_OF_RANGE": "Verify value against domain bounds.",
    "CONSISTENCY_VIOLATION": "Investigate contradictory data across columns."
}

def _generate_issue_id(source: str, issue_type: str, rule_name: str, row_index: Any, column: Optional[str]) -> str:
    components = [
        str(source),
        str(issue_type),
        str(rule_name),
        str(row_index) if row_index is not None else "DATASET",
        str(column) if column is not None else "DATASET"
    ]
    raw_id = "|".join(components)
    return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()

class IssueManager:
    """Manages and consolidates data quality and business rule issues."""
    
    def consolidate(self, issues: list) -> List[StandardizedIssue]:
        """Normalize both QualityIssue and RuleViolation into StandardizedIssue."""
        standardized = []
        for issue in issues:
            if isinstance(issue, QualityIssue):
                standardized.append(self._normalize_quality_issue(issue))
            elif isinstance(issue, RuleViolation):
                standardized.append(self._normalize_rule_violation(issue))
            else:
                # Safely ignore or log unknown issue types
                pass
        return standardized

    def _normalize_quality_issue(self, issue: QualityIssue) -> StandardizedIssue:
        issue_id = _generate_issue_id(
            source="quality_check",
            issue_type=issue.issue_type,
            rule_name=issue.check_name,
            row_index=issue.row_index,
            column=issue.column
        )
        severity = _QUALITY_SEVERITY_MAP.get(issue.issue_type, "MEDIUM")
        recommendation = _QUALITY_RECOMMENDATION_MAP.get(issue.issue_type, "Review data quality issue.")
        classification = _classify_issue(source="quality_check", issue_type=issue.issue_type, column=issue.column)
        
        return StandardizedIssue(
            issue_id=issue_id,
            source="quality_check",
            issue_type=issue.issue_type,
            rule_or_check_name=issue.check_name,
            row_index=issue.row_index,
            column=issue.column,
            actual_value=issue.actual_value,
            expected_condition=issue.expected_condition or "",
            severity=severity,
            message=issue.description,
            recommendation=recommendation,
            classification=classification
        )

    def _normalize_rule_violation(self, issue: RuleViolation) -> StandardizedIssue:
        issue_id = _generate_issue_id(
            source="business_rule",
            issue_type=issue.rule_type,
            rule_name=issue.rule_name,
            row_index=issue.row_index,
            column=issue.column
        )
        recommendation = "Review business rule logic or correct data to meet business requirements."
        classification = _classify_issue(source="business_rule", issue_type=issue.rule_type, column=issue.column)
        
        return StandardizedIssue(
            issue_id=issue_id,
            source="business_rule",
            issue_type=issue.rule_type,
            rule_or_check_name=issue.rule_name,
            row_index=issue.row_index,
            column=issue.column,
            actual_value=issue.actual_value,
            expected_condition=issue.expected_condition or "",
            severity=issue.severity,
            message=issue.message,
            recommendation=recommendation,
            classification=classification
        )
