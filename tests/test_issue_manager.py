import pytest
from src.issue_manager import IssueManager, StandardizedIssue, _generate_issue_id
from src.quality_engine import QualityIssue
from src.rules import RuleViolation

def test_generate_issue_id_deterministic():
    id1 = _generate_issue_id("quality_check", "MISSING_VALUE", "missing_value_check", 5, "Age")
    id2 = _generate_issue_id("quality_check", "MISSING_VALUE", "missing_value_check", 5, "Age")
    assert id1 == id2
    
def test_generate_issue_id_unique():
    id1 = _generate_issue_id("quality_check", "MISSING_VALUE", "missing_value_check", 5, "Age")
    id2 = _generate_issue_id("quality_check", "MISSING_VALUE", "missing_value_check", 6, "Age")
    id3 = _generate_issue_id("business_rule", "MISSING_VALUE", "missing_value_check", 5, "Age")
    assert id1 != id2
    assert id1 != id3

def test_consolidate_quality_issue():
    manager = IssueManager()
    qi = QualityIssue(
        row_index=10,
        column="Salary",
        issue_type="INVALID_NUMERIC",
        check_name="numeric_check",
        actual_value="10k",
        expected_condition="Numeric format",
        description="Not a number"
    )
    
    results = manager.consolidate([qi])
    assert len(results) == 1
    issue = results[0]
    assert isinstance(issue, StandardizedIssue)
    assert issue.source == "quality_check"
    assert issue.issue_type == "INVALID_NUMERIC"
    assert issue.severity == "HIGH"
    assert issue.row_index == 10
    assert issue.column == "Salary"
    assert issue.actual_value == "10k"
    assert issue.message == "Not a number"
    assert issue.expected_condition == "Numeric format"
    assert "numeric" in issue.recommendation.lower()

def test_consolidate_rule_violation():
    manager = IssueManager()
    rv = RuleViolation(
        rule_name="salary_minimum",
        rule_type="range",
        row_index="row_alpha",
        column="Salary",
        actual_value=100,
        expected_condition=">= 1000",
        severity="CRITICAL",
        message="Too low"
    )
    
    results = manager.consolidate([rv])
    assert len(results) == 1
    issue = results[0]
    assert issue.source == "business_rule"
    assert issue.issue_type == "range"
    assert issue.rule_or_check_name == "salary_minimum"
    assert issue.row_index == "row_alpha"
    assert issue.severity == "CRITICAL"

def test_consolidate_mixed():
    manager = IssueManager()
    qi = QualityIssue(row_index=None, column=None, issue_type="DUPLICATE_ROW", check_name="dup", description="dup row")
    rv = RuleViolation(rule_name="req", rule_type="required_column", row_index=None, column="ID", expected_condition="exists")
    
    results = manager.consolidate([qi, rv])
    assert len(results) == 2
    assert results[0].source == "quality_check"
    assert results[1].source == "business_rule"

def test_empty_input_handled_safely():
    manager = IssueManager()
    results = manager.consolidate([])
    assert len(results) == 0

def test_unknown_type_ignored():
    manager = IssueManager()
    results = manager.consolidate(["Not An Issue Object"])
    assert len(results) == 0
