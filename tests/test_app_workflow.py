import pytest
from streamlit.testing.v1 import AppTest
from unittest.mock import patch, MagicMock
from pathlib import Path
import pandas as pd
from src.workspace import ProjectWorkspace
import sys

def test_streamlit_initial_state():
    at = AppTest.from_file("../app.py").run(timeout=30)
    assert not at.exception
    assert at.session_state.current_page == "Data Import"

@patch('src.pipeline.run_pipeline')
def test_streamlit_workflow_mocked(mock_run, tmp_path):
    at = AppTest.from_file("../app.py").run(timeout=30)
    project_dir = tmp_path / "my_new_project"
    project_dir.mkdir()
    ws = ProjectWorkspace(project_dir)
    ws.save()
    
    # Enter path
    at.text_input[0].input(str(project_dir)).run(timeout=30)
    # Click Open
    open_btn = [btn for btn in at.button if btn.label == "Open Existing Project"][0]
    open_btn.click().run(timeout=30)
    
    assert not at.exception
    assert at.session_state.current_page == "Overview"

@patch('src.pipeline.run_pipeline')
def test_e2e_button_actions(mock_run, tmp_path):
    at = AppTest.from_file("../app.py").run(timeout=30)
    
    # Setup mock workspace
    project_dir = tmp_path / "e2e_project"
    project_dir.mkdir()
    df = pd.DataFrame({"id": [1, 2], "val": [10, 20]})
    df.to_csv(project_dir / "data1.csv", index=False)
    ws = ProjectWorkspace(project_dir)
    ws.discover_datasets()
    ws.save()
    
    at.text_input[0].input(str(project_dir)).run(timeout=30)
    open_btn = [btn for btn in at.button if btn.label == "Open Existing Project"][0]
    open_btn.click().run(timeout=30)
    
    assert at.session_state.current_page == "Overview"
