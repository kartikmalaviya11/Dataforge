"""
Phase 12: SQL Analyzer

Embedded SQL analysis layer using DuckDB.
Reproduces Data Quality and KPI aggregations via ANSI SQL to validate Python pipeline correctness.
"""

from dataclasses import dataclass
from typing import Any, Optional, Dict, List
import math
import duckdb
import pandas as pd
from loguru import logger

from .kpi_engine import KPIRecommendation

@dataclass
class SQLAnalysisResult:
    query_name: str
    python_result: Any
    sql_result: Any
    difference: Any
    match_status: str
    sql: str
    notes: str = ""

def _compare_values(python_val: Any, sql_val: Any, tolerance: float = 1e-5) -> tuple[bool, Any]:
    """
    Centralized comparison logic.
    - If None, both must be None.
    - If Numeric, match using math.isclose for floating points.
    - If String/Bool, exact match.
    Returns: (is_match, difference)
    """
    if python_val is None and sql_val is None:
        return True, 0
    if python_val is None or sql_val is None:
        return False, None
        
    try:
        # Check if both can be treated as numeric
        try:
            py_f = float(python_val)
            sql_f = float(sql_val)
            is_numeric = True
        except (ValueError, TypeError):
            is_numeric = False
            
        if is_numeric:
            diff = abs(py_f - sql_f)
            
            # Handle NaNs safely
            if math.isnan(py_f) and math.isnan(sql_f):
                return True, 0.0
                
            # Exact match (for ints or exact floats)
            if py_f == sql_f:
                return True, diff
                
            # Use math.isclose to handle both relative and absolute differences for large/small numbers
            is_match = math.isclose(py_f, sql_f, rel_tol=1e-5, abs_tol=1e-5)
            return is_match, diff
            
        # String or other exact matches
        return str(python_val) == str(sql_val), None
        
    except Exception as e:
        logger.warning(f"Comparison error: {e}")
        return False, None

def _safe_quote(identifier: str) -> str:
    """Safely quote column identifiers for DuckDB to prevent injection and handle special chars."""
    # Escape existing double quotes by doubling them
    safe_id = str(identifier).replace('"', '""')
    return f'"{safe_id}"'


class SQLAnalyzer:
    def __init__(self, df: pd.DataFrame, table_name: str = "dataset"):
        self.table_name = "dataset" # Hardcoded to 'dataset' per requirements
        self.conn = duckdb.connect(database=':memory:')
        # Register the pandas dataframe explicitly. DuckDB can query 'df' natively, 
        # but registering it ensures it's consistently named as requested.
        self.conn.register(self.table_name, df)
        self.df = df
        
    def _execute(self, query: str) -> Any:
        """Executes a scalar query and returns the single value."""
        try:
            result = self.conn.execute(query).fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"SQL execution failed: {query}\nError: {e}")
            return None

    def compare(self, name: str, python_result: Any, sql_query: str) -> SQLAnalysisResult:
        """Run SQL and compare against python_result."""
        sql_result = self._execute(sql_query)
        is_match, diff = _compare_values(python_result, sql_result)
        
        return SQLAnalysisResult(
            query_name=name,
            python_result=python_result,
            sql_result=sql_result,
            difference=diff,
            match_status="MATCH" if is_match else "MISMATCH",
            sql=sql_query,
            notes="Tolerance: 1e-9" if isinstance(python_result, float) else "Exact match"
        )

    # ─── Data Quality SQL Queries ───────────────────────────────────────────
    
    def check_missing_values(self, column: str, python_count: int) -> SQLAnalysisResult:
        col = _safe_quote(column)
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE {col} IS NULL"
        return self.compare(f"Missing Values ({column})", python_count, query)
        
    def check_blank_values(self, column: str, python_count: int) -> SQLAnalysisResult:
        col = _safe_quote(column)
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE {col} IS NOT NULL AND TRIM({col}::VARCHAR) = ''"
        return self.compare(f"Blank Values ({column})", python_count, query)
        
    def check_duplicate_rows(self, python_count: int) -> SQLAnalysisResult:
        # Phase 4 keeps first occurrence and flags subsequent copies.
        # This matches sum(count - 1) for all groups with count > 1.
        group_cols = ", ".join(_safe_quote(c) for c in self.df.columns)
        query = (
            f"SELECT COALESCE(SUM(cnt - 1)::INT, 0) FROM ("
            f"  SELECT COUNT(*) as cnt FROM {self.table_name} "
            f"  GROUP BY {group_cols} HAVING COUNT(*) > 1"
            f")"
        )
        # duckdb returns a huge integer type, we ensure we compare it natively
        return self.compare("Duplicate Rows", python_count, query)

    def check_duplicate_ids(self, column: str, python_count: int) -> SQLAnalysisResult:
        # Phase 4 uses keep=False on non-null values. Meaning ALL rows with a shared ID are flagged.
        col = _safe_quote(column)
        query = (
            f"SELECT COUNT(*) FROM {self.table_name} "
            f"WHERE {col} IS NOT NULL AND {col} IN ("
            f"  SELECT {col} FROM {self.table_name} "
            f"  WHERE {col} IS NOT NULL "
            f"  GROUP BY {col} HAVING COUNT(*) > 1"
            f")"
        )
        return self.compare(f"Duplicate IDs ({column})", python_count, query)
        
    def check_range(self, column: str, min_val: float, max_val: float, python_count: int) -> SQLAnalysisResult:
        col = _safe_quote(column)
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE {col} IS NOT NULL AND ({col} < {min_val} OR {col} > {max_val})"
        return self.compare(f"Range Violation ({column})", python_count, query)

    # ─── KPI Aggregation SQL Queries ────────────────────────────────────────

    def aggregate_kpi(self, kpi: KPIRecommendation, python_result: Any = None) -> SQLAnalysisResult:
        """Dynamically builds an aggregate SQL query mirroring a KPIRecommendation."""
        if kpi.status == "UNAVAILABLE":
            return SQLAnalysisResult(
                query_name=kpi.kpi_name,
                python_result="NOT_AVAILABLE",
                sql_result="NOT_AVAILABLE",
                difference=None,
                match_status="NOT_AVAILABLE",
                sql="SELECT NULL"
            )
            
        if " grouped by " in kpi.calculation_logic:
            return SQLAnalysisResult(
                query_name=kpi.kpi_name,
                python_result="NOT_AVAILABLE",
                sql_result="NOT_AVAILABLE",
                difference=None,
                match_status="NOT_AVAILABLE",
                sql="-- Grouped KPI comparison not supported",
                notes="Grouped KPI that is not currently compared at grouped-result level"
            )
            
        # Compute python_result dynamically if not provided
        if python_result is None:
            def _eval_agg(expr: str):
                import re
                import pandas as pd
                match = re.match(r'^([A-Z]+)\(([^)]+)\)$', expr.strip())
                if not match:
                    return None
                func = match.group(1)
                col_raw = match.group(2).strip()
                if col_raw.startswith('[') and col_raw.endswith(']'):
                    col = col_raw[1:-1]
                else:
                    col = col_raw
                if col not in self.df.columns:
                    return None
                series = pd.to_numeric(self.df[col], errors='coerce') if func in ('SUM', 'AVERAGE') else self.df[col]
                if func == 'SUM':
                    return float(series.sum())
                elif func == 'AVERAGE':
                    return float(series.mean())
                elif func == 'DISTINCTCOUNT':
                    return int(series.nunique())
                return None

            logic_eval = kpi.calculation_logic.split(" grouped by ")[0].strip()
            if " / " in logic_eval:
                parts = logic_eval.split(" / ")
                num_val = _eval_agg(parts[0])
                den_val = _eval_agg(parts[1])
                if num_val is not None and den_val is not None and den_val != 0:
                    python_result = num_val / den_val
            else:
                python_result = _eval_agg(logic_eval)
            
            if python_result is None:
                python_result = "NOT_AVAILABLE"

        # Parse calculation logic into SQL safely
        # Note: Phase 11 DAX logic parser is very similar, but we produce ANSI SQL here.
        logic = kpi.calculation_logic
        
        if " / " in logic:
            parts = logic.split(" / ")
            num_sql = self._parse_agg(parts[0].strip(), kpi.available_columns)
            den_sql = self._parse_agg(parts[1].strip(), kpi.available_columns)
            query = f"SELECT {num_sql} / NULLIF({den_sql}, 0) FROM {self.table_name}"
        else:
            agg_sql = self._parse_agg(logic, kpi.available_columns)
            query = f"SELECT {agg_sql} FROM {self.table_name}"
            
        if python_result == "NOT_AVAILABLE":
            sql_result = self._execute(query)
            return SQLAnalysisResult(
                query_name=kpi.kpi_name,
                python_result="NOT_AVAILABLE",
                sql_result=sql_result,
                difference=None,
                match_status="NOT_AVAILABLE",
                sql=query
            )
            
        return self.compare(kpi.kpi_name, python_result, query)

    def _parse_agg(self, expression: str, available_columns: List[str]) -> str:
        """Converts generic pseudo-logic like SUM(Sales) to SUM("Sales")"""
        import re
        match = re.match(r'^([A-Z]+)\(([^)]+)\)$', expression)
        if match:
            func = match.group(1)
            col_raw = match.group(2).strip()
            
            if func == "DISTINCTCOUNT":
                return f"COUNT(DISTINCT {_safe_quote(col_raw)})"
            if func == "AVERAGE":
                return f"AVG({_safe_quote(col_raw)})"
            
            return f"{func}({_safe_quote(col_raw)})"
        return expression

    def close(self):
        """Clean up the connection."""
        if self.conn:
            self.conn.close()
