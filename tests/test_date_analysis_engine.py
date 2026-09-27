import pytest
import pandas as pd
import numpy as np
import json
from pathlib import Path
from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine
from src.date_analysis_engine import (
    DateDimensionConfig,
    DateTableMetadata,
    TimeMetricDefinition,
    DateAnalysisEngine
)

@pytest.fixture
def workspace(tmp_path):
    ws = ProjectWorkspace(tmp_path)
    return ws

@pytest.fixture
def duckdb_engine(workspace):
    engine = DuckDBEngine(workspace)
    return engine

@pytest.fixture
def date_engine(workspace, duckdb_engine):
    return DateAnalysisEngine(workspace, duckdb_engine)

def test_generate_date_table_pandas(date_engine):
    # Setup
    df = pd.DataFrame({
        'date_col': ['2023-01-01', '2023-12-31', 'invalid', None, '2024-02-29']
    })
    
    date_engine.duckdb_engine.conn.execute("CREATE TABLE source_data AS SELECT * FROM df")
    
    config = DateDimensionConfig(
        config_id="conf_1",
        source_table="source_data",
        date_column="date_col",
        user_min_date=None,
        user_max_date=None,
        missing_date_behavior="DROP"
    )
    date_engine.register_config(config)
    
    date_table = date_engine.generate_date_table_pandas(config.config_id)
    
    # 2023-01-01 to 2024-02-29 is 425 days
    assert len(date_table) == 425
    assert 'ISO_Year' in date_table.columns
    assert 'ISO_Week' in date_table.columns
    
    # Dec 31, 2023 is Sunday. ISO year 2023, week 52
    dec31 = date_table[date_table['Date'] == pd.Timestamp('2023-12-31')].iloc[0]
    assert dec31['ISO_Year'] == 2023
    assert dec31['ISO_Week'] == 52

def test_generate_date_table_duckdb(date_engine):
    df = pd.DataFrame({
        'date_col': ['2023-01-01', '2024-02-29']
    })
    date_engine.duckdb_engine.conn.execute("CREATE TABLE source_data_2 AS SELECT * FROM df")
    
    config = DateDimensionConfig(
        config_id="conf_2",
        source_table="source_data_2",
        date_column="date_col",
        user_min_date=None,
        user_max_date=None,
        missing_date_behavior="DROP"
    )
    date_engine.register_config(config)
    
    date_table_duckdb = date_engine.generate_date_table_duckdb(config.config_id)
    date_table_pandas = date_engine.generate_date_table_pandas(config.config_id)
    
    pd.testing.assert_frame_equal(date_table_pandas.reset_index(drop=True), date_table_duckdb.reset_index(drop=True), check_dtype=False)

def test_persistence(date_engine, workspace):
    config = DateDimensionConfig("c1", "t1", "d1", "2020-01-01", "2020-12-31", "DROP")
    date_engine.register_config(config)
    
    metric = TimeMetricDefinition("m1", "kpi_1", "MoM", "RETURN_NULL")
    date_engine.register_metric(metric)
    
    # Check file exists
    config_file = workspace.project_root / ".dataforge" / "date_configs.json"
    assert config_file.exists()
    
    # Reload
    engine2 = DateAnalysisEngine(workspace, DuckDBEngine(workspace))
    assert "c1" in engine2.configs
    assert "m1" in engine2.metrics

def test_time_metric_mom(date_engine):
    df = pd.DataFrame({
        'Date': pd.date_range('2023-01-01', '2023-05-31', freq='D'),
    })
    # Add some values: Jan=31, Feb=28, Mar=31, Apr=30, May=31
    df['value'] = 1.0
    
    metric = TimeMetricDefinition("m_mom", "base", "MoM", "RETURN_NULL")
    date_engine.register_metric(metric)
    
    # Calculate pandas
    res = date_engine.calculate_time_metric_pandas(df, 'Date', 'value', metric.metric_id)
    
    # Jan has no previous month -> MoM = NULL
    # Feb has Jan -> (28 - 31) / 31 = -3/31
    # Mar has Feb -> (31 - 28) / 28 = 3/28
    
    res_feb = res[res['YearMonth'] == '2023-02'].iloc[0]
    assert np.isclose(res_feb['MoM_Growth'], (28 - 31) / 31)

def test_time_metric_yoy(date_engine):
    df = pd.DataFrame({
        'Date': pd.date_range('2023-01-01', '2024-03-31', freq='D'),
    })
    df['value'] = 10.0
    
    metric = TimeMetricDefinition("m_yoy", "base", "YoY", "RETURN_NULL")
    date_engine.register_metric(metric)
    
    res = date_engine.calculate_time_metric_pandas(df, 'Date', 'value', metric.metric_id)
    
    res_mar = res[res['YearMonth'] == '2024-03'].iloc[0]
    # Mar 2023 value = 31 * 10 = 310
    # Mar 2024 value = 31 * 10 = 310
    # YoY = 0.0
    assert np.isclose(res_mar['YoY_Growth'], 0.0)

def test_rolling_3_months(date_engine):
    df = pd.DataFrame({
        'Date': pd.date_range('2023-01-01', '2023-06-30', freq='D'),
    })
    df['value'] = 1.0
    
    metric = TimeMetricDefinition("m_roll", "base", "ROLLING_3_MONTH", "RETURN_NULL")
    date_engine.register_metric(metric)
    
    res = date_engine.calculate_time_metric_pandas(df, 'Date', 'value', metric.metric_id)
    
    # Jan (31), Feb (28), Mar (31) = 90
    res_mar = res[res['YearMonth'] == '2023-03'].iloc[0]
    assert res_mar['ROLLING_3_MONTH_SUM'] == 90.0
    
    # Jan shouldn't have rolling 3 month if behavior is RETURN_NULL
    res_jan = res[res['YearMonth'] == '2023-01'].iloc[0]
    assert pd.isna(res_jan['ROLLING_3_MONTH_SUM'])


def test_rolling_calendar_period_unequal_months(date_engine, workspace):
    import pandas as pd
    import numpy as np
    df = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-31', '2023-02-28', '2023-03-31', '2023-04-30']),
        'Val': [10.0, 20.0, 30.0, 40.0]
    })
    path_d = workspace.project_root / "dates.csv"
    df.to_csv(path_d, index=False)
    safe_path = str(path_d).replace("'", "''")
    date_engine.duckdb_engine.conn.execute(f"CREATE OR REPLACE VIEW dates AS SELECT * FROM read_csv_auto('{safe_path}', header=True)")
    
    date_engine.register_metric(TimeMetricDefinition("rm3", "kpi", "ROLLING_3_MONTH", "RETURN_NULL"))
    
    res_pd = date_engine.calculate_time_metric_pandas(df, "Date", "Val", "rm3")
    res_ddb = date_engine.calculate_time_metric_duckdb("dates", "Date", "Val", "rm3")
    
    apr_val_pd = res_pd.loc[res_pd['YearMonth'] == '2023-04', 'ROLLING_3_MONTH_SUM'].values[0]
    apr_val_ddb = res_ddb.loc[res_ddb['YearMonth'] == '2023-04', 'ROLLING_3_MONTH_SUM'].values[0]
    
    assert np.isclose(apr_val_pd, 90.0)
    assert np.isclose(apr_val_ddb, 90.0)
