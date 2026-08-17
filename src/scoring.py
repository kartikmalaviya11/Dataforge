"""
Phase 7: Data Readiness Scoring

Builds a deterministic, explainable readiness score based on actual pipeline outputs.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import pandas as pd
from collections import Counter

from .issue_manager import StandardizedIssue

@dataclass
class DimensionResult:
    score: float
    is_applicable: bool
    issue_count: int
    row_penalty: float
    dataset_penalty: float
    defect_rate: float
    reason: str
    evidence: str

@dataclass
class ReadinessScore:
    overall_score: float
    grade: str
    status: str
    dimension_scores: Dict[str, float]
    dimension_results: Dict[str, DimensionResult]
    weights: Dict[str, float]
    penalties: Dict[str, float]
    issue_counts: Dict[str, int]
    total_rows: int
    total_columns: int
    explanation: str
    recommendations: List[str]

DEFAULT_WEIGHTS = {
    "COMPLETENESS": 0.25,
    "VALIDITY": 0.25,
    "CONSISTENCY": 0.20,
    "UNIQUENESS": 0.15,
    "RULE_COMPLIANCE": 0.15
}

SEVERITY_PENALTY = {
    "INFO": 0.0,
    "LOW": 0.1,
    "MEDIUM": 0.5,
    "HIGH": 1.0,
    "CRITICAL": 5.0
}

# Centralized Dimension Mapping
DIMENSION_MAPPING = {
    "COMPLETENESS": {"MISSING_VALUE", "BLANK_VALUE"},
    "VALIDITY": {"INVALID_EMAIL", "INVALID_DATE", "INVALID_NUMERIC", "INVALID_CATEGORY", "OUT_OF_RANGE"},
    "CONSISTENCY": {"CONSISTENCY_VIOLATION", "comparison"},
    "UNIQUENESS": {"DUPLICATE_ROW", "DUPLICATE_ID", "uniqueness"},
    "RULE_COMPLIANCE": {"required_column", "range", "allowed_values", "referential_integrity"}
}

# Multiplier to convert Defect Rate to a 100-point scale drop
PENALTY_MULTIPLIER = 100.0

def _get_dimension_for_issue(issue: StandardizedIssue) -> str:
    for dim, types in DIMENSION_MAPPING.items():
        if issue.issue_type in types:
            return dim
    
    # Fallbacks for unknown types
    if issue.source == "business_rule":
        return "RULE_COMPLIANCE"
    return "VALIDITY"

def get_grade_and_status(score: float) -> tuple[str, str]:
    if score >= 90.0: return "Excellent", "READY"
    if score >= 75.0: return "Good", "READY_WITH_WARNINGS"
    if score >= 60.0: return "Needs Improvement", "REVIEW_REQUIRED"
    if score >= 40.0: return "Poor", "NOT_READY"
    return "Critical", "NOT_READY"

def calculate_readiness_score(
    df: pd.DataFrame, 
    column_profiles: list, 
    issues: List[StandardizedIssue], 
    weights: Dict[str, float] = None,
    rules_configured: bool = True
) -> ReadinessScore:
    
    if weights is None:
        weights = DEFAULT_WEIGHTS
        
    if not all(k in weights for k in DEFAULT_WEIGHTS.keys()):
        raise ValueError("Weights dictionary must contain all 5 dimensions.")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError("Weights must sum to 1.0.")
        
    total_rows = len(df)
    total_columns = len(df.columns)
    
    # Separate issues into dimensions and track row-level vs dataset-level
    # Structure: dim -> {'row': [(issue, sev)], 'dataset': [(issue, sev)]}
    dim_issues = {dim: {'row': [], 'dataset': []} for dim in DEFAULT_WEIGHTS.keys()}
    
    for issue in issues:
        severity = issue.severity if issue.severity in SEVERITY_PENALTY else "MEDIUM"
        dim = _get_dimension_for_issue(issue)
        
        if issue.row_index is not None:
            dim_issues[dim]['row'].append((issue, severity))
        else:
            dim_issues[dim]['dataset'].append((issue, severity))
            
    dim_results = {}
    
    for dim in DEFAULT_WEIGHTS.keys():
        row_list = dim_issues[dim]['row']
        dataset_list = dim_issues[dim]['dataset']
        
        issue_count = len(row_list) + len(dataset_list)
        
        row_penalty = sum(SEVERITY_PENALTY[sev] for _, sev in row_list)
        dataset_penalty = sum(SEVERITY_PENALTY[sev] for _, sev in dataset_list)
        total_penalty = row_penalty + dataset_penalty
        
        if total_rows == 0 or total_columns == 0:
            dim_results[dim] = DimensionResult(
                score=100.0, is_applicable=False, issue_count=0, 
                row_penalty=0.0, dataset_penalty=0.0, defect_rate=0.0,
                reason="Empty dataset", evidence="No data"
            )
            continue
            
        is_applicable = True
        if dim == "RULE_COMPLIANCE" and not rules_configured:
            is_applicable = False
            
        # Defect Rate Calculation
        # Row-level issues are normalized by total rows.
        # Dataset-level issues directly add to the defect rate.
        row_dpr = row_penalty / total_rows if total_rows > 0 else 0.0
        dataset_dpr = dataset_penalty
        defect_rate = row_dpr + dataset_dpr
        
        raw_score = 100.0 - (defect_rate * PENALTY_MULTIPLIER)
        score = max(0.0, min(100.0, raw_score))
        
        if not is_applicable:
            score = 100.0
            reason = f"{dim.title()} is not applicable (no business rules configured)."
        elif issue_count == 0:
            reason = f"Perfect {dim.title()} score. No issues detected."
        else:
            reason = f"{dim.title()} score is {score:.1f} because {issue_count} issues caused a defect rate of {defect_rate:.4f}."
            
        dim_results[dim] = DimensionResult(
            score=float(score), 
            is_applicable=is_applicable, 
            issue_count=issue_count, 
            row_penalty=float(row_penalty),
            dataset_penalty=float(dataset_penalty),
            defect_rate=float(defect_rate),
            reason=reason,
            evidence=f"{len(row_list)} row-level and {len(dataset_list)} dataset-level issues."
        )

    active_weights = sum(weights[dim] for dim, res in dim_results.items() if res.is_applicable)
    weighted_sum = sum(res.score * weights[dim] for dim, res in dim_results.items() if res.is_applicable)
            
    if active_weights > 0:
        overall_score = weighted_sum / active_weights
    else:
        overall_score = 100.0
        
    grade, status = get_grade_and_status(overall_score)
    
    recommendations = []
    if total_rows == 0 or total_columns == 0:
        recommendations.append("Dataset is empty. Provide a valid dataset.")
    else:
        issue_types = Counter(i.issue_type for i in issues)
        for it, count in issue_types.most_common(3):
            rec = next((i.recommendation for i in issues if i.issue_type == it), f"Address {it} issues.")
            rec_str = f"({count} issues) {rec}"
            if rec_str not in recommendations:
                recommendations.append(rec_str)
                
        if not recommendations:
            if not rules_configured:
                recommendations.append("Dataset is technically clean. Consider adding business rules.")
            else:
                recommendations.append("Dataset is clean and ready for analysis.")
        
    return ReadinessScore(
        overall_score=float(overall_score),
        grade=grade,
        status=status,
        dimension_scores={dim: res.score for dim, res in dim_results.items()},
        dimension_results=dim_results,
        weights=weights,
        penalties={dim: res.row_penalty + res.dataset_penalty for dim, res in dim_results.items()},
        issue_counts={dim: res.issue_count for dim, res in dim_results.items()},
        total_rows=total_rows,
        total_columns=total_columns,
        explanation=f"Overall score is {overall_score:.1f}. Evaluated {len(issues)} issues across {total_rows} rows.",
        recommendations=recommendations
    )
