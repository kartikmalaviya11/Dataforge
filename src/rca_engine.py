import json
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import pandas as pd

from src.workspace import ProjectWorkspace
from src.kpi_engine import KPIManager
from src.data_model import DataModel, RelationshipStatus
from src.sql_engine import DuckDBEngine

class AmbiguousRCAPathError(Exception):
    pass

class MissingRCAPathError(Exception):
    pass


@dataclass
class RCACondition:
    column: str
    operator: str  # 'EQUALS', 'NOT_EQUALS', 'GREATER_THAN', 'LESS_THAN_OR_EQUAL', 'IN', 'IS_NULL', 'IS_NOT_NULL'
    value: Any
    logical_operator: Optional[str] = None  # 'AND', 'OR' (for chaining)

    def __post_init__(self):
        allowed = {"EQUALS", "NOT_EQUALS", "GREATER_THAN", "LESS_THAN", "GREATER_THAN_OR_EQUAL", "LESS_THAN_OR_EQUAL", "IN", "IS_NULL", "IS_NOT_NULL"}
        if self.operator.upper() not in allowed:
            raise ValueError(f"Invalid RCA operator: {self.operator}")
        if self.logical_operator and self.logical_operator.upper() not in {"AND", "OR"}:
            raise ValueError(f"Invalid logical operator: {self.logical_operator}")

    def to_sql(self, table: str) -> str:
        op = self.operator.upper()
        if op == "EQUALS": sql_op = "="
        elif op == "NOT_EQUALS": sql_op = "!="
        elif op == "GREATER_THAN": sql_op = ">"
        elif op == "LESS_THAN_OR_EQUAL": sql_op = "<="
        elif op == "LESS_THAN": sql_op = "<"
        elif op == "GREATER_THAN_OR_EQUAL": sql_op = ">="
        elif op == "IN": sql_op = "IN"
        elif op == "IS_NULL": return f'"{table}"."{self.column}" IS NULL'
        elif op == "IS_NOT_NULL": return f'"{table}"."{self.column}" IS NOT NULL'
        else: sql_op = "="

        if sql_op == "IN":
            # value should be a list
            vals = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in self.value])
            return f'"{table}"."{self.column}" IN ({vals})'
        else:
            v = f"'{self.value}'" if isinstance(self.value, str) else str(self.value)
            return f'"{table}"."{self.column}" {sql_op} {v}'


@dataclass
class RCAAnalysisDefinition:
    analysis_id: str
    problem_definition: str
    source_table: str
    target_metric_kpi_id: str
    affected_conditions: List[RCACondition]
    baseline_type: str
    dimension_table: str
    dimension_column: str
    minimum_affected_sample_size: int = 30
    minimum_baseline_sample_size: int = 30
    missing_value_behavior: str = "EXCLUDE"
    custom_baseline_conditions: Optional[List[RCACondition]] = None
    created_at: float = 0.0

@dataclass
class RCAGroupResult:
    dimension_value: Any
    affected_metric_value: Optional[float]
    baseline_metric_value: Optional[float]
    absolute_difference: Optional[float]
    relative_difference_pct: Optional[float]
    affected_sample_size: int
    baseline_sample_size: int
    association_classification: str


class RCAEngine:
    def __init__(self, workspace: ProjectWorkspace, data_model: DataModel, kpi_manager: KPIManager):
        self.workspace = workspace
        self.data_model = data_model
        self.kpi_manager = kpi_manager
        self.duckdb = DuckDBEngine(workspace)

    def _find_shortest_path(self, source: str, target: str) -> List[Any]:
        if source == target:
            return []
            
        queue = [(source, [])]
        visited = set()
        paths = []
        shortest_len = float('inf')
        
        while queue:
            current, path = queue.pop(0)
            
            if len(path) > shortest_len:
                continue
                
            if current == target:
                if len(path) < shortest_len:
                    shortest_len = len(path)
                    paths = [path]
                elif len(path) == shortest_len:
                    paths.append(path)
                continue
                
            visited.add(current)
                
            for rel in self.data_model.relationships:
                if rel.status != RelationshipStatus.ACCEPTED:
                    continue
                    
                nxt = None
                if rel.source_table == current:
                    nxt = rel.target_table
                elif rel.target_table == current:
                    nxt = rel.source_table
                    
                if nxt and nxt not in [p_node for p_rel, p_node in path]:
                    queue.append((nxt, path + [(rel, current)]))
                    
        if not paths:
            raise MissingRCAPathError(f"No valid relationship path between {source} and {target}")
        if len(paths) > 1:
            raise AmbiguousRCAPathError(f"Ambiguous relationships: multiple shortest paths between {source} and {target}")
            
        return [rel for rel, _ in paths[0]]

    def _build_conditions_sql(self, conditions: List[RCACondition], table: str) -> str:
        if not conditions:
            return "1=1"
        sqls = []
        for i, c in enumerate(conditions):
            c_sql = c.to_sql(table)
            if i > 0 and c.logical_operator:
                sqls.append(f" {c.logical_operator} {c_sql}")
            elif i > 0:
                sqls.append(f" AND {c_sql}")
            else:
                sqls.append(c_sql)
        return "".join(sqls)

    def execute(self, definition: RCAAnalysisDefinition) -> List[RCAGroupResult]:
        kpi = next((k for k in self.kpi_manager.load_kpis() if k.kpi_id == definition.target_metric_kpi_id), None)
        if not kpi or not kpi.metric_definitions:
            raise ValueError(f"KPI {definition.target_metric_kpi_id} not found or has no metric definitions")
            
        met_table = kpi.metric_definitions[0].source_table
        dim_table = definition.dimension_table
        cond_table = definition.source_table
        
        required_tables = {met_table, dim_table, cond_table}
        
        edges_to_join = set()
        base_t = met_table
        for t in required_tables:
            if t != base_t:
                path = self._find_shortest_path(base_t, t)
                for rel in path:
                    edges_to_join.add((rel.source_table, rel.source_column, rel.target_table, rel.target_column))
                    
        joined_tables = {base_t}
        join_clauses = []
        edges = list(edges_to_join)
        
        while edges:
            progress = False
            for i in range(len(edges)-1, -1, -1):
                src_t, src_c, tgt_t, tgt_c = edges[i]
                if src_t in joined_tables and tgt_t not in joined_tables:
                    join_clauses.append(f'JOIN "{tgt_t}" ON "{src_t}"."{src_c}" = "{tgt_t}"."{tgt_c}"')
                    joined_tables.add(tgt_t)
                    edges.pop(i)
                    progress = True
                elif tgt_t in joined_tables and src_t not in joined_tables:
                    join_clauses.append(f'JOIN "{src_t}" ON "{tgt_t}"."{tgt_c}" = "{src_t}"."{src_c}"')
                    joined_tables.add(src_t)
                    edges.pop(i)
                    progress = True
                elif src_t in joined_tables and tgt_t in joined_tables:
                    join_clauses.append(f'JOIN "{tgt_t}" ON "{src_t}"."{src_c}" = "{tgt_t}"."{tgt_c}"')
                    edges.pop(i)
                    progress = True
            if not progress:
                break
                
        from_clause = f'FROM "{base_t}" ' + " ".join(join_clauses)
        
        aff_sql = self._build_conditions_sql(definition.affected_conditions, cond_table)
        
        if definition.baseline_type == "BASELINE_ALL":
            base_sql = "1=1"
        elif definition.baseline_type == "BASELINE_COMPLEMENT":
            base_sql = f"NOT ({aff_sql})"
        elif definition.baseline_type == "BASELINE_CUSTOM":
            base_sql = self._build_conditions_sql(definition.custom_baseline_conditions, cond_table)
        else:
            base_sql = "1=1"
            
        dim_col_full = f'"{dim_table}"."{definition.dimension_column}"'
        met_col_full = f'"{met_table}"."{kpi.metric_definitions[0].source_column}"'
        operation = kpi.metric_definitions[0].operation
        
        sql = f"""
        SELECT 
            {dim_col_full} as dimension_value,
            COUNT(CASE WHEN {aff_sql} THEN 1 END) as affected_sample_size,
            COUNT(CASE WHEN {base_sql} THEN 1 END) as baseline_sample_size,
            {operation}(CASE WHEN {aff_sql} THEN {met_col_full} END) as affected_metric_value,
            {operation}(CASE WHEN {base_sql} THEN {met_col_full} END) as baseline_metric_value
        {from_clause}
        """
        
        if definition.missing_value_behavior == "EXCLUDE":
            sql += f" WHERE {dim_col_full} IS NOT NULL"
            
        sql += f" GROUP BY 1"
        
        df = self.duckdb.execute_query(sql)
        
        results = []
        for _, row in df.iterrows():
            aff_size = int(row['affected_sample_size']) if pd.notnull(row['affected_sample_size']) else 0
            base_size = int(row['baseline_sample_size']) if pd.notnull(row['baseline_sample_size']) else 0
            
            aff_val = float(row['affected_metric_value']) if pd.notnull(row['affected_metric_value']) else None
            base_val = float(row['baseline_metric_value']) if pd.notnull(row['baseline_metric_value']) else None
            
            abs_diff = None
            rel_diff = None
            
            if aff_val is not None and base_val is not None:
                abs_diff = aff_val - base_val
                if base_val != 0:
                    rel_diff = (abs_diff / abs(base_val)) * 100.0
                    
            # Classification
            if aff_size < definition.minimum_affected_sample_size or base_size < definition.minimum_baseline_sample_size:
                classification = "Insufficient Evidence"
            else:
                if rel_diff is not None:
                    if abs(rel_diff) > 50.0:
                        classification = "Large Observed Association"
                    elif abs(rel_diff) > 10.0:
                        classification = "Observed Association"
                    else:
                        classification = "Insufficient Evidence"
                else:
                    classification = "Insufficient Evidence"
                    
            results.append(RCAGroupResult(
                dimension_value=row['dimension_value'],
                affected_metric_value=aff_val,
                baseline_metric_value=base_val,
                absolute_difference=abs_diff,
                relative_difference_pct=rel_diff,
                affected_sample_size=aff_size,
                baseline_sample_size=base_size,
                association_classification=classification
            ))
            
        return results

    def save_analysis(self, config: RCAAnalysisDefinition):
        import json
        import os
        from dataclasses import asdict
        path = os.path.join(self.workspace.project_root, ".dataforge", "rca_analyses.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        analyses = self.load_analyses()
        analyses = [a for a in analyses if a.analysis_id != config.analysis_id]
        analyses.append(config)
        with open(path, "w") as f:
            json.dump([asdict(a) for a in analyses], f, indent=2)

    def load_analyses(self) -> List[RCAAnalysisDefinition]:
        import json
        import os
        path = os.path.join(self.workspace.project_root, ".dataforge", "rca_analyses.json")
        if not os.path.exists(path):
            return []
        with open(path, "r") as f:
            data = json.load(f)
        res = []
        for d in data:
            d["affected_conditions"] = [RCACondition(**c) for c in d.get("affected_conditions", [])]
            if d.get("custom_baseline_conditions"):
                d["custom_baseline_conditions"] = [RCACondition(**c) for c in d["custom_baseline_conditions"]]
            res.append(RCAAnalysisDefinition(**d))
        return res

