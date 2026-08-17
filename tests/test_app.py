import pytest
import os
from pathlib import Path
import collections
from app import run_pipeline

def test_app_pipeline_execution():
    """Test that the app.py backend pipeline runs successfully on a valid dataset."""
    test_file = Path("data/Ecommerce_Sales_Data.xlsx")
    if not test_file.exists():
        pytest.skip("Test file not found")
        
    rules_file = Path("config/rules.yaml")
    
    # Mock Streamlit UploadedFile
    UploadedFile = collections.namedtuple('UploadedFile', ['name', 'size', 'getvalue'])
    
    with open(test_file, 'rb') as f:
        content = f.read()
        
    mock_file = UploadedFile(
        name=test_file.name,
        size=len(content),
        getvalue=lambda: content
    )
    
    success, err = run_pipeline(mock_file, str(rules_file))
    
    assert success is True, f"Pipeline failed: {err}"
    assert err == ""

def test_validate_default_cols():
    from app import validate_default_cols
    import pandas as pd
    
    # 1. Default column exists
    df_columns = pd.Index(['A', 'B', 'C'])
    assert validate_default_cols(df_columns, ['A', 'C']) == ['A', 'C']
    
    # 2. Default column missing
    assert validate_default_cols(df_columns, ['D']) == ['A', 'B', 'C']
    
    # 3. Mixed valid/invalid default columns
    assert validate_default_cols(df_columns, ['A', 'D']) == ['A']
    
    # 4. Fallback behavior (max 5)
    df_columns_many = pd.Index(['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'])
    assert validate_default_cols(df_columns_many, ['Missing']) == ['C1', 'C2', 'C3', 'C4', 'C5']