
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
