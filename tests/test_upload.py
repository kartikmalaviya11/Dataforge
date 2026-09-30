import pytest
from streamlit.testing.v1 import AppTest
from pathlib import Path
import hashlib
import pandas as pd
import io
from src.workspace import ProjectWorkspace

def test_upload_empty_state():
    at = AppTest.from_file("../app.py").run()
    assert at.session_state.current_page == "Data Import"
    assert any("Upload Your Data" in str(m.value) for m in at.markdown)

def test_single_csv_upload():
    at = AppTest.from_file("../app.py").run()
    csv_bytes = b"id,val\n1,10\n2,20"
    at.file_uploader[0].set_value([("data.csv", csv_bytes, "text/csv")]).run()
    assert any("data.csv" in str(m.value) for m in at.markdown)

def test_multiple_csv_upload():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([
        ("customers.csv", b"id\n1", "text/csv"),
        ("orders.csv", b"id\n2", "text/csv")
    ]).run()
    assert any("customers.csv" in str(m.value) for m in at.markdown)
    assert any("orders.csv" in str(m.value) for m in at.markdown)

def test_xlsx_upload():
    at = AppTest.from_file("../app.py").run()
    
    df = pd.DataFrame({"id": [1, 2], "val": [10, 20]})
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    xlsx_bytes = buffer.read()
    
    at.file_uploader[0].set_value([("data.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    assert not at.exception
    assert at.session_state.current_page == "Overview"
    ws = at.session_state.workspace
    assert "data" in ws.registry

def test_supported_extension_validation(monkeypatch):
    monkeypatch.setenv("DATAFORGE_TESTING", "1")
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([("data.json", b'{"a": 1}', "application/json")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    assert any("Unsupported format: data.json" in err.value for err in at.error)
    assert at.session_state.current_page == "Data Import"
    assert "workspace" not in at.session_state

def test_invalid_extension(monkeypatch):
    monkeypatch.setenv("DATAFORGE_TESTING", "1")
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([("data.txt", b"id\n1", "text/plain")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    # Verify DATAFORGE explicit error is shown
    assert any("Unsupported format: data.txt" in err.value for err in at.error)
    
    # Verify no workspace is created
    assert at.session_state.current_page == "Data Import"
    assert "workspace" not in at.session_state


def test_duplicate_filename():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([
        ("data.csv", b"id\n1", "text/csv"),
        ("data.csv", b"id\n2", "text/csv")
    ]).run()
    
    # Check if streamlit deduped them or if our error shows
    has_start = any(btn.label == "Start Analysis" for btn in at.button)
    if has_start:
        start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
        start_btn.click().run()
        if at.error:
            assert "Duplicate filename: data.csv" in at.error[0].value
        else:
            ws = at.session_state.workspace
            assert len(ws.registry) == 1

def test_remove_file():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([
        ("data1.csv", b"id\n1", "text/csv"),
        ("data2.csv", b"id\n2", "text/csv")
    ]).run()
    
    assert any("data1.csv" in str(m.value) for m in at.markdown)
    assert any("data2.csv" in str(m.value) for m in at.markdown)
    
    remove_btn = [btn for btn in at.button if btn.key == "remove_data2.csv"][0]
    remove_btn.click().run()
    
    assert any("data1.csv" in str(m.value) for m in at.markdown)
    assert not any("data2.csv" in str(m.value) for m in at.markdown)

def test_remove_all():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([
        ("data1.csv", b"id\n1", "text/csv"),
        ("data2.csv", b"id\n2", "text/csv")
    ]).run()
    
    remove_all_btn = [btn for btn in at.button if btn.label == "Remove All"][0]
    remove_all_btn.click().run()
    
    assert not any("data1.csv" in str(m.value) for m in at.markdown)
    assert not any("data2.csv" in str(m.value) for m in at.markdown)

def test_start_analysis():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([("data.csv", b"id\n1\n2", "text/csv")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    assert not at.exception
    assert at.session_state.current_page == "Overview"
    ws = at.session_state.workspace
    assert "data" in ws.registry

def test_uploaded_raw_hash_unchanged():
    at = AppTest.from_file("../app.py").run()
    csv_bytes = b"id,val\n1,10\n2,20\n3,30"
    h1 = hashlib.sha256(csv_bytes).hexdigest()
    
    at.file_uploader[0].set_value([("testhash.csv", csv_bytes, "text/csv")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    ws = at.session_state.workspace
    target_file = ws.project_root / "testhash.csv"
    h2 = hashlib.sha256(target_file.read_bytes()).hexdigest()
    
    assert h1 == h2

def test_multi_table_workspace():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([
        ("customers.csv", b"id,name\n1,Alice", "text/csv"),
        ("orders.csv", b"id,customer_id\n10,1", "text/csv")
    ]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    ws = at.session_state.workspace
    assert len(ws.registry) == 2
    assert "customers" in ws.registry
    assert "orders" in ws.registry

def test_existing_project_still_works(tmp_path):
    pd.DataFrame({"id": [1]}).to_csv(tmp_path / "data.csv", index=False)
    ws = ProjectWorkspace(tmp_path)
    ws.discover_datasets()
    ws.save()
    
    at = AppTest.from_file("../app.py").run()
    at.text_input[0].input(str(tmp_path)).run()
    
    open_btn = [btn for btn in at.button if btn.label == "Open Existing Project"][0]
    open_btn.click().run()
    
    assert not at.exception
    assert at.session_state.current_page == "Overview"
    assert "data" in at.session_state.workspace.registry

def test_upload_to_overview_transition():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([("data.csv", b"id\n1\n2", "text/csv")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    assert at.session_state.current_page == "Overview"

def test_xlsx_raw_hash_unchanged():
    df = pd.DataFrame({"id": [1, 2], "val": [10, 20]})
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    xlsx_bytes = buffer.read()
    
    at = AppTest.from_file("../app.py").run()
    h1 = hashlib.sha256(xlsx_bytes).hexdigest()
    
    at.file_uploader[0].set_value([("data.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    ws = at.session_state.workspace
    target_file = ws.project_root / "data.xlsx"
    h2 = hashlib.sha256(target_file.read_bytes()).hexdigest()
    
    assert h1 == h2

def test_empty_file_size_validation():
    at = AppTest.from_file("../app.py").run()
    at.file_uploader[0].set_value([("empty.csv", b"", "text/csv")]).run()
    
    start_btn = [btn for btn in at.button if btn.label == "Start Analysis"][0]
    start_btn.click().run()
    
    assert "File is empty: empty.csv" in at.error[0].value

def test_workspace_persistence(tmp_path):
    ws = ProjectWorkspace(tmp_path)
    ws.save()
    ws2 = ProjectWorkspace.load(tmp_path)
    assert ws.project_name == ws2.project_name
