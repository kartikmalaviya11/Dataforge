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
