import json
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import List, Optional, Any, Dict
from datetime import datetime
from pathlib import Path

from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine

@dataclass
class OutlierAnalysisDefinition:
    table_name: str
    column_name: str
    method: str  # "IQR" or "Z-Score"
    threshold: float

@dataclass
class OutlierRecord:
    value: float

@dataclass
class OutlierAnalysisResult:
    definition: Optional[OutlierAnalysisDefinition]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    outliers: List[OutlierRecord]
    analyzed_at: str

class AnomalyEngine:
    def __init__(self, workspace: ProjectWorkspace, duckdb_engine: DuckDBEngine):
        self.workspace = workspace
        self.duckdb_engine = duckdb_engine
        self.persist_dir = self.workspace.project_root / ".dataforge"
        self.persist_file = self.persist_dir / "outlier_analyses.json"

    def analyze(self, definition: OutlierAnalysisDefinition, use_duckdb: bool = True) -> OutlierAnalysisResult:
        if definition.method.upper() == "IQR":
            if use_duckdb:
                result = self._detect_iqr_duckdb(definition.table_name, definition.column_name, definition.threshold)
            else:
                df, _ = self.workspace.load_table(definition.table_name)
                result = self._detect_iqr_pandas(df, definition.column_name, definition.threshold)
        elif definition.method.upper() in ["Z-SCORE", "ZSCORE"]:
            if use_duckdb:
                result = self._detect_zscore_duckdb(definition.table_name, definition.column_name, definition.threshold)
            else:
                df, _ = self.workspace.load_table(definition.table_name)
                result = self._detect_zscore_pandas(df, definition.column_name, definition.threshold)
        else:
            raise ValueError(f"Unknown method {definition.method}")
            
        result.definition = definition
        self._persist_result(result)
        return result

    def _persist_result(self, result: OutlierAnalysisResult):
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        data = []
        if self.persist_file.exists():
            try:
                with open(self.persist_file, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
                
        # Append as dict
        data.append(asdict(result))
        
        with open(self.persist_file, "w") as f:
            json.dump(data, f, indent=2)

    def _detect_iqr_duckdb(self, table_name: str, column_name: str, threshold: float) -> OutlierAnalysisResult:
        query = f"""
            SELECT 
                COUNT("{column_name}") as n,
                quantile_cont("{column_name}"::DOUBLE, 0.25) as q1,
                quantile_cont("{column_name}"::DOUBLE, 0.75) as q3
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
        """
        stats_df = self.duckdb_engine.execute_query(query)
        if stats_df.empty or stats_df['n'].iloc[0] == 0:
            return OutlierAnalysisResult(None, None, None, [], datetime.now().isoformat())
            
        q1 = float(stats_df['q1'].iloc[0])
        q3 = float(stats_df['q3'].iloc[0])
        iqr = q3 - q1
        lower_bound = q1 - (threshold * iqr)
        upper_bound = q3 + (threshold * iqr)
        
        outliers_query = f"""
            SELECT "{column_name}" as val
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
              AND ("{column_name}"::DOUBLE < {lower_bound} OR "{column_name}"::DOUBLE > {upper_bound})
        """
        outliers_df = self.duckdb_engine.execute_query(outliers_query)
        outliers = [OutlierRecord(float(v)) for v in outliers_df['val'].tolist()]
        
        return OutlierAnalysisResult(
            definition=None, 
            lower_bound=lower_bound, 
            upper_bound=upper_bound, 
            outliers=outliers, 
            analyzed_at=datetime.now().isoformat()
        )

    def _detect_iqr_pandas(self, df: pd.DataFrame, column_name: str, threshold: float) -> OutlierAnalysisResult:
        s = df[column_name].dropna()
        if len(s) == 0:
            return OutlierAnalysisResult(None, None, None, [], datetime.now().isoformat())
            
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        lower_bound = float(q1 - (threshold * iqr))
        upper_bound = float(q3 + (threshold * iqr))
        
        outliers_s = s[(s < lower_bound) | (s > upper_bound)]
        outliers = [OutlierRecord(float(v)) for v in outliers_s]
        
        return OutlierAnalysisResult(
            definition=None, 
            lower_bound=lower_bound, 
            upper_bound=upper_bound, 
            outliers=outliers, 
            analyzed_at=datetime.now().isoformat()
        )

    def _detect_zscore_duckdb(self, table_name: str, column_name: str, threshold: float) -> OutlierAnalysisResult:
        query = f"""
            SELECT 
                COUNT("{column_name}") as n,
                AVG("{column_name}"::DOUBLE) as mean_val,
                STDDEV_SAMP("{column_name}"::DOUBLE) as std_val
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
        """
        stats_df = self.duckdb_engine.execute_query(query)
        if stats_df.empty or stats_df['n'].iloc[0] == 0:
            return OutlierAnalysisResult(None, None, None, [], datetime.now().isoformat())
            
        n = stats_df['n'].iloc[0]
        mean_val = float(stats_df['mean_val'].iloc[0])
        
        std_val = stats_df['std_val'].iloc[0]
        if pd.isna(std_val) or n < 2 or std_val == 0:
            return OutlierAnalysisResult(None, mean_val, mean_val, [], datetime.now().isoformat())
            
        std_val = float(std_val)
        lower_bound = mean_val - (threshold * std_val)
        upper_bound = mean_val + (threshold * std_val)
        
        outliers_query = f"""
            SELECT "{column_name}" as val
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
              AND ("{column_name}"::DOUBLE < {lower_bound} OR "{column_name}"::DOUBLE > {upper_bound})
        """
        outliers_df = self.duckdb_engine.execute_query(outliers_query)
        outliers = [OutlierRecord(float(v)) for v in outliers_df['val'].tolist()]
        
        return OutlierAnalysisResult(
            definition=None, 
            lower_bound=lower_bound, 
            upper_bound=upper_bound, 
            outliers=outliers, 
            analyzed_at=datetime.now().isoformat()
        )

    def _detect_zscore_pandas(self, df: pd.DataFrame, column_name: str, threshold: float) -> OutlierAnalysisResult:
        s = df[column_name].dropna()
        n = len(s)
        if n == 0:
            return OutlierAnalysisResult(None, None, None, [], datetime.now().isoformat())
            
        mean_val = s.mean()
        std_val = s.std(ddof=1)
        
        if pd.isna(std_val) or n < 2 or std_val == 0:
            return OutlierAnalysisResult(None, float(mean_val), float(mean_val), [], datetime.now().isoformat())
            
        lower_bound = float(mean_val - (threshold * std_val))
        upper_bound = float(mean_val + (threshold * std_val))
        
        outliers_s = s[(s < lower_bound) | (s > upper_bound)]
        outliers = [OutlierRecord(float(v)) for v in outliers_s]
        
        return OutlierAnalysisResult(
            definition=None, 
            lower_bound=lower_bound, 
            upper_bound=upper_bound, 
            outliers=outliers, 
            analyzed_at=datetime.now().isoformat()
        )
