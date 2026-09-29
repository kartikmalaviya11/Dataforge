import pytest
import pandas as pd
from pathlib import Path
from src.pipeline import run_pipeline
from unittest.mock import patch, MagicMock

class MockUploadedFile:
    def __init__(self, name, content):
        self.name = name
        self._content = content
        self.size = len(content)
    def getvalue(self):
        return self._content

def test_pipeline_regression(tmp_path):
    df = pd.DataFrame({'price': [-10.0, 20.0, 30.0, 30.0], 'category': ['A ', 'B', None, None]})
    
    csv_path = tmp_path / 'sales.csv'
    df.to_csv(csv_path, index=False)
    
    with open(csv_path, 'rb') as f:
        file_obj = MockUploadedFile('sales.csv', f.read())
        
    rules_path = tmp_path / 'rules.yaml'
    rules_path.write_text('')
    
    with patch('src.pipeline.st') as mock_st:
        state_dict = {}
        class SessionStateMock:
            def __getattr__(self, name):
                if name == "workspace":
                    return MagicMock() 
                return state_dict.get(name)
            def __setattr__(self, name, value):
                state_dict[name] = value
                
        mock_st.session_state = SessionStateMock()
        
        success, error = run_pipeline(file_obj, str(rules_path))
        
        assert success is True, f"Pipeline failed: {error}"
        
        res = mock_st.session_state.analysis_results
        
        assert res is not None
        assert res['filename'] == 'sales.csv'
        assert isinstance(res['df'], pd.DataFrame)
        
        issue_descriptions = [(i.message + ' ' + i.issue_type).lower() for i in res['all_issues']]
        
        # Verify specific quality issues are detected on intentionally invalid input
        assert any("duplicate" in d for d in issue_descriptions), f"Failed to detect duplicate row. Issues: {issue_descriptions}"
        assert any("missing" in d or "null" in d for d in issue_descriptions), "Failed to detect missing values on category column"
        
        proposals = res['proposals']
        # The data has leading/trailing whitespaces ('A ') which should trigger a STRIP whitespace proposal
        strip_proposals = [p for p in proposals if 'strip' in p.action.lower() or 'whitespace' in p.reason.lower()]
        assert strip_proposals, "Failed to generate STRIP_WHITESPACE proposal for 'A ' in category column"





