import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import json
from src.workspace import ProjectWorkspace
from src.run_history import RunHistoryManager
from src.dataset_versioning import DatasetVersioningManager

def test_backend_integration_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = ProjectWorkspace(tmpdir)
        rhm = RunHistoryManager(tmpdir)
        dvm = DatasetVersioningManager(tmpdir)
        
        # 1. Empty history
        assert len(rhm.get_all_runs()) == 0
        
        # 2. Simulate Scan
        df = pd.DataFrame({"col1": [1, np.nan, 3], "col2": ["a", "b", "c"]})
        
        run_id = rhm.create_run()
        rhm.update_run(run_id, {"cleaning_summary": {"operation": "Data Quality Scan"}})
        
        source_hash = dvm.compute_df_hash(df)
        schema_hash = dvm.compute_hash(str(list(df.columns)))
        vid = dvm.create_version("RAW", source_hash, len(df), 1, schema_hash, None, {}, column_count=len(df.columns))
        
        rhm.update_run(run_id, {"dataset_version_id": vid})
        rhm.complete_run(run_id)
        
        # Verify
        run_obj = rhm.get_run(run_id)
        assert run_obj.status == "COMPLETED"
        assert run_obj.dataset_version_id == vid
        
        versions = dvm.get_all_versions()
        assert len(versions) == 1
        assert versions[0].version_type == "RAW"
        assert versions[0].table_count == 1
        assert versions[0].column_count == 2
        
        # 3. Simulate failed scan
        run_id_fail = rhm.create_run()
        rhm.fail_run(run_id_fail)
        
        run_fail_obj = rhm.get_run(run_id_fail)
        assert run_fail_obj.status == "FAILED"
        assert run_fail_obj.dataset_version_id is None
        
        # 4. Immutability & Content Hash
        df_mut = df.copy()
        
        # Simulate Auto Repair
        df_clean = df_mut.fillna(0)
        
        # Original shouldn't be modified (verified by hash check)
        assert dvm.compute_df_hash(df) == source_hash
        
        # New hash should be different
        source_hash_clean = dvm.compute_df_hash(df_clean)
        assert source_hash_clean != source_hash
        schema_hash_clean = dvm.compute_hash(str(list(df_clean.columns)))
        
        # Same schema, different content
        assert schema_hash_clean == schema_hash
        
        new_vid = dvm.create_version("CLEANED", source_hash_clean, len(df_clean), 1, schema_hash, vid, {"operation": "Auto Repair"}, column_count=len(df_clean.columns))
        run_id_clean = rhm.create_run()
        rhm.update_run(run_id_clean, {"dataset_version_id": new_vid})
        rhm.complete_run(run_id_clean)
        
        versions = dvm.get_all_versions()
        assert len(versions) == 2
        
        v_raw = dvm.get_version(vid)
        v_clean = dvm.get_version(new_vid)
        assert v_clean.parent_version_id == v_raw.version_id
        assert v_clean.change_summary["operation"] == "Auto Repair"
        assert v_clean.table_count == 1
        assert v_clean.column_count == 2

def test_identical_hash_no_duplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        dvm = DatasetVersioningManager(tmpdir)
        df = pd.DataFrame({"A": [1, 2]})
        
        h1 = dvm.compute_df_hash(df)
        v1 = dvm.create_version("RAW", h1, len(df), 1, "s1", None, {}, column_count=len(df.columns))
        
        h2 = dvm.compute_df_hash(df)
        assert h1 == h2
        
        # Simulate check in UI
        vid = None
        for v in dvm.get_all_versions():
            if v.version_type == "RAW" and v.source_hash == h2:
                vid = v.version_id
                break
        
        assert vid == v1
        
        # Now change content slightly
        df.iloc[0, 0] = 99
        h3 = dvm.compute_df_hash(df)
        assert h3 != h1

def test_workspace_isolation():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        rhm1 = RunHistoryManager(d1)
        rhm2 = RunHistoryManager(d2)
        dvm1 = DatasetVersioningManager(d1)
        dvm2 = DatasetVersioningManager(d2)
        
        rhm1.create_run()
        dvm1.create_version("RAW", "h1", 10, 5, "s1", column_count=20)
        
        assert len(rhm1.get_all_runs()) == 1
        assert len(dvm1.get_all_versions()) == 1
        assert dvm1.get_all_versions()[0].table_count == 5
        assert dvm1.get_all_versions()[0].column_count == 20
        
        assert len(rhm2.get_all_runs()) == 0
        assert len(dvm2.get_all_versions()) == 0

def test_legacy_table_count_compatibility():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake legacy JSON with table_count and NO column_count
        legacy_data = {
            "test_legacy_id": {
                "version_id": "test_legacy_id",
                "parent_version_id": None,
                "version_type": "RAW",
                "created_at": "2026-10-01T00:00:00Z",
                "source_hash": "testhash",
                "row_count": 50,
                "table_count": 10,
                "schema_hash": "schema123",
                "change_summary": {},
                "status": "ACTIVE"
                # deliberately omitting column_count
            }
        }
        
        os.makedirs(os.path.join(tmpdir, "dataset_versioning"), exist_ok=True)
        with open(os.path.join(tmpdir, "dataset_versioning", "versions.json"), "w") as f:
            json.dump(legacy_data, f)
            
        dvm = DatasetVersioningManager(os.path.join(tmpdir, "dataset_versioning"))
        v = dvm.get_version("test_legacy_id")
        
        # It should load successfully, retaining table_count=10 and default column_count=None
        assert v.table_count == 10
        assert v.column_count is None
