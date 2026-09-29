import pytest
from streamlit.testing.v1 import AppTest
from src.workspace import ProjectWorkspace
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

def test_streamlit_initial_state():
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    assert not at.exception
    assert at.session_state.current_page == "Project Setup"
    
def test_streamlit_workflow_mocked(tmp_path):
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    
    ws = ProjectWorkspace(tmp_path)
    df = pd.DataFrame({'id': [1,2,2], 'price': [10.0, 20.0, 20.0]})
    df.to_csv(tmp_path / 'sales.csv', index=False)
    ws.discover_datasets()
    
    at.session_state.workspace = ws
    at.session_state.analysis_results = {
        'df': df,
        'filename': 'sales.csv'
    }
    
    pages = [
        "Overview", "Data Quality", "Issues", "Cleaning", "Validation",
        "Relationships", "Feature Engineering", "SQL Workspace",
        "KPI Center", "Business Questions", "Segmentation", "Anomaly Detection",
        "Date Analysis", "RCA", "Findings",
        "Power BI Model", "Advanced DAX", "Dashboard Blueprint", "Insight Visuals",
        "Data Lineage", "Run History", "Dataset Versions", "Readiness", "Assumptions",
        "Business Impact", "Documentation", "Export Package", "Domain Templates"
    ]
    
    for page in pages:
        at.session_state.current_page = page
        at.run()
        assert not at.exception, f"Exception occurred on page {page}"

def test_e2e_button_actions(tmp_path):
    ws = ProjectWorkspace(tmp_path)
    df = pd.DataFrame({'id': [1,2,2], 'price': [10.0, 20.0, 20.0], 'category': ['A ', 'B', None], 'created_at': ['2023-01-01', '2023-01-02', '2023-01-03']})
    df.to_csv(tmp_path / 'sales.csv', index=False)
    ws.discover_datasets()
    from src.workspace import TableStatus
    ws.registry['sales'].status = TableStatus.ANALYZED
    
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    at.session_state.workspace = ws
    
    from src.pipeline import run_pipeline
    class MockFile:
        def __init__(self, c): self._c = c; self.name = 'sales.csv'; self.size=len(c)
        def getvalue(self): return self._c
    with open(tmp_path / 'sales.csv', 'rb') as f:
        mf = MockFile(f.read())
    import streamlit as st
    with patch('src.pipeline.st') as mock_st:
        mock_st.session_state = MagicMock()
        mock_st.session_state.workspace = ws
        run_pipeline(mf, None)
        res = mock_st.session_state.analysis_results
        at.session_state.analysis_results = res
    
    action_matrix = [
        ('Overview', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Data Quality', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Issues', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Cleaning', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Cleaning', 'Approve Safe Fixes', None, lambda at: assert_success(at, "Repairs applied")), 
        ('Validation', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Relationships', 'Detect Relationships', None, lambda at: assert_success(at, "Detected candidates")), 
        ('Feature Engineering', 'Create', lambda at: at.text_input(key="fe_name").set_value("new_feat").run(), lambda at: assert_success(at, "Feature created")), 
        ('SQL Workspace', 'Run', lambda at: at.text_area[0].set_value("SELECT * FROM sales LIMIT 5").run(), lambda at: assert_dataframe(at)), 
        ('KPI Center', 'Generate KPIs', None, lambda at: assert_success(at, "KPIs generated")), 
        ('Business Questions', 'Auto Generate', None, lambda at: assert_success(at, "Generated.")), 
        ('Segmentation', 'Auto Segment', None, lambda at: assert_success(at, "Segments generated")), 
        ('Anomaly Detection', 'Detect Outliers', None, lambda at: assert_success(at, "Analysis saved")), 
        ('Date Analysis', 'Generate Date Table', None, lambda at: assert_success(at, "Date table generated")), 
        ('RCA', 'Run Example RCA', None, lambda at: assert_success(at, "Executed RCA")), 
        ('Findings', 'Create Dummy Finding', None, lambda at: assert_success(at, "Saved.")), 
        ('Power BI Model', 'Generate Model', None, lambda at: assert_success(at, "Model Generated!")), 
        ('Data Lineage', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Advanced DAX', 'Generate DAX', None, lambda at: assert_success(at, "DAX Generated!")), 
        ('Dashboard Blueprint', 'Generate Blueprint', None, lambda at: assert_success(at, "Blueprint Generated")), 
        ('Insight Visuals', 'Generate Mapping', None, lambda at: assert_success(at, "Mapping Generated")), 
        ('Run History', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Dataset Versions', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Readiness', 'NAVIGATION/INFORMATION ACTION', None, None), 
        ('Assumptions', 'Register Assumption', None, lambda at: assert_success(at, "Registered")), 
        ('Business Impact', 'Map Impact', None, lambda at: assert_success(at, "Impact Mapped")), 
        ('Documentation', 'Generate All Docs', None, lambda at: assert_success(at, "Documentation Generated")), 
        ('Export Package', 'Build Export Package', None, lambda at: assert_success(at, "Exported")), 
        ('Domain Templates', 'Apply Template', None, lambda at: assert_success(at, "Loaded")), 
    ]
    
    def assert_success(at, expected_text):
        successes = [s.value for s in at.success]
        assert any(expected_text.lower() in s.lower() for s in successes), f"Expected success message containing '{expected_text}', got: {successes}"
        
    def assert_dataframe(at):
        assert len(at.dataframe) > 0, "Expected a dataframe in the output"
    
    for page, button_label, setup_fn, verify_fn in action_matrix:
        at.session_state.current_page = page
        at.run()
        assert not at.exception, f"Exception during render of page '{page}': {at.exception}"
        
        if button_label == 'NAVIGATION/INFORMATION ACTION':
            continue
            
        clicked = False
        for btn in at.button:
            if btn.label == button_label:
                if setup_fn:
                    setup_fn(at)
                    
                btn.click().run()
                assert not at.exception, f"Exception during action '{button_label}' on page '{page}': {at.exception}"
                
                errs = [e.value for e in at.error]
                assert not errs, f"Action '{button_label}' produced errors: {errs}"
                
                warns = [w.value for w in at.warning]
                assert not warns, f"Action '{button_label}' produced warnings: {warns}"
                
                if verify_fn:
                    verify_fn(at)
                    
                clicked = True
                break
                
        if not clicked:
            print(f"AVAILABLE BUTTONS ON {page}:", [b.label for b in at.button])
        assert clicked, f"Button '{button_label}' not found on page '{page}'"
