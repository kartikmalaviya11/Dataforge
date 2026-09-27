
import os
import shutil
import pytest
from src.historical_readiness import HistoricalReadinessManager
import time

@pytest.fixture
def manager():
    test_dir = ".dataforge_test/historical_readiness"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield HistoricalReadinessManager(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_snapshot_creation_and_preservation(manager):
    r_id = manager.create_snapshot("run_1", "dv_1", 95.0, 90.0, "READY")
    recs = manager.get_all()
    assert len(recs) == 1
    assert recs[0].readiness_id == r_id
    assert recs[0].quality_score == 95.0

def test_chronological_ordering(manager):
    manager.create_snapshot("run_1", "dv_1", 95.0, 90.0, "READY")
    time.sleep(0.01)
    manager.create_snapshot("run_2", "dv_2", 96.0, 91.0, "READY")
    recs = manager.get_all()
    assert recs[0].run_id == "run_1"
    assert recs[1].run_id == "run_2"
    assert recs[0].recorded_at < recs[1].recorded_at

def test_persistence(manager):
    manager.create_snapshot("run_1", "dv_1", 95.0, 90.0, "READY")
    m2 = HistoricalReadinessManager(manager.persistence_dir)
    assert len(m2.get_all()) == 1

def test_isolation():
    m1 = HistoricalReadinessManager(".dataforge_test/h1")
    m2 = HistoricalReadinessManager(".dataforge_test/h2")
    m1.create_snapshot("run_1", "dv_1", 95.0, 90.0, "READY")
    assert len(m1.get_all()) == 1
    assert len(m2.get_all()) == 0
    shutil.rmtree(".dataforge_test/h1")
    shutil.rmtree(".dataforge_test/h2")
