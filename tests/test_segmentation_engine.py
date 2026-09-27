import pytest
import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
import json

from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine
from src.segmentation_engine import (
    SegmentDefinition,
    ExplicitThresholdRule,
    PercentileRule,
    SegmentationEngine,
    SegmentationConfig
)

@pytest.fixture
def workspace_and_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = ProjectWorkspace(tmpdir, "test_proj")
        
        # Create a dummy dataset
        df = pd.DataFrame({
            'customer_id': range(1, 11),
            'spend': [10, 20, 30, 40, 50, 60, 70, 80, 90, np.nan],
            'category': ['A', 'A', 'B', 'B', 'B', 'C', 'C', 'C', 'D', 'D']
        })
        
        file_path = Path(tmpdir) / "sales.csv"
        df.to_csv(file_path, index=False)
        
        ws.discover_datasets()
        ws.load_table("sales")
        
        engine = DuckDBEngine(ws)
        yield ws, engine
        engine.close()

def test_explicit_threshold_rule(workspace_and_engine):
    ws, engine = workspace_and_engine
    
    config = SegmentationConfig(
        table_name="sales",
        column_name="spend",
        segments=[
            SegmentDefinition("Low", ExplicitThresholdRule(min_val=None, max_val=30, end_inclusive=True)),
            SegmentDefinition("Medium", ExplicitThresholdRule(min_val=30, max_val=70, start_inclusive=False, end_inclusive=True)),
            SegmentDefinition("High", ExplicitThresholdRule(min_val=70, max_val=None, start_inclusive=False))
        ]
    )
    
    seg_engine = SegmentationEngine(ws, engine)
    
    # Pandas mode
    df_pd = seg_engine.apply_segmentation(config, mode="pandas")
    
    assert df_pd.loc[df_pd['customer_id'] == 1, 'segment'].iloc[0] == "Low"
    assert df_pd.loc[df_pd['customer_id'] == 3, 'segment'].iloc[0] == "Low"
    assert df_pd.loc[df_pd['customer_id'] == 4, 'segment'].iloc[0] == "Medium"
    assert df_pd.loc[df_pd['customer_id'] == 7, 'segment'].iloc[0] == "Medium"
    assert df_pd.loc[df_pd['customer_id'] == 8, 'segment'].iloc[0] == "High"
    # Missing value
    assert pd.isna(df_pd.loc[df_pd['customer_id'] == 10, 'segment'].iloc[0])
    
    # DuckDB mode
    df_sql = seg_engine.apply_segmentation(config, mode="duckdb")
    
    # Parity check
    pd.testing.assert_series_equal(df_pd['segment'], df_sql['segment'], check_names=False, check_dtype=False)

def test_percentile_rule(workspace_and_engine):
    ws, engine = workspace_and_engine
    
    # We have 9 valid values for spend: 10, 20, 30, 40, 50, 60, 70, 80, 90
    config = SegmentationConfig(
        table_name="sales",
        column_name="spend",
        segments=[
            SegmentDefinition("Bottom 33%", PercentileRule(min_pct=0, max_pct=33.33, end_inclusive=True)),
            SegmentDefinition("Middle 33%", PercentileRule(min_pct=33.33, max_pct=66.67, start_inclusive=False, end_inclusive=True)),
            SegmentDefinition("Top 33%", PercentileRule(min_pct=66.67, max_pct=100, start_inclusive=False, end_inclusive=True))
        ]
    )
    
    seg_engine = SegmentationEngine(ws, engine)
    
    df_pd = seg_engine.apply_segmentation(config, mode="pandas")
    df_sql = seg_engine.apply_segmentation(config, mode="duckdb")
    
    # Percentiles in pandas: 10 is 0%, 50 is 50%, 90 is 100%
    # Spend <= 33.33% of data range => 33.33% percentile is ~ 36.66
    # So 10, 20, 30 are Bottom
    assert df_pd.loc[df_pd['customer_id'] == 3, 'segment'].iloc[0] == "Bottom 33%"
    assert df_pd.loc[df_pd['customer_id'] == 4, 'segment'].iloc[0] == "Middle 33%"
    
    # Duckdb percentile_cont might calculate slightly different, but let's try to ensure parity.
    pd.testing.assert_series_equal(df_pd['segment'], df_sql['segment'], check_names=False, check_dtype=False)

def test_overlap_rejection(workspace_and_engine):
    ws, engine = workspace_and_engine
    
    # Overlapping bounds
    config = SegmentationConfig(
        table_name="sales",
        column_name="spend",
        segments=[
            SegmentDefinition("A", ExplicitThresholdRule(min_val=0, max_val=50, end_inclusive=True)),
            SegmentDefinition("B", ExplicitThresholdRule(min_val=40, max_val=100, start_inclusive=True, end_inclusive=True))
        ]
    )
    
    seg_engine = SegmentationEngine(ws, engine)
    
    with pytest.raises(ValueError, match="overlap"):
        seg_engine.validate_config(config)

def test_gap_detection(workspace_and_engine):
    ws, engine = workspace_and_engine
    
    # Gaps in bounds
    config = SegmentationConfig(
        table_name="sales",
        column_name="spend",
        segments=[
            SegmentDefinition("A", ExplicitThresholdRule(min_val=0, max_val=40, end_inclusive=True)),
            SegmentDefinition("B", ExplicitThresholdRule(min_val=60, max_val=100, start_inclusive=True, end_inclusive=True))
        ]
    )
    
    seg_engine = SegmentationEngine(ws, engine)
    
    # We can detect gaps, maybe it's a warning or we handle them gracefully.
    warnings = seg_engine.validate_config(config)
    assert any("gap" in w.lower() for w in warnings)

def test_persistence(workspace_and_engine):
    ws, engine = workspace_and_engine
    
    config = SegmentationConfig(
        table_name="sales",
        column_name="spend",
        segments=[
            SegmentDefinition("Low", ExplicitThresholdRule(min_val=None, max_val=50, end_inclusive=True))
        ]
    )
    
    seg_engine = SegmentationEngine(ws, engine)
    seg_engine.save_config("spend_segments", config)
    
    # Check persistence
    path = ws.project_root / ".dataforge" / "segmentations.json"
    assert path.exists()
    
    with open(path, "r") as f:
        data = json.load(f)
    
    assert "spend_segments" in data
    assert data["spend_segments"]["table_name"] == "sales"
    
    # Load back
    loaded_config = seg_engine.load_config("spend_segments")
    assert loaded_config.column_name == "spend"
    assert len(loaded_config.segments) == 1
    assert loaded_config.segments[0].name == "Low"
    assert loaded_config.segments[0].rule.max_val == 50
