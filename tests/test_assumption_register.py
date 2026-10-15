import os
import shutil
import pytest
from src.assumption_register import AssumptionRegisterManager

@pytest.fixture
def manager(tmp_path):
    test_dir = str(tmp_path / "assumptions")
    os.makedirs(test_dir, exist_ok=True)
    yield AssumptionRegisterManager(test_dir)

def test_create_and_update(manager):
    a_id = manager.create("T", "D", "R", "High", ["sql"])
    assert manager.assumptions[a_id].status == "ACTIVE"
    manager.update(a_id, title="T2")
    assert manager.assumptions[a_id].title == "T2"

def test_review(manager):
    a_id = manager.create("T", "D", "R", "High", ["sql"])
    manager.review(a_id)
    assert manager.assumptions[a_id].status == "REVIEWED"

def test_retire(manager):
    a_id = manager.create("T", "D", "R", "High", ["sql"])
    manager.retire(a_id)
    assert manager.assumptions[a_id].status == "RETIRED"

def test_persistence_and_stable_serialization(manager):
    manager.create("T", "D", "R", "High", ["sql"])
    m2 = AssumptionRegisterManager(manager.persistence_dir)
    assert len(m2.get_all()) == 1

def test_isolation(tmp_path):
    d1 = str(tmp_path / "a1")
    d2 = str(tmp_path / "a2")
    m1 = AssumptionRegisterManager(d1)
    m2 = AssumptionRegisterManager(d2)
    m1.create("T", "D", "R", "High", [])
    assert len(m1.get_all()) == 1
    assert len(m2.get_all()) == 0

def test_create_validation_empty_title(manager):
    with pytest.raises(ValueError, match="Assumption title cannot be empty"):
        manager.create("", "Valid Description", "Reason", "LOW", [])
    with pytest.raises(ValueError, match="Assumption title cannot be empty"):
        manager.create("   ", "Valid Description", "Reason", "LOW", [])
    assert len(manager.get_all()) == 0

def test_create_validation_empty_description(manager):
    with pytest.raises(ValueError, match="Assumption description cannot be empty"):
        manager.create("Valid Title", "", "Reason", "LOW", [])
    with pytest.raises(ValueError, match="Assumption description cannot be empty"):
        manager.create("Valid Title", "   ", "Reason", "LOW", [])
    assert len(manager.get_all()) == 0

def test_create_full_persistence_and_fields(manager):
    a_id = manager.create(
        title="Currency in USD",
        description="All transaction amounts normalized to USD at time of ingestion",
        reason="Finance team policy",
        risk="HIGH",
        used_in=["sales", "revenue_kpi"]
    )
    assert a_id is not None
    assert len(manager.get_all()) == 1

    # Reload from disk in a fresh manager instance
    reloaded = AssumptionRegisterManager(manager.persistence_dir)
    assump = reloaded.assumptions.get(a_id)
    assert assump is not None
    assert assump.title == "Currency in USD"
    assert assump.description == "All transaction amounts normalized to USD at time of ingestion"
    assert assump.reason == "Finance team policy"
    assert assump.risk == "HIGH"
    assert assump.used_in == ["sales", "revenue_kpi"]
    assert assump.status == "ACTIVE"
