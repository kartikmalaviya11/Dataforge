import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Union, Tuple
from pathlib import Path
import pandas as pd
import numpy as np

from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine

@dataclass
class ExplicitThresholdRule:
    min_val: Optional[float]
    max_val: Optional[float]
    start_inclusive: bool = True
    end_inclusive: bool = False

@dataclass
class PercentileRule:
    min_pct: float
    max_pct: float
    start_inclusive: bool = True
    end_inclusive: bool = False

@dataclass
class SegmentDefinition:
    name: str
    rule: Union[ExplicitThresholdRule, PercentileRule]

@dataclass
class SegmentationConfig:
    table_name: str
    column_name: str
    segments: List[SegmentDefinition]

class SegmentationEngine:
    def __init__(self, workspace: ProjectWorkspace, engine: DuckDBEngine):
        self.workspace = workspace
        self.engine = engine

    def validate_config(self, config: SegmentationConfig) -> List[str]:
        warnings = []
        
        # Check overlaps and gaps
        # First, ensure we only compare apples to apples
        rule_types = {type(s.rule) for s in config.segments}
        if len(rule_types) > 1:
            raise ValueError("Cannot mix ExplicitThresholdRule and PercentileRule in the same config")
            
        if not config.segments:
            return warnings
            
        # We need a unified way to get bounds
        def get_bounds(rule):
            if isinstance(rule, ExplicitThresholdRule):
                return rule.min_val if rule.min_val is not None else float('-inf'), \
                       rule.max_val if rule.max_val is not None else float('inf'), \
                       rule.start_inclusive, rule.end_inclusive
            elif isinstance(rule, PercentileRule):
                return rule.min_pct, rule.max_pct, rule.start_inclusive, rule.end_inclusive
                
        bounds = [get_bounds(s.rule) for s in config.segments]
        # Sort by min val
        bounds.sort(key=lambda x: x[0])
        
        # Check overlap
        for i in range(len(bounds) - 1):
            curr_min, curr_max, curr_start_inc, curr_end_inc = bounds[i]
            next_min, next_max, next_start_inc, next_end_inc = bounds[i+1]
            
            # If curr_max > next_min, overlap
            if curr_max > next_min:
                raise ValueError(f"Segments overlap at {curr_max}")
            elif curr_max == next_min:
                if curr_end_inc and next_start_inc:
                    raise ValueError(f"Segments overlap exactly at boundary {curr_max} (both inclusive)")
                    
            # Check gap
            if curr_max < next_min:
                warnings.append(f"Gap detected between {curr_max} and {next_min}")
            elif curr_max == next_min and not curr_end_inc and not next_start_inc:
                warnings.append(f"Gap detected at exact boundary {curr_max} (both exclusive)")
                
        return warnings

    def save_config(self, name: str, config: SegmentationConfig):
        path = self.workspace.project_root / ".dataforge" / "segmentations.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {}
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                
        # Serialize config
        config_dict = {
            "table_name": config.table_name,
            "column_name": config.column_name,
            "segments": []
        }
        for seg in config.segments:
            rule_dict = asdict(seg.rule)
            rule_dict["__type__"] = seg.rule.__class__.__name__
            config_dict["segments"].append({
                "name": seg.name,
                "rule": rule_dict
            })
            
        data[name] = config_dict
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_config(self, name: str) -> SegmentationConfig:
        path = self.workspace.project_root / ".dataforge" / "segmentations.json"
        if not path.exists():
            raise FileNotFoundError("segmentations.json not found")
            
        with open(path, "r") as f:
            data = json.load(f)
            
        if name not in data:
            raise KeyError(f"Segmentation '{name}' not found")
            
        c = data[name]
        segments = []
        for s in c["segments"]:
            r = s["rule"]
            r_type = r.pop("__type__")
            if r_type == "ExplicitThresholdRule":
                rule = ExplicitThresholdRule(**r)
            elif r_type == "PercentileRule":
                rule = PercentileRule(**r)
            else:
                raise ValueError(f"Unknown rule type {r_type}")
            segments.append(SegmentDefinition(s["name"], rule))
            
        return SegmentationConfig(
            table_name=c["table_name"],
            column_name=c["column_name"],
            segments=segments
        )

    def apply_segmentation(self, config: SegmentationConfig, mode: str = "pandas") -> pd.DataFrame:
        if mode == "pandas":
            return self._apply_pandas(config)
        elif mode == "duckdb":
            return self._apply_duckdb(config)
        else:
            raise ValueError(f"Unknown mode {mode}")

    def _apply_pandas(self, config: SegmentationConfig) -> pd.DataFrame:
        df, _ = self.workspace.load_table(config.table_name)
        
        # We need a copy to not modify original if not desired, but let's just create a new series
        # or append 'segment'
        res = df.copy()
        res['segment'] = pd.Series(dtype='object')
        
        col = res[config.column_name]
        
        # If percentile rule, calculate values
        is_percentile = any(isinstance(s.rule, PercentileRule) for s in config.segments)
        
        for seg in config.segments:
            if isinstance(seg.rule, ExplicitThresholdRule):
                min_val = seg.rule.min_val if seg.rule.min_val is not None else float('-inf')
                max_val = seg.rule.max_val if seg.rule.max_val is not None else float('inf')
            else:
                # PercentileRule
                # Use interpolation linear to match DuckDB's percentile_cont
                # Percentiles from 0 to 100
                if seg.rule.min_pct == 0:
                    min_val = float('-inf')
                else:
                    min_val = col.quantile(seg.rule.min_pct / 100.0, interpolation='linear')
                
                if seg.rule.max_pct == 100:
                    max_val = float('inf')
                else:
                    max_val = col.quantile(seg.rule.max_pct / 100.0, interpolation='linear')
                    
            start_inc = seg.rule.start_inclusive
            end_inc = seg.rule.end_inclusive
            
            if start_inc and end_inc:
                mask = (col >= min_val) & (col <= max_val)
            elif start_inc and not end_inc:
                mask = (col >= min_val) & (col < max_val)
            elif not start_inc and end_inc:
                mask = (col > min_val) & (col <= max_val)
            else:
                mask = (col > min_val) & (col < max_val)
                
            res.loc[mask, 'segment'] = seg.name
            
        return res

    def _apply_duckdb(self, config: SegmentationConfig) -> pd.DataFrame:
        table_name = config.table_name
        col_name = config.column_name
        
        is_percentile = any(isinstance(s.rule, PercentileRule) for s in config.segments)
        
        # Base query to get data and compute percentiles if needed
        # To match pandas exactly with percentiles, we can use percentile_cont over a window.
        # However, percentile_cont over a window requires an OVER clause which DuckDB supports.
        
        cases = []
        
        if is_percentile:
            # We need to compute the quantiles first
            pcts = set()
            for seg in config.segments:
                if seg.rule.min_pct not in (0, 100):
                    pcts.add(seg.rule.min_pct / 100.0)
                if seg.rule.max_pct not in (0, 100):
                    pcts.add(seg.rule.max_pct / 100.0)
                    
            pcts_list = sorted(list(pcts))
            
            # Create a query to get percentiles
            if pcts_list:
                pct_exprs = ", ".join(f"quantile_cont(\"{col_name}\", {p}) as pct_{i}" for i, p in enumerate(pcts_list))
                pct_query = f"SELECT {pct_exprs} FROM \"{table_name}\""
                pct_df = self.engine.conn.execute(pct_query).fetchdf()
                
                # Map pcts back
                pct_map = {p: pct_df.iloc[0][f"pct_{i}"] for i, p in enumerate(pcts_list)}
            else:
                pct_map = {}
                
            # Now build cases using actual evaluated percentiles
            for seg in config.segments:
                if seg.rule.min_pct == 0:
                    min_val = -float('inf')
                else:
                    min_val = pct_map[seg.rule.min_pct / 100.0]
                    
                if seg.rule.max_pct == 100:
                    max_val = float('inf')
                else:
                    max_val = pct_map[seg.rule.max_pct / 100.0]
                    
                start_op = ">=" if seg.rule.start_inclusive else ">"
                end_op = "<=" if seg.rule.end_inclusive else "<"
                
                # Build SQL conditions
                conds = []
                if min_val != -float('inf'):
                    conds.append(f'"{col_name}" {start_op} {min_val}')
                if max_val != float('inf'):
                    conds.append(f'"{col_name}" {end_op} {max_val}')
                    
                if not conds:
                    case_when = "WHEN True"
                else:
                    case_when = "WHEN " + " AND ".join(conds)
                
                cases.append(f"{case_when} THEN '{seg.name}'")
        else:
            for seg in config.segments:
                conds = []
                if seg.rule.min_val is not None:
                    start_op = ">=" if seg.rule.start_inclusive else ">"
                    conds.append(f'"{col_name}" {start_op} {seg.rule.min_val}')
                if seg.rule.max_val is not None:
                    end_op = "<=" if seg.rule.end_inclusive else "<"
                    conds.append(f'"{col_name}" {end_op} {seg.rule.max_val}')
                    
                if not conds:
                    case_when = "WHEN True"
                else:
                    case_when = "WHEN " + " AND ".join(conds)
                cases.append(f"{case_when} THEN '{seg.name}'")
                
        case_stmt = "CASE " + " ".join(cases) + " ELSE NULL END"
        
        sql = f"""
        SELECT *,
               {case_stmt} as segment
        FROM "{table_name}"
        """
        
        return self.engine.conn.execute(sql).fetchdf()

