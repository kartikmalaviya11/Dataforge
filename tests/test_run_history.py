
import os
import shutil
import pytest
from src.run_history import RunHistoryManager, RunRecord

@pytest.fixture
def manager():
    test_dir = ".dataforge_test/run_history"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield RunHistoryManager(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_create_and_get_run(manager):
    run_id = manager.create_run()
    run = manager.get_run(run_id)
    assert run is not None
    assert run.run_id == run_id
    assert run.status == "RUNNING"

def test_update_run(manager):
    run_id = manager.create_run()
    manager.update_run(run_id, {"quality_score": 95.5})
    run = manager.get_run(run_id)
    assert run.quality_score == 95.5

def test_complete_run(manager):
    run_id = manager.create_run()
    manager.complete_run(run_id)
    run = manager.get_run(run_id)
    assert run.status == "COMPLETED"
    assert run.completed_at is not None

def test_fail_run(manager):
    run_id = manager.create_run()
    manager.fail_run(run_id)
    run = manager.get_run(run_id)
    assert run.status == "FAILED"
    assert run.completed_at is not None

def test_cancel_run(manager):
    run_id = manager.create_run()
    manager.cancel_run(run_id)
    run = manager.get_run(run_id)
    assert run.status == "CANCELLED"
    assert run.completed_at is not None

def test_immutable_completed(manager):
    run_id = manager.create_run()
    manager.complete_run(run_id)
    with pytest.raises(ValueError):
        manager.update_run(run_id, {"quality_score": 100})

def test_persistence_and_deterministic_ordering(manager):
    id1 = manager.create_run()
    id2 = manager.create_run()
    
    manager2 = RunHistoryManager(manager.persistence_dir)
    runs = manager2.get_all_runs()
    assert len(runs) == 2
    assert [r.run_id for r in runs] == sorted([id1, id2])

def test_isolation():
    m1 = RunHistoryManager(".dataforge_test/m1")
    m2 = RunHistoryManager(".dataforge_test/m2")
    m1.create_run()
    assert len(m1.get_all_runs()) == 1
    assert len(m2.get_all_runs()) == 0
    shutil.rmtree(".dataforge_test/m1")
    shutil.rmtree(".dataforge_test/m2")
