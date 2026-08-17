import pytest
import pandas as pd
from src.scoring import calculate_readiness_score, DEFAULT_WEIGHTS, get_grade_and_status, _get_dimension_for_issue
from src.issue_manager import StandardizedIssue

def create_issue(issue_type: str, severity: str = "MEDIUM", row_index=0, source="quality_check"):
    return StandardizedIssue(
        issue_id="test_id",
        source=source,
        issue_type=issue_type,
        rule_or_check_name="test_rule",
        row_index=row_index,
        column="col1",
        actual_value=None,
        expected_condition="",
        severity=severity,
        message="Test issue",
        recommendation="Fix it"
    )

def test_dimension_mapping():
    assert _get_dimension_for_issue(create_issue("MISSING_VALUE")) == "COMPLETENESS"
    assert _get_dimension_for_issue(create_issue("INVALID_EMAIL")) == "VALIDITY"
    assert _get_dimension_for_issue(create_issue("CONSISTENCY_VIOLATION")) == "CONSISTENCY"
    assert _get_dimension_for_issue(create_issue("comparison")) == "CONSISTENCY"
    assert _get_dimension_for_issue(create_issue("DUPLICATE_ROW")) == "UNIQUENESS"
    assert _get_dimension_for_issue(create_issue("range")) == "RULE_COMPLIANCE"
    # Fallbacks
    assert _get_dimension_for_issue(create_issue("UNKNOWN", source="business_rule")) == "RULE_COMPLIANCE"
    assert _get_dimension_for_issue(create_issue("UNKNOWN", source="quality_check")) == "VALIDITY"

def test_perfect_dataset():
    df = pd.DataFrame({'col1': [1, 2, 3]})
    score = calculate_readiness_score(df, [], [], rules_configured=True)
    assert score.overall_score == 100.0
    assert score.grade == "Excellent"
    assert "Perfect" in score.dimension_results["COMPLETENESS"].reason

def test_row_level_penalty_scaling():
    # 1000 rows. 100 MISSING_VALUE (LOW=0.1)
    df = pd.DataFrame({'col1': range(1000)})
    issues = [create_issue("MISSING_VALUE", "LOW", row_index=i) for i in range(100)]
    score = calculate_readiness_score(df, [], issues)
    # Row penalty = 100 * 0.1 = 10.0
    # DPR = 10.0 / 1000 = 0.01
    # Score drop = 0.01 * 100 = 1.0
    assert score.dimension_scores["COMPLETENESS"] == 99.0

def test_dataset_level_penalty():
    # 1,000,000 rows, but 1 dataset-level issue (required_column missing) with CRITICAL (5.0)
    df = pd.DataFrame({'col1': range(100000)}) 
    issue = create_issue("required_column", "CRITICAL", row_index=None, source="business_rule")
    score = calculate_readiness_score(df, [], [issue])
    # Dataset penalty = 5.0
    # DPR = 5.0
    # Score drop = 5.0 * 100 = 500 -> Clamped to 0
    assert score.dimension_scores["RULE_COMPLIANCE"] == 0.0

def test_dataset_size_does_not_dilute_column_issue():
    # Dataset with 10 rows. 1 column has 10 MISSING (100% missing).
    df1 = pd.DataFrame({'col1': range(10)})
    issues1 = [create_issue("MISSING_VALUE", "LOW", row_index=i) for i in range(10)]
    score1 = calculate_readiness_score(df1, [], issues1)
    # DPR = (10 * 0.1) / 10 = 0.1. Drop = 10. Completeness = 90.0
    
    # Dataset with 1000 rows. 1 column has 1000 MISSING (100% missing).
    df2 = pd.DataFrame({'col1': range(1000)})
    issues2 = [create_issue("MISSING_VALUE", "LOW", row_index=i) for i in range(1000)]
    score2 = calculate_readiness_score(df2, [], issues2)
    # DPR = (1000 * 0.1) / 1000 = 0.1. Drop = 10. Completeness = 90.0
    
    assert score1.dimension_scores["COMPLETENESS"] == 90.0
    assert score2.dimension_scores["COMPLETENESS"] == 90.0

def test_invalid_weights_rejected():
    df = pd.DataFrame({'col1': [1, 2]})
    with pytest.raises(ValueError, match="sum to 1.0"):
        calculate_readiness_score(df, [], [], weights={"COMPLETENESS": 0.5, "VALIDITY": 0.5, "CONSISTENCY": 0.5, "UNIQUENESS": 0.0, "RULE_COMPLIANCE": 0.0})
    with pytest.raises(ValueError, match="contain all 5 dimensions"):
        calculate_readiness_score(df, [], [], weights={"COMPLETENESS": 1.0})

def test_not_applicable_dimension():
    df = pd.DataFrame({'col1': [1, 2]})
    score = calculate_readiness_score(df, [], [], rules_configured=False)
    assert not score.dimension_results["RULE_COMPLIANCE"].is_applicable
    assert "not applicable" in score.dimension_results["RULE_COMPLIANCE"].reason

def test_empty_dataframe():
    df = pd.DataFrame()
    score = calculate_readiness_score(df, [], [])
    assert score.overall_score == 100.0
    assert not score.dimension_results["COMPLETENESS"].is_applicable

def test_all_invalid_clamped():
    df = pd.DataFrame({'col1': [1, 2]})
    issues = [create_issue("INVALID_EMAIL", "CRITICAL") for _ in range(10)]
    score = calculate_readiness_score(df, [], issues)
    assert score.dimension_scores["VALIDITY"] == 0.0
    assert score.overall_score >= 0.0

def test_grade_boundaries():
    assert get_grade_and_status(95.0)[0] == "Excellent"
    assert get_grade_and_status(80.0)[0] == "Good"
    assert get_grade_and_status(65.0)[0] == "Needs Improvement"
    assert get_grade_and_status(50.0)[0] == "Poor"
    assert get_grade_and_status(10.0)[0] == "Critical"

def test_unknown_severity():
    df = pd.DataFrame({'col1': [1, 2, 3, 4]})
    issue = create_issue("INVALID_EMAIL", "SUPER_BAD", row_index=0)
    score = calculate_readiness_score(df, [], [issue])
    # Fallback MEDIUM = 0.5. Total rows = 4. DPR = 0.5 / 4 = 0.125. Drop = 12.5. Score = 87.5
    assert score.dimension_scores["VALIDITY"] == 87.5
