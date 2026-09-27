
import os
import shutil
import pytest
import json
from src.project_export import ProjectExportManager

@pytest.fixture
def manager():
    test_dir = ".dataforge_test/export"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield ProjectExportManager(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_package_creation_and_manifest(manager):
    pkg_dir = manager.generate_package({"config": {"name": "test"}, "raw_data": "id,val\n1,2"})
    assert os.path.exists(os.path.join(pkg_dir, "raw", "data.csv"))
    assert os.path.exists(os.path.join(pkg_dir, "manifest.json"))
    
    with open(os.path.join(pkg_dir, "manifest.json"), "r") as f:
        manifest = json.load(f)
        assert "raw\\data.csv" in manifest or "raw/data.csv" in manifest or "raw"+os.sep+"data.csv" in manifest

def test_hash_verification(manager):
    pkg_dir = manager.generate_package({"config": {"name": "test"}, "raw_data": "id,val\n1,2"})
    assert manager.verify_package(pkg_dir) == True
    
    # Tamper
    with open(os.path.join(pkg_dir, "raw", "data.csv"), "w") as f:
        f.write("tampered")
    assert manager.verify_package(pkg_dir) == False

def test_missing_artifacts_handling(manager):
    pkg_dir = manager.generate_package({"config": {"name": "test"}, "raw_data": "id,val\n1,2"})
    os.remove(os.path.join(pkg_dir, "raw", "data.csv"))
    assert manager.verify_package(pkg_dir) == False

def test_raw_immutability(manager):
    data = "id,val\n1,2"
    pkg_dir = manager.generate_package({"config": {}, "raw_data": data})
    with open(os.path.join(pkg_dir, "raw", "data.csv"), "r") as f:
        read_data = f.read()
    assert read_data == data
