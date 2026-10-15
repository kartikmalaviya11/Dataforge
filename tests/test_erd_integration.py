import pytest
import os
import shutil
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from src.workspace import ProjectWorkspace, TableRegistryEntry, TableStatus
import hashlib

@pytest.fixture
def workspace():
    ws_dir = ".dataforge_test_erd"
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)
    os.makedirs(ws_dir)
    ws = ProjectWorkspace(ws_dir)
    
    with open(os.path.join(ws_dir, "customers.csv"), "w") as f:
        f.write("id,name\n1,Alice\n2,Bob")
    with open(os.path.join(ws_dir, "orders.csv"), "w") as f:
        f.write("order_id,customer_id\n100,1\n101,2")
        
    ws.registry["customers"] = TableRegistryEntry(
        table_name="customers", file_name="customers.csv",
        file_path=os.path.join(ws_dir, "customers.csv"),
        file_type="csv", row_count=2, column_count=2, status=TableStatus.LOADED.value, last_modified=0
    )
    ws.registry["orders"] = TableRegistryEntry(
        table_name="orders", file_name="orders.csv",
        file_path=os.path.join(ws_dir, "orders.csv"),
        file_type="csv", row_count=2, column_count=2, status=TableStatus.LOADED.value, last_modified=0
    )
    ws.save()
    
    yield ws
    if os.path.exists(ws_dir):
        shutil.rmtree(ws_dir)

@patch("ui.pages.analysis.st.graphviz_chart")
def test_erd_ui_integration(mock_graphviz, workspace):
    at = AppTest.from_file("../app.py")
    at.run(timeout=30)
    
    at.text_input[0].input(str(workspace.project_root)).run(timeout=30)
    open_btn = [btn for btn in at.button if btn.label == "Open Existing Project"][0]
    open_btn.click().run(timeout=30)
    
    rel_btn = [b for b in at.button if b.label == "Relationships"][0]
    rel_btn.click().run(timeout=30)
    
    detect_btn_key = f"btn_{hashlib.md5('Detect Relationships'.encode()).hexdigest()}"
    at.button(key=detect_btn_key).click().run(timeout=30)
    
    cands = at.session_state.relationship_candidates
    order_cand = next((c for c in cands if c.source_table == "orders" and c.target_table == "customers"), None)
    
    # CANDIDATE should not have edge
    order_cand.status = "CANDIDATE"
    mock_graphviz.reset_mock()
    at.run(timeout=30)
    mock_graphviz.assert_called_once()
    assert "->" not in mock_graphviz.call_args[0][0]
    
    # REJECTED should not have edge
    order_cand.status = "REJECTED"
    mock_graphviz.reset_mock()
    at.run(timeout=30)
    mock_graphviz.assert_called_once()
    assert "->" not in mock_graphviz.call_args[0][0]

    # ACCEPTED should call graphviz and have edge
    order_cand.status = "ACCEPTED"
    at.run(timeout=30)
    assert mock_graphviz.call_count > 0
    assert "orders:customer_id -> customers:id" in mock_graphviz.call_args[0][0]

@patch("ui.pages.analysis.st.graphviz_chart")
def test_erd_ui_empty_state(mock_graphviz, workspace):
    at = AppTest.from_file("../app.py")
    at.run(timeout=30)
    
    at.text_input[0].input(str(workspace.project_root)).run(timeout=30)
    open_btn = [btn for btn in at.button if btn.label == "Open Existing Project"][0]
    open_btn.click().run(timeout=30)
    
    rel_btn = [b for b in at.button if b.label == "Relationships"][0]
    rel_btn.click().run(timeout=30)
    
    mock_graphviz.assert_not_called()
