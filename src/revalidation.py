from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import hashlib

from .issue_manager import StandardizedIssue, IssueManager
from .profiler import profile_dataset, ColumnProfile
from .type_detector import detect_semantic_types, TypeDetectionResult
from .quality_engine import run_quality_checks
from .rules import load_rules, RuleEngine
from .scoring import calculate_readiness_score, ReadinessScore

def _compute_issue_signature(issue: StandardizedIssue) -> str:
    """
    Compute a stable signature that does NOT depend strictly on row_index alone.
    If we rely only on row_index, row shifts might cause false mismatches.
    We include column, issue_type, rule_name, and actual_value.
    Identical issues will be disambiguated by a counter during snapshot creation.
    """
    components = [
        str(issue.source),
        str(issue.issue_type),
        str(issue.rule_or_check_name),
        str(issue.column) if issue.column is not None else "DATASET",
        str(issue.actual_value) if issue.actual_value is not None else "NO_VAL",
    ]
    raw = "|".join(components)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

@dataclass
class ValidationSnapshot:
    issues: List[StandardizedIssue]
    readiness: ReadinessScore
    col_profiles: List[ColumnProfile]
    type_results: List[TypeDetectionResult]
    
    issue_signatures: Dict[str, StandardizedIssue] = field(init=False)
    
    def __post_init__(self):
        self.issue_signatures = {}
        counts: Dict[str, int] = {}
        for issue in self.issues:
            base_sig = _compute_issue_signature(issue)
            if base_sig not in self.issue_signatures:
                sig = base_sig
                counts[base_sig] = 1
            else:
                idx = counts.get(base_sig, 1)
                sig = f"{base_sig}_{idx}"
                while sig in self.issue_signatures:
                    idx += 1
                    sig = f"{base_sig}_{idx}"
                counts[base_sig] = idx + 1
            self.issue_signatures[sig] = issue

@dataclass
class ComparisonResult:
    before_issue_count: int
    after_issue_count: int
    resolved_issue_count: int
    remaining_issue_count: int
    new_issue_count: int
    
    before_readiness: float
    after_readiness: float
    readiness_change: float
    
    resolved_issues: List[StandardizedIssue]
    remaining_issues: List[StandardizedIssue]
    new_issues: List[StandardizedIssue]

class RevalidationEngine:
    def __init__(self, rules_yaml_path: Optional[str] = None):
        self.rules_yaml_path = rules_yaml_path
        self.issue_manager = IssueManager()
        
    def run_validation(self, df: pd.DataFrame) -> ValidationSnapshot:
        col_profiles = profile_dataset(df)
        type_results = detect_semantic_types(df, col_profiles)
        quality_issues = run_quality_checks(df, col_profiles, type_results)
        
        rule_issues = []
        rules_configured = False
        if self.rules_yaml_path:
            import os
            from pathlib import Path
            if Path(self.rules_yaml_path).exists():
                rules = load_rules(Path(self.rules_yaml_path))
                engine = RuleEngine(rules)
                rule_issues = engine.run(df)
                rules_configured = True
                
        all_issues = self.issue_manager.consolidate(quality_issues + rule_issues)
        readiness = calculate_readiness_score(df, col_profiles, all_issues, rules_configured=rules_configured)
        
        return ValidationSnapshot(
            issues=all_issues,
            readiness=readiness,
            col_profiles=col_profiles,
            type_results=type_results
        )
        
    def compare(self, before: ValidationSnapshot, after: ValidationSnapshot) -> ComparisonResult:
        before_sigs = set(before.issue_signatures.keys())
        after_sigs = set(after.issue_signatures.keys())
        
        resolved_sigs = before_sigs - after_sigs
        remaining_sigs = before_sigs & after_sigs
        new_sigs = after_sigs - before_sigs
        
        resolved = [before.issue_signatures[s] for s in resolved_sigs]
        remaining = [before.issue_signatures[s] for s in remaining_sigs]
        new_iss = [after.issue_signatures[s] for s in new_sigs]
        
        before_score = before.readiness.overall_score
        after_score = after.readiness.overall_score
        
        return ComparisonResult(
            before_issue_count=len(before.issues),
            after_issue_count=len(after.issues),
            resolved_issue_count=len(resolved),
            remaining_issue_count=len(remaining),
            new_issue_count=len(new_iss),
            before_readiness=before_score,
            after_readiness=after_score,
            readiness_change=after_score - before_score,
            resolved_issues=resolved,
            remaining_issues=remaining,
            new_issues=new_iss
        )
