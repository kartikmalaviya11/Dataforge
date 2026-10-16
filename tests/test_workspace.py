import pytest
import pandas as pd
from pathlib import Path
import tempfile
import json
import time

from src.workspace import ProjectWorkspace, TableStatus

@pytest.fixture
def workspace_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # 1, 2, 3: Mixed files
        pd.DataFrame({'a': [1,2]}).to_csv(tdp / 'dataset_a.csv', index=False)
        pd.DataFrame({'b': [1,2,3]}).to_excel(tdp / 'dataset_b.xlsx', index=False)
        pd.DataFrame({'c': [1]}).to_csv(tdp / 'dataset_a_v2.csv', index=False) # for collision
        
        # 4: Unsupported
        (tdp / 'notes.txt').write_text("Hello world")
        
        # 8: Corrupt file
        (tdp / 'corrupt.xlsx').write_text("This is not an Excel file\n" * 10)
        
        yield tdp

def test_discovery_and_metadata(workspace_env):
    ws = ProjectWorkspace(workspace_env)
    ws.discover_datasets()
    
    names = list(ws.registry.keys())
    # 6 & 7: Deterministic naming and collision handling
    # dataset_a.csv -> dataset_a
    # dataset_b.xlsx -> dataset_b
    # dataset_a_v2.csv -> dataset_a_v2
    # corrupt.csv -> corrupt
    
    assert "dataset_a" in ws.registry
    assert "dataset_b" in ws.registry
    assert "dataset_a_v2" in ws.registry
    assert "corrupt" in ws.registry
    
    # 4: unsupported ignored
    assert "notes" not in ws.registry
    
    assert len(ws.registry) == 4
    
    # Check initial status is DISCOVERED and metadata is None
    for entry in ws.registry.values():
        assert entry.status == TableStatus.DISCOVERED.value
        assert entry.row_count is None

def test_load_and_metadata(workspace_env):
    ws = ProjectWorkspace(workspace_env)
    ws.discover_datasets()
    
    # 5: Correct row/col metadata after loading
    df, prof = ws.load_table("dataset_a")
    assert len(df) == 2
    assert len(df.columns) == 1
    
    entry = ws.registry["dataset_a"]
    assert entry.status == TableStatus.LOADED.value
    assert entry.row_count == 2
    assert entry.column_count == 1
    
def test_corrupt_file_handling(workspace_env):
    ws = ProjectWorkspace(workspace_env)
    ws.discover_datasets()
    
    # 8: Corrupt/unreadable file gets ERROR status without crashing
    with pytest.raises(Exception):
        ws.load_table("corrupt")
        
    entry = ws.registry["corrupt"]
    assert entry.status == TableStatus.ERROR.value
    assert "corrupt" in ws.registry

def test_save_and_reopen(workspace_env):
    ws = ProjectWorkspace(workspace_env)
    ws.discover_datasets()
    ws.load_table("dataset_a")
    
    # 9: Save config
    ws.save()
    assert (workspace_env / "project_config.json").exists()
    
    # 10: Reopen config
    ws2 = ProjectWorkspace.load(workspace_env)
    assert len(ws2.registry) == 4
    
    # Validate preserved state
    assert ws2.registry["dataset_a"].status == TableStatus.LOADED.value
    assert ws2.registry["dataset_a"].row_count == 2

def test_missing_and_changed_files(workspace_env):
    ws = ProjectWorkspace(workspace_env)
    ws.discover_datasets()
    ws.load_table("dataset_a")
    ws.save()
    
    # Wait to ensure mtime changes
    time.sleep(0.1)
    
    # 11: Missing file
    (workspace_env / 'dataset_b.xlsx').unlink()
    
    # 12: Changed file
    pd.DataFrame({'a': [1,2,3,4]}).to_csv(workspace_env / 'dataset_a.csv', index=False)
    
    ws2 = ProjectWorkspace.load(workspace_env)
    
    assert ws2.registry["dataset_b"].status == TableStatus.MISSING.value
    assert ws2.registry["dataset_a"].status == TableStatus.DISCOVERED.value
    assert ws2.registry["dataset_a"].row_count is None # Invalidated

def test_original_files_unchanged(workspace_env):
    # 13: Original source files remain unchanged
    file_path = workspace_env / 'dataset_a.csv'
    orig_content = file_path.read_bytes()
    orig_mtime = file_path.stat().st_mtime
    
    ws = ProjectWorkspace(workspace_env)
    ws.discover_datasets()
    ws.load_table("dataset_a")
    
    assert file_path.read_bytes() == orig_content
    assert file_path.stat().st_mtime == orig_mtime

def test_corrupt_project_config_preserves_backup(tmp_path):
    # Test that corrupt project_config.json is preserved as .bak before being overwritten
    config_path = tmp_path / "project_config.json"
    corrupt_content = '{"project_name": "Broken", "tables": { MALFORMED JSON HERE '
    config_path.write_text(corrupt_content, encoding="utf-8")

    ws = ProjectWorkspace.load(tmp_path)
    assert ws is not None

    bak_path = tmp_path / "project_config.corrupted.bak"
    assert bak_path.exists()
    assert bak_path.read_text(encoding="utf-8") == corrupt_content

    # The new config was cleanly saved
    assert config_path.exists()
    new_data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "project_name" in new_data
