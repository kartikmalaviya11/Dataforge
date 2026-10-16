
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
    zip_path = manager.generate_package({"config": {"name": "test"}, "raw_data": "id,val\n1,2"})
    import zipfile
    pkg_dir = zip_path.replace(".zip", "_extracted")
    with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(pkg_dir)
    assert os.path.exists(os.path.join(pkg_dir, "raw", "data.csv"))
    assert os.path.exists(os.path.join(pkg_dir, "manifest.json"))

    with open(os.path.join(pkg_dir, "manifest.json"), "r") as f:
        manifest = json.load(f)
        assert "raw\\data.csv" in manifest or "raw/data.csv" in manifest or "raw"+os.sep+"data.csv" in manifest

def test_hash_verification(manager):
    zip_path = manager.generate_package({"config": {"name": "test"}, "raw_data": "id,val\n1,2"})
    import zipfile
    pkg_dir = zip_path.replace(".zip", "_extracted")
    with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(pkg_dir)
    assert manager.verify_package(pkg_dir) == True

    # Tamper
    with open(os.path.join(pkg_dir, "raw", "data.csv"), "w") as f:
        f.write("tampered")
    assert manager.verify_package(pkg_dir) == False

def test_missing_artifacts_handling(manager):
    zip_path = manager.generate_package({"config": {"name": "test"}, "raw_data": "id,val\n1,2"})
    import zipfile
    pkg_dir = zip_path.replace(".zip", "_extracted")
    with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(pkg_dir)
    os.remove(os.path.join(pkg_dir, "raw", "data.csv"))
    assert manager.verify_package(pkg_dir) == False

def test_raw_immutability(manager):
    data = "id,val\n1,2"
    zip_path = manager.generate_package({"config": {}, "raw_data": data})
    import zipfile
    pkg_dir = zip_path.replace(".zip", "_extracted")
    with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(pkg_dir)
    with open(os.path.join(pkg_dir, "raw", "data.csv"), "r") as f:
        read_data = f.read()
    assert read_data == data

def test_export_package_with_workspace_genuine_artifacts_and_immutability(tmp_path):
    import hashlib
    import zipfile
    from src.workspace import ProjectWorkspace

    ws_root = tmp_path / "test_ws"
    ws_root.mkdir(parents=True, exist_ok=True)
    raw_file = ws_root / "raw_table.csv"
    raw_content = "id,name,value\n1,alpha,100\n2,beta,200\n"
    raw_file.write_text(raw_content, encoding="utf-8")
    before_hash = hashlib.sha256(raw_file.read_bytes()).hexdigest()

    ws = ProjectWorkspace(ws_root)
    ws.discover_datasets()

    # Add genuine cleaned file
    cleaned_dir = ws_root / ".dataforge" / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    (cleaned_dir / "cleaned_table.csv").write_text("id,name,value\n1,alpha,100\n", encoding="utf-8")

    # Add metadata in subfolder
    sub_meta = ws_root / ".dataforge" / "business_impact"
    sub_meta.mkdir(parents=True, exist_ok=True)
    (sub_meta / "impacts.json").write_text('{"imp1": {"status": "POTENTIAL_IMPACT"}}', encoding="utf-8")

    # Add reports in docs
    docs_dir = ws_root / ".dataforge" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "summary.md").write_text("# Project Summary\nAll good.", encoding="utf-8")

    export_mgr = ProjectExportManager(str(ws_root / ".dataforge" / "export"))
    zip_path = export_mgr.generate_package(workspace=ws)
    assert os.path.exists(zip_path)

    # 1. Source immutability
    after_hash = hashlib.sha256(raw_file.read_bytes()).hexdigest()
    assert before_hash == after_hash

    # 2. Extract and verify manifest
    extracted_dir = str(tmp_path / "extracted")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extracted_dir)

    assert export_mgr.verify_package(extracted_dir) is True

    # 3. Verify genuine cleaned data and subfolder metadata
    assert os.path.exists(os.path.join(extracted_dir, "cleaned", "cleaned_table.csv"))
    assert os.path.exists(os.path.join(extracted_dir, "reports", "summary.md"))
    assert os.path.exists(os.path.join(extracted_dir, "export_metadata.json"))

    with open(os.path.join(extracted_dir, "manifest.json"), "r") as f:
        manifest = json.load(f)

    # Every manifest entry must accurately match the file hash
    for rel_path, expected_hash in manifest.items():
        fp = os.path.join(extracted_dir, rel_path)
        assert os.path.exists(fp)
        with open(fp, "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == expected_hash

def test_export_package_includes_cleaned_tables_without_mutating_raw(tmp_path):
    import hashlib
    import zipfile
    import pandas as pd
    from src.workspace import ProjectWorkspace

    ws_root = tmp_path / "ws_cleaned_test"
    ws_root.mkdir(parents=True, exist_ok=True)
    raw_csv = ws_root / "customers.csv"
    raw_content = "id,name,email\n1,Alice,alice@example.com\n2,Bob,bob@invalid\n"
    raw_csv.write_text(raw_content, encoding="utf-8")
    raw_hash_before = hashlib.sha256(raw_csv.read_bytes()).hexdigest()

    ws = ProjectWorkspace(ws_root)
    ws.discover_datasets()

    # Repaired dataset in session state (e.g. invalid email repaired)
    repaired_df = pd.DataFrame([
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"}
    ])

    export_mgr = ProjectExportManager(str(ws_root / ".dataforge" / "export"))
    zip_path = export_mgr.generate_package(workspace=ws, cleaned_tables={"customers": repaired_df})
    assert os.path.exists(zip_path)

    # 1. Raw source immutability check
    raw_hash_after = hashlib.sha256(raw_csv.read_bytes()).hexdigest()
    assert raw_hash_before == raw_hash_after, "Raw source file must remain strictly immutable"

    # 2. Extract ZIP and verify contents
    extracted = str(tmp_path / "extracted_cleaned")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extracted)

    # 3. Cleaned data file present and matches repaired_df
    cleaned_file = os.path.join(extracted, "cleaned", "customers_cleaned.csv")
    assert os.path.exists(cleaned_file), "Cleaned dataset must be written to pkg/cleaned/"
    exported_cleaned_df = pd.read_csv(cleaned_file)
    assert len(exported_cleaned_df) == 2
    assert exported_cleaned_df.loc[1, "email"] == "bob@example.com"

    # 4. Manifest verification
    assert export_mgr.verify_package(extracted) is True
    with open(os.path.join(extracted, "manifest.json"), "r") as f:
        manifest = json.load(f)

    # Check that cleaned file is recorded in manifest with correct SHA-256
    cleaned_rel = os.path.join("cleaned", "customers_cleaned.csv")
    assert cleaned_rel in manifest or cleaned_rel.replace("\\", "/") in manifest
    actual_hash = hashlib.sha256(open(cleaned_file, "rb").read()).hexdigest()
    assert manifest.get(cleaned_rel, manifest.get(cleaned_rel.replace("\\", "/"))) == actual_hash
