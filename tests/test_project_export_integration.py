import pytest
import os
import shutil
import hashlib
import json
import zipfile
from src.workspace import ProjectWorkspace, TableRegistryEntry, TableStatus
from src.project_export import ProjectExportManager

@pytest.fixture
def workspace():
    ws_dir = ".dataforge_test_export"
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)
    ws = ProjectWorkspace(ws_dir)
    
    # Create real metadata files in .dataforge
    df_dir = os.path.join(ws_dir, ".dataforge")
    os.makedirs(df_dir, exist_ok=True)
    
    with open(os.path.join(df_dir, "dataset_versions.json"), "w") as f:
        json.dump([{"version_id": "v1", "table_name": "test_table", "row_count": 2, "column_count": 2}], f)
    with open(os.path.join(df_dir, "run_history.json"), "w") as f:
        json.dump([{"run_id": "r1", "workflow_name": "DATA_PROFILING", "status": "COMPLETED"}], f)
    with open(os.path.join(df_dir, "kpi_snapshots.json"), "w") as f:
        json.dump([{"snapshot_id": "s1", "kpi_id": "k1", "value": 15.0, "dataset_version_id": "v1"}], f)
    with open(os.path.join(df_dir, "lineage.json"), "w") as f:
        json.dump({"nodes": [], "edges": []}, f)
    with open(os.path.join(df_dir, "kpis.json"), "w") as f:
        json.dump([{"kpi_id": "k1", "kpi_name": "Avg Value"}], f)
    with open(os.path.join(df_dir, "findings.json"), "w") as f:
        json.dump({"findings": [{"finding_id": "fnd_01", "problem": "Revenue drop in Q3"}]}, f)
    with open(os.path.join(df_dir, "model_specification.json"), "w") as f:
        json.dump({"model_name": "SalesModel", "tables": ["test_table"]}, f)
        
    csv_content = "id,val\n1,10\n2,20\n"
    csv_path = os.path.join(ws_dir, "data.csv")
    with open(csv_path, "w") as f:
        f.write(csv_content)
        
    ws.registry["test_table"] = TableRegistryEntry(
        table_name="test_table",
        file_name="data.csv",
        file_path=csv_path,
        file_type="csv",
        row_count=2,
        column_count=2,
        status=TableStatus.LOADED.value,
        last_modified=0
    )
    ws.save()
    
    yield ws
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)

def test_real_project_export(workspace):
    csv_path = os.path.join(workspace.project_root, "data.csv")
    with open(csv_path, "rb") as f:
        raw_hash_before = hashlib.sha256(f.read()).hexdigest()
        
    em = ProjectExportManager(os.path.join(workspace.project_root, "export"))
    zip_path = em.generate_package(workspace=workspace)
    assert os.path.exists(zip_path)

    # 1. Raw source on disk remains untouched
    with open(csv_path, "rb") as f:
        raw_hash_after = hashlib.sha256(f.read()).hexdigest()
    assert raw_hash_before == raw_hash_after

    # 2. Inspect ZIP member names and contents programmatically
    with zipfile.ZipFile(zip_path, 'r') as z:
        names = z.namelist()
        print("ZIP Member Names:", names)
        
        # Core metadata files
        assert "project_config.json" in names
        assert "manifest.json" in names
        assert "metadata/dataset_versions.json" in names
        assert "metadata/run_history.json" in names
        assert "metadata/kpi_snapshots.json" in names
        assert "metadata/lineage.json" in names
        assert "metadata/kpis.json" in names
        assert "metadata/findings.json" in names
        assert "metadata/model_specification.json" in names
        assert "findings/findings.json" in names
        assert "dashboard/model_specification.json" in names
        assert "raw/data.csv" in names

        # Content verification: raw data inside zip matches original exactly
        raw_in_zip = z.read("raw/data.csv")
        with open(csv_path, "rb") as f:
            assert raw_in_zip == f.read()

        # Content verification: dataset versions
        versions = json.loads(z.read("metadata/dataset_versions.json").decode("utf-8"))
        assert len(versions) == 1
        assert versions[0]["version_id"] == "v1"

        # Content verification: kpi snapshots
        snaps = json.loads(z.read("metadata/kpi_snapshots.json").decode("utf-8"))
        assert len(snaps) == 1
        assert snaps[0]["snapshot_id"] == "s1"
        assert snaps[0]["value"] == 15.0

        # Content verification: run history
        runs = json.loads(z.read("metadata/run_history.json").decode("utf-8"))
        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"

        # Content verification: findings
        fnd = json.loads(z.read("findings/findings.json").decode("utf-8"))
        assert "findings" in fnd
        assert fnd["findings"][0]["finding_id"] == "fnd_01"

        # Content verification: model specification
        model_spec = json.loads(z.read("dashboard/model_specification.json").decode("utf-8"))
        assert model_spec["model_name"] == "SalesModel"

    # 3. Verify extracted package integrity with manifest
    pkg_dir = zip_path.replace(".zip", "_extracted")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(pkg_dir)
    assert em.verify_package(pkg_dir) is True

def test_export_invalid_workspace():
    em = ProjectExportManager(".dataforge_test_export_inv")
    with pytest.raises(ValueError, match="Workspace must be provided"):
        em.generate_package(workspace=None)

    with pytest.raises(ValueError, match="Workspace must be provided"):
        em.generate_package(workspace="not_a_workspace")

    class FakeWS:
        pass
    with pytest.raises(ValueError, match="Workspace must be provided"):
        em.generate_package(workspace=FakeWS())

def test_export_empty_project():
    ws_dir = ".dataforge_test_export_empty"
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)
    ws = ProjectWorkspace(ws_dir)
    ws.save()
    
    em = ProjectExportManager(os.path.join(ws.project_root, "export"))
    zip_path = em.generate_package(workspace=ws)
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        names = z.namelist()
        assert "project_config.json" in names
        assert "manifest.json" in names

    pkg_dir = zip_path.replace(".zip", "_extracted")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(pkg_dir)
    assert em.verify_package(pkg_dir) is True
    
    shutil.rmtree(ws_dir)
