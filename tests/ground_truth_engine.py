import yaml
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

from src.ingestion import load_dataset
from src.profiler import profile_dataset
from src.type_detector import detect_semantic_types
from src.quality_engine import run_quality_checks
from src.rules import RuleEngine
from src.issue_manager import IssueManager

def load_expected_issues(yaml_path: str) -> set[tuple]:
    """
    Loads expected issues from a YAML file.
    Returns a set of tuples: (row_index, column, issue_type)
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        
    expected_set = set()
    for item in data.get('expected_issues', []):
        row = item.get('row_index')
        col = item.get('column')
        itype = item.get('issue_type')
        expected_set.add((row, col, itype))
        
    return expected_set

def run_ground_truth_pipeline(
    dataset_path: str,
    rules_path: Optional[str] = None
) -> set[tuple]:
    """
    Runs the real pipeline (Phase 1-6) on the dataset and returns a set of detected issues.
    Returns a set of tuples: (row_index, column, issue_type)
    """
    # Phase 1: Ingestion
    df, profile = load_dataset(dataset_path)
    
    # Phase 2: Profiling
    column_profiles = profile_dataset(df)
    
    # Phase 3: Semantic Types
    type_results = detect_semantic_types(df, column_profiles)
    
    # Phase 4: Quality Checks
    quality_issues = run_quality_checks(df, column_profiles, type_results)
    
    # Phase 5: Business Rules
    rule_issues = []
    if rules_path:
        engine = RuleEngine.from_yaml(rules_path)
        rule_issues = engine.run(df)
        
    # Phase 6: Issue Management
    manager = IssueManager()
    all_issues = manager.consolidate(quality_issues + rule_issues)
    
    detected_set = set()
    for issue in all_issues:
        detected_set.add((issue.row_index, issue.column, issue.issue_type))
        
    return detected_set

def calculate_metrics(expected: set[tuple], detected: set[tuple]) -> Dict[str, Any]:
    """
    Calculates TP, FP, FN, Precision, Recall, and F1 for each issue type and overall.
    """
    # Find all unique issue types across expected and detected
    all_types = {t[2] for t in expected} | {t[2] for t in detected}
    
    results = {}
    
    # Per-type metrics
    for itype in all_types:
        expected_type = {t for t in expected if t[2] == itype}
        detected_type = {t for t in detected if t[2] == itype}
        
        tp = len(expected_type & detected_type)
        fp = len(detected_type - expected_type)
        fn = len(expected_type - detected_type)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        results[itype] = {
            'TP': tp,
            'FP': fp,
            'FN': fn,
            'Precision': precision,
            'Recall': recall,
            'F1': f1,
            'expected_set': expected_type,
            'detected_set': detected_type
        }
        
    # Overall metrics
    tp = len(expected & detected)
    fp = len(detected - expected)
    fn = len(expected - detected)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    results['OVERALL'] = {
        'TP': tp,
        'FP': fp,
        'FN': fn,
        'Precision': precision,
        'Recall': recall,
        'F1': f1,
        'expected_set': expected,
        'detected_set': detected
    }
    
    return results
