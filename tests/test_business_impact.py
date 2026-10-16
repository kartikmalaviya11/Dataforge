
import os
import shutil
import pytest
from src.business_impact import BusinessImpactManager

@pytest.fixture
def manager():
    test_dir = ".dataforge_test/business_impact"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield BusinessImpactManager(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_issue_kpi_link(manager):
    i_id = manager.create(100, "Revenue", "Low rev", "missing rows")
    assert manager.impacts[i_id].affected_kpi == "Revenue"

def test_unresolved_kpi(manager):
    i_id = manager.create(100, "Revenue", "Low rev", "missing rows")
    manager.update_status(i_id, "UNRESOLVED")
    assert manager.impacts[i_id].status == "UNRESOLVED"

def test_potential_observed_impact(manager):
    i_id = manager.create(100, "Revenue", "Low rev", "missing rows")
    assert manager.impacts[i_id].status == "POTENTIAL_IMPACT"
    manager.update_status(i_id, "OBSERVED_IMPACT")
    assert manager.impacts[i_id].status == "OBSERVED_IMPACT"

def test_persistence_and_stable_ids(manager):
    i_id = manager.create(100, "Revenue", "Low rev", "missing rows")
    m2 = BusinessImpactManager(manager.persistence_dir)
    assert len(m2.get_all()) == 1
    assert m2.get_all()[0].issue_id == i_id

def test_register_impact_with_standardized_issue_and_kpi_recommendation(tmp_path):
    from src.business_impact import BusinessImpact
    from src.issue_manager import StandardizedIssue
    from src.kpi_engine import KPIRecommendation

    issue = StandardizedIssue(
        issue_id="ISSUE_123",
        source="customers",
        issue_type="BLANK_VALUE",
        rule_or_check_name="not_blank",
        row_index=4,
        column="email",
        actual_value=None,
        expected_condition="non-empty string",
        severity="MEDIUM",
        message="Email is blank",
        recommendation="impute_or_review"
    )

    kpi = KPIRecommendation(
        kpi_name="Customer Churn Rate",
        category="Ratio",
        priority="HIGH",
        status="AVAILABLE",
        required_columns=["customer_id", "email"],
        available_columns=["customer_id", "email"],
        calculation_logic="COUNT(churned) / COUNT(customer_id)",
        explanation="Calculates churn"
    )

    class MockWorkspace:
        project_root = tmp_path

    bim = BusinessImpactManager(MockWorkspace())
    assert os.path.exists(os.path.join(tmp_path, ".dataforge", "business_impact"))

    impact = BusinessImpact(
        issue_id=issue.issue_id,
        affected_records=1,
        affected_kpi=kpi.kpi_name,
        business_impact_description=f"Missing {issue.column} impacts {kpi.kpi_name}",
        evidence=f"Detected blank value in {issue.source}.{issue.column}",
        status="POTENTIAL_IMPACT",
        created_at="2026-10-15T00:00:00Z"
    )

    registered_id = bim.register_impact(impact)
    assert registered_id == "ISSUE_123"

    # Reload from disk and verify
    bim_reloaded = BusinessImpactManager(MockWorkspace())
    reloaded_impacts = bim_reloaded.get_all()
    assert len(reloaded_impacts) == 1
    assert reloaded_impacts[0].issue_id == "ISSUE_123"
    assert reloaded_impacts[0].affected_kpi == "Customer Churn Rate"
    assert reloaded_impacts[0].status == "POTENTIAL_IMPACT"
