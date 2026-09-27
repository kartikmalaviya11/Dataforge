from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np
import json
from pathlib import Path

from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine

@dataclass
class DateDimensionConfig:
    config_id: str
    source_table: str
    date_column: str
    user_min_date: Optional[str]
    user_max_date: Optional[str]
    missing_date_behavior: str

@dataclass
class DateTableMetadata:
    derived_min_date: str
    derived_max_date: str
    total_days: int
    last_generated_at: float

@dataclass
class TimeMetricDefinition:
    metric_id: str
    base_kpi_id: str
    time_comparison: str
    insufficient_history_behavior: str

class DateAnalysisEngine:
    def __init__(self, workspace: ProjectWorkspace, duckdb_engine: DuckDBEngine):
        self.workspace = workspace
        self.duckdb_engine = duckdb_engine
        self.configs: Dict[str, DateDimensionConfig] = {}
        self.metrics: Dict[str, TimeMetricDefinition] = {}
        self.metadata: Dict[str, DateTableMetadata] = {}
        self._config_path = self.workspace.project_root / ".dataforge" / "date_configs.json"
        self._load_configs()

    def _load_configs(self):
        if not self._config_path.exists():
            return
            
        with open(self._config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for conf in data.get('configs', []):
            c = DateDimensionConfig(**conf)
            self.configs[c.config_id] = c
            
        for met in data.get('metrics', []):
            m = TimeMetricDefinition(**met)
            self.metrics[m.metric_id] = m
            
        for meta in data.get('metadata', []):
            pass

    def _save_configs(self):
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'configs': [asdict(c) for c in self.configs.values()],
            'metrics': [asdict(m) for m in self.metrics.values()],
            'metadata': {k: asdict(v) for k, v in self.metadata.items()}
        }
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def register_config(self, config: DateDimensionConfig):
        self.configs[config.config_id] = config
        self._save_configs()

    def register_metric(self, metric: TimeMetricDefinition):
        self.metrics[metric.metric_id] = metric
        self._save_configs()

    def generate_date_table_pandas(self, config_id: str) -> pd.DataFrame:
        config = self.configs[config_id]
        df_source = self.duckdb_engine.conn.execute(f'SELECT "{config.date_column}" FROM "{config.source_table}"').fetchdf()
        
        dates = pd.to_datetime(df_source[config.date_column], errors='coerce')
        valid_dates = dates.dropna()
        
        if valid_dates.empty:
            min_d, max_d = pd.Timestamp('2000-01-01'), pd.Timestamp('2000-01-01')
        else:
            min_d, max_d = valid_dates.min(), valid_dates.max()
            
        if config.user_min_date: min_d = pd.Timestamp(config.user_min_date)
        if config.user_max_date: max_d = pd.Timestamp(config.user_max_date)
            
        date_range = pd.date_range(min_d, max_d, freq='D')
        df = pd.DataFrame({'Date': date_range})
        df['Year'] = df['Date'].dt.year.astype('Int64')
        df['Month'] = df['Date'].dt.month.astype('Int64')
        df['Day'] = df['Date'].dt.day.astype('Int64')
        df['ISO_Year'] = df['Date'].dt.isocalendar().year.astype('Int64')
        df['ISO_Week'] = df['Date'].dt.isocalendar().week.astype('Int64')
        return df

    def generate_date_table_duckdb(self, config_id: str) -> pd.DataFrame:
        config = self.configs[config_id]
        q = f"""
        WITH min_max AS (
            SELECT MIN(TRY_CAST("{config.date_column}" AS DATE)) as min_d,
                   MAX(TRY_CAST("{config.date_column}" AS DATE)) as max_d
            FROM "{config.source_table}"
        )
        SELECT 
            d.date AS Date,
            EXTRACT(YEAR FROM d.date)::BIGINT AS Year,
            EXTRACT(MONTH FROM d.date)::BIGINT AS Month,
            EXTRACT(DAY FROM d.date)::BIGINT AS Day,
            EXTRACT(ISOYEAR FROM d.date)::BIGINT AS ISO_Year,
            EXTRACT(WEEK FROM d.date)::BIGINT AS ISO_Week
        FROM (SELECT CAST(min_d + INTERVAL (i) DAY AS TIMESTAMP) as date FROM min_max, generate_series(0, DATE_DIFF('day', min_d, max_d)) as s(i)) d
        ORDER BY d.date ASC
        """
        return self.duckdb_engine.conn.execute(q).fetchdf()

    def calculate_time_metric_pandas(self, df: pd.DataFrame, date_col: str, val_col: str, metric_id: str) -> pd.DataFrame:
        metric = self.metrics[metric_id]
        df = df.copy()
        df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['Date'])
        df['YearMonth'] = df['Date'].dt.to_period('M')
        monthly = df.groupby('YearMonth')[val_col].sum().reset_index().sort_values('YearMonth')
        
        if metric.time_comparison == 'MoM':
            monthly['prev_val'] = monthly[val_col].shift(1)
            monthly['MoM_Growth'] = np.where(monthly['prev_val'] != 0, (monthly[val_col] - monthly['prev_val']) / monthly['prev_val'], np.nan)
            monthly['YearMonth'] = monthly['YearMonth'].dt.strftime('%Y-%m')
            return monthly
        elif metric.time_comparison == 'YoY':
            all_months = pd.period_range(monthly['YearMonth'].min(), monthly['YearMonth'].max(), freq='M')
            monthly = monthly.set_index('YearMonth').reindex(all_months).fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
            monthly['prev_val'] = monthly[val_col].shift(12)
            monthly['YoY_Growth'] = np.where(monthly['prev_val'] != 0, (monthly[val_col] - monthly['prev_val']) / monthly['prev_val'], np.nan)
            monthly['YearMonth'] = monthly['YearMonth'].dt.strftime('%Y-%m')
            return monthly
        elif metric.time_comparison.startswith('ROLLING_'):
            months = int(metric.time_comparison.split('_')[1])
            all_months = pd.period_range(monthly['YearMonth'].min(), monthly['YearMonth'].max(), freq='M')
            monthly = monthly.set_index('YearMonth').reindex(all_months).fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
            monthly[f'ROLLING_{months}_MONTH_SUM'] = monthly[val_col].rolling(window=months, min_periods=months).sum()
            monthly['YearMonth'] = monthly['YearMonth'].dt.strftime('%Y-%m')
            return monthly
        return monthly

    def calculate_time_metric_duckdb(self, table_name: str, date_col: str, val_col: str, metric_id: str) -> pd.DataFrame:
        metric = self.metrics[metric_id]
        q_monthly = f"""
        WITH monthly AS (
            SELECT strftime(TRY_CAST("{date_col}" AS DATE), '%Y-%m') AS YearMonth, SUM("{val_col}") AS sum_val
            FROM "{table_name}" WHERE TRY_CAST("{date_col}" AS DATE) IS NOT NULL GROUP BY 1
        ),
        date_series AS (
            SELECT strftime(CAST(min_d + INTERVAL (i) MONTH AS DATE), '%Y-%m') AS YearMonth
            FROM (SELECT date_trunc('month', MIN(TRY_CAST("{date_col}" AS DATE))) as min_d, date_trunc('month', MAX(TRY_CAST("{date_col}" AS DATE))) as max_d FROM "{table_name}") limits,
            generate_series(0, CAST((EXTRACT(YEAR FROM max_d) - EXTRACT(YEAR FROM min_d)) * 12 + (EXTRACT(MONTH FROM max_d) - EXTRACT(MONTH FROM min_d)) AS INTEGER)) as s(i)
        ),
        filled AS (
            SELECT d.YearMonth, COALESCE(m.sum_val, 0.0) as val FROM date_series d LEFT JOIN monthly m ON d.YearMonth = m.YearMonth
        )
        """
        
        if metric.time_comparison == 'MoM':
            q = q_monthly + " SELECT YearMonth, val, lag(val, 1) OVER (ORDER BY YearMonth) as prev_val, CASE WHEN lag(val, 1) OVER (ORDER BY YearMonth) != 0 THEN (val - lag(val, 1) OVER (ORDER BY YearMonth)) / lag(val, 1) OVER (ORDER BY YearMonth) ELSE NULL END as MoM_Growth FROM filled ORDER BY YearMonth"
        elif metric.time_comparison == 'YoY':
            q = q_monthly + " SELECT YearMonth, val, lag(val, 12) OVER (ORDER BY YearMonth) as prev_val, CASE WHEN lag(val, 12) OVER (ORDER BY YearMonth) != 0 THEN (val - lag(val, 12) OVER (ORDER BY YearMonth)) / lag(val, 12) OVER (ORDER BY YearMonth) ELSE NULL END as YoY_Growth FROM filled ORDER BY YearMonth"
        elif metric.time_comparison.startswith('ROLLING_'):
            months = int(metric.time_comparison.split('_')[1])
            q = q_monthly + f" SELECT YearMonth, val, SUM(val) OVER (ORDER BY YearMonth ROWS BETWEEN {months - 1} PRECEDING AND CURRENT ROW) as rolling_sum, COUNT(val) OVER (ORDER BY YearMonth ROWS BETWEEN {months - 1} PRECEDING AND CURRENT ROW) as rolling_cnt FROM filled ORDER BY YearMonth"
            df = self.duckdb_engine.conn.execute(q).fetchdf()
            df[f'ROLLING_{months}_MONTH_SUM'] = np.where(df['rolling_cnt'] == months, df['rolling_sum'], np.nan)
            df = df.drop(columns=['rolling_sum', 'rolling_cnt'])
            return df
        return self.duckdb_engine.conn.execute(q).fetchdf()
