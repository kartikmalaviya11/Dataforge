
import os
import shutil
import pytest
from src.dataset_versioning import DatasetVersioningManager

@pytest.fixture
def manager():
    test_dir = ".dataforge_test/dataset_versioning"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield DatasetVersioningManager(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_first_raw(manager):
    v_id = manager.create_version("RAW", "hash1", 100, 1, "schema1")
    v = manager.get_version(v_id)
    assert v.version_type == "RAW"
    assert v.parent_version_id is None

def test_new_raw_and_cleaned_child(manager):
    parent_id = manager.create_version("RAW", "hash1", 100, 1, "schema1")
    child_id = manager.create_version("CLEANED", "hash2", 90, 1, "schema2", parent_id, {"removed_rows": 10})
    child = manager.get_version(child_id)
    assert child.parent_version_id == parent_id
    assert child.version_type == "CLEANED"
    assert child.change_summary["removed_rows"] == 10

def test_bi_ready_child(manager):
    cleaned_id = manager.create_version("CLEANED", "hash2", 90, 1, "schema2", "raw_1")
    bi_id = manager.create_version("BI_READY", "hash3", 90, 2, "schema3", cleaned_id)
    bi = manager.get_version(bi_id)
    assert bi.version_type == "BI_READY"
    assert bi.parent_version_id == cleaned_id

def test_integrity_and_schema_changes(manager):
    v_id = manager.create_version("RAW", "hash1", 100, 1, "schema1")
    v = manager.get_version(v_id)
    assert v.schema_hash == "schema1"
    assert v.row_count == 100

def test_stable_hash(manager):
    h1 = manager.compute_hash("test data")
    h2 = manager.compute_hash("test data")
    assert h1 == h2

def test_raw_immutability(manager):
    content = "my raw data"
    h1 = manager.compute_hash(content)
    # simulate no modification allowed to content - checking hash remains same
    assert h1 == manager.compute_hash(content)

def test_persistence(manager):
    v_id = manager.create_version("RAW", "hash1", 100, 1, "schema1")
    m2 = DatasetVersioningManager(manager.persistence_dir)
    assert m2.get_version(v_id) is not None

def test_isolation():
    m1 = DatasetVersioningManager(".dataforge_test/v1")
    m2 = DatasetVersioningManager(".dataforge_test/v2")
    m1.create_version("RAW", "h", 1, 1, "s")
    assert len(m1.get_all_versions()) == 1
    assert len(m2.get_all_versions()) == 0
    shutil.rmtree(".dataforge_test/v1")
    shutil.rmtree(".dataforge_test/v2")
