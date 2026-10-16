"""
Phase 10: KPI Recommendation Engine

Recommends deterministic, mathematically feasible KPIs based on dataset semantic types,
column roles, and data quality issue thresholds.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from loguru import logger
import re

from .type_detector import TypeDetectionResult
from .issue_manager import StandardizedIssue

@dataclass
class KPIRecommendation:
    kpi_name: str
    category: str       # "Aggregation", "Transaction", "Ratio", "Time", "Dimension"
    priority: str       # "HIGH", "MEDIUM", "LOW"
    status: str         # "AVAILABLE", "UNAVAILABLE", "REQUIRES_REVIEW"
    required_columns: List[str]
    available_columns: List[str]
    calculation_logic: str
    explanation: str
    missing_requirements: List[str] = field(default_factory=list)


# Keywords used to heuristically identify semantic roles in combination with data types.
MEASURE_KEYWORDS = {"sales", "revenue", "profit", "quantity", "cost", "discount", "amount", "price", "tax", "margin"}
IGNORE_MEASURE_KEYWORDS = {"id", "age", "year", "zip", "code", "phone", "latitude", "longitude"}

DIMENSION_KEYWORDS = {"category", "region", "status", "department", "product", "segment", "country", "city", "type", "group"}


class KPIEngine:
    def __init__(self, review_threshold: float = 0.10):
        """
        Initialize the KPI Engine.
        
        Args:
            review_threshold: The defect rate threshold above which a KPI is marked REQUIRES_REVIEW.
                              A default of 0.10 means if >10% of the values in a required column
                              have quality issues, human review is recommended before trusting the KPI.
        """
        self.review_threshold = review_threshold
        
    def _tokenize(self, text: str) -> Set[str]:
        """Split text into lowercase word tokens."""
        spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', text)
        tokens = re.split(r'[^a-zA-Z0-9]+', spaced)
        return {t.lower() for t in tokens if t}

    def _determine_column_roles(self, type_results: List[TypeDetectionResult]) -> Dict[str, List[str]]:
        """
        Categorize columns into roles based on semantic types and name context.
        Roles: 'measures', 'ids', 'dates', 'dimensions'
        """
        roles = {
            "measures": [],
            "ids": [],
            "dates": [],
            "dimensions": []
        }
        
        for res in type_results:
            col = res.column_name
            tokens = self._tokenize(col)
            sem_type = res.detected_type
            
            # IDs
            if sem_type == "ID" or "id" in tokens:
                roles["ids"].append(col)
                continue
                
            # Dates
            if sem_type in ("Date", "DateTime"):
                roles["dates"].append(col)
                continue
                
            # Measures
            # Do NOT treat every Integer/Decimal as a business measure.
            # E.g. "Age", "Year" are numeric but not typical aggregate measures.
            # It's a measure if it's explicitly Currency/Percentage, OR it's numeric AND has a measure keyword,
            # OR it's numeric and has NO ignore keywords (fallback, cautious).
            if sem_type in ("Integer", "Decimal", "Currency", "Percentage"):
                if tokens.intersection(IGNORE_MEASURE_KEYWORDS):
                    pass # Not a measure
                elif sem_type in ("Currency", "Percentage"):
                    roles["measures"].append(col)
                elif tokens.intersection(MEASURE_KEYWORDS):
                    roles["measures"].append(col)
                elif not tokens:
                    pass
                else:
                    # Generic numeric column without ignore keywords
                    roles["measures"].append(col)
                continue
                
            # Dimensions
            if sem_type == "Category" or tokens.intersection(DIMENSION_KEYWORDS):
                roles["dimensions"].append(col)
                continue
                
        return roles

    def _calculate_defect_rates(self, issues: List[StandardizedIssue], total_rows: int) -> Dict[str, float]:
        """Calculate the defect rate for each column based on unique affected records."""
        if total_rows <= 0:
            return {}
            
        from collections import defaultdict
        col_affected_rows = defaultdict(set)
        col_unindexed_count = defaultdict(int)

        for issue in issues:
            if issue.column:
                if issue.row_index is not None:
                    col_affected_rows[issue.column].add(issue.row_index)
                else:
                    col_unindexed_count[issue.column] += 1

        all_cols = set(col_affected_rows.keys()).union(col_unindexed_count.keys())
        defect_rates = {}
        for col in all_cols:
            unique_rows = len(col_affected_rows[col])
            total_affected = min(total_rows, unique_rows + col_unindexed_count[col])
            defect_rates[col] = total_affected / total_rows

        return defect_rates

    def _evaluate_kpi(
        self,
        name: str,
        category: str,
        priority: str,
        required_cols: List[str],
        logic_template: str,
        defect_rates: Dict[str, float]
    ) -> KPIRecommendation:
        """Evaluate a KPI template and return its recommendation status."""
        missing = [col for col in required_cols if not col]
        available = [col for col in required_cols if col]
        
        if missing:
            return KPIRecommendation(
                kpi_name=name,
                category=category,
                priority=priority,
                status="UNAVAILABLE",
                required_columns=[col if col else "[Missing Required Column]" for col in required_cols],
                available_columns=available,
                calculation_logic="N/A",
                explanation=f"{name} requires additional columns to be calculated.",
                missing_requirements=[f"Missing requirement for {category}"]
            )
            
        # Check defect rates for REQUIRES_REVIEW
        highest_defect_rate = max((defect_rates.get(col, 0.0) for col in available), default=0.0)
        
        if highest_defect_rate > self.review_threshold:
            status = "REQUIRES_REVIEW"
            explanation = (
                f"{name} can be calculated, but relies on columns with a defect rate of "
                f"{highest_defect_rate:.1%}. Review data quality before reporting."
            )
        else:
            status = "AVAILABLE"
            explanation = f"{name} is fully supported by the dataset."
            
        return KPIRecommendation(
            kpi_name=name,
            category=category,
            priority=priority,
            status=status,
            required_columns=available,
            available_columns=available,
            calculation_logic=logic_template,
            explanation=explanation,
            missing_requirements=[]
        )

    def recommend_kpis(
        self, 
        total_rows: int, 
        type_results: List[TypeDetectionResult], 
        issues: List[StandardizedIssue]
    ) -> List[KPIRecommendation]:
        """
        Recommend KPIs based on dataset semantics and data quality.
        """
        logger.info("Evaluating KPI recommendations...")
        roles = self._determine_column_roles(type_results)
        defect_rates = self._calculate_defect_rates(issues, total_rows)
        
        recommendations = []
        
        # Helper to find specific measure columns
        def find_measure(*keywords) -> Optional[str]:
            for m in roles["measures"]:
                tokens = self._tokenize(m)
                if any(kw in tokens for kw in keywords):
                    return m
            return None
            
        # 1. Aggregation KPIs
        sales_col = find_measure("sales", "revenue")
        profit_col = find_measure("profit", "margin")
        qty_col = find_measure("quantity", "qty")
        discount_col = find_measure("discount")
        
        # Generic fallback if no specific keywords match, just take the first measure
        primary_measure = sales_col or profit_col or (roles["measures"][0] if roles["measures"] else None)
        
        if sales_col:
            recommendations.append(self._evaluate_kpi(
                "Total Sales", "Aggregation", "HIGH", [sales_col], f"SUM({sales_col})", defect_rates
            ))
            recommendations.append(self._evaluate_kpi(
                "Average Sales", "Aggregation", "MEDIUM", [sales_col], f"AVERAGE({sales_col})", defect_rates
            ))
        elif primary_measure:
            recommendations.append(self._evaluate_kpi(
                f"Total {primary_measure.title()}", "Aggregation", "MEDIUM", [primary_measure], f"SUM({primary_measure})", defect_rates
            ))
            
        if qty_col:
            recommendations.append(self._evaluate_kpi(
                "Total Quantity", "Aggregation", "MEDIUM", [qty_col], f"SUM({qty_col})", defect_rates
            ))
            
        # 2. Transaction KPIs
        order_id = next((i for i in roles["ids"] if any(k in self._tokenize(i) for k in ("order", "transaction", "invoice", "receipt"))), None)
        cust_id = next((i for i in roles["ids"] if "customer" in self._tokenize(i)), None)
        
        if order_id:
            recommendations.append(self._evaluate_kpi(
                "Total Orders", "Transaction", "HIGH", [order_id], f"DISTINCTCOUNT({order_id})", defect_rates
            ))
        else:
            recommendations.append(self._evaluate_kpi(
                "Total Orders", "Transaction", "HIGH", [None], "DISTINCTCOUNT([Order ID])", defect_rates
            ))
            
        if cust_id:
            recommendations.append(self._evaluate_kpi(
                "Distinct Customers", "Transaction", "HIGH", [cust_id], f"DISTINCTCOUNT({cust_id})", defect_rates
            ))
            
        if sales_col and order_id:
            recommendations.append(self._evaluate_kpi(
                "Average Order Value", "Transaction", "HIGH", [sales_col, order_id], f"SUM({sales_col}) / DISTINCTCOUNT({order_id})", defect_rates
            ))
        else:
            recommendations.append(self._evaluate_kpi(
                "Average Order Value", "Transaction", "HIGH", [sales_col, order_id], "SUM([Sales]) / DISTINCTCOUNT([Order ID])", defect_rates
            ))
            
        # 3. Ratio KPIs
        if sales_col and profit_col:
            recommendations.append(self._evaluate_kpi(
                "Profit Margin", "Ratio", "HIGH", [profit_col, sales_col], f"SUM({profit_col}) / SUM({sales_col})", defect_rates
            ))
        else:
            recommendations.append(self._evaluate_kpi(
                "Profit Margin", "Ratio", "HIGH", [profit_col, sales_col], "SUM([Profit]) / SUM([Sales])", defect_rates
            ))
            
        if discount_col and sales_col:
            recommendations.append(self._evaluate_kpi(
                "Discount Rate", "Ratio", "MEDIUM", [discount_col, sales_col], f"SUM({discount_col}) / SUM({sales_col})", defect_rates
            ))
            
        # 4. Time KPIs
        primary_date = roles["dates"][0] if roles["dates"] else None
        if primary_measure and primary_date:
            recommendations.append(self._evaluate_kpi(
                f"{primary_measure.title()} over Time", "Time", "HIGH", [primary_measure, primary_date], f"SUM({primary_measure}) grouped by {primary_date}", defect_rates
            ))
            
        # 5. Dimension KPIs
        primary_dim = roles["dimensions"][0] if roles["dimensions"] else None
        if primary_measure and primary_dim:
            recommendations.append(self._evaluate_kpi(
                f"{primary_measure.title()} by {primary_dim.title()}", "Dimension", "MEDIUM", [primary_measure, primary_dim], f"SUM({primary_measure}) grouped by {primary_dim}", defect_rates
            ))

        # Deduplicate by kpi_name (keep first occurrence)
        seen = set()
        deduped = []
        for r in recommendations:
            if r.kpi_name not in seen:
                seen.add(r.kpi_name)
                deduped.append(r)

        logger.info(f"Generated {len(deduped)} KPI recommendations.")
        return deduped

# ==============================================================================
# PHASE 5: KPI Builder & Cross-Validation
# ==============================================================================

import os
import json
import time
import math
import pandas as pd
from typing import Any, Union
from src.sql_engine import DuckDBEngine

ALLOWED_OPERATIONS = {"COUNT", "COUNT_DISTINCT", "SUM", "AVG", "MIN", "MAX"}
ALLOWED_FILTER_OPS = {"==", "!=", ">", "<", ">=", "<="}

@dataclass
class FilterDefinition:
    column: str
    operator: str
    value: Any

    def __post_init__(self):
        if self.operator not in ALLOWED_FILTER_OPS:
            raise ValueError(f"Invalid operator: {self.operator}. Allowed: {ALLOWED_FILTER_OPS}")
        if self.value is None:
            raise ValueError("NULL comparisons (col == None) are blocked. Filter out NULLs explicitly if needed.")

@dataclass
class MetricDefinition:
    metric_name: str
    operation: str
    source_table: str
    source_column: str
    filters: Optional[List[FilterDefinition]] = None

    def __post_init__(self):
        self.operation = self.operation.upper()
        if self.operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"Invalid operation: {self.operation}. Allowed: {ALLOWED_OPERATIONS}")

@dataclass
class KPIDefinition:
    kpi_id: str
    kpi_name: str
    business_definition: str
    formula: str  # Descriptive only
    metric_definitions: List[MetricDefinition]
    source_tables: List[str]
    source_columns: List[str]
    unit: str
    description: str
    version: int = 1
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        metrics = []
        for m in self.metric_definitions:
            filters = []
            if m.filters:
                for f in m.filters:
                    filters.append({"column": f.column, "operator": f.operator, "value": f.value})
            metrics.append({
                "metric_name": m.metric_name,
                "operation": m.operation,
                "source_table": m.source_table,
                "source_column": m.source_column,
                "filters": filters if m.filters else None
            })
        return {
            "kpi_id": self.kpi_id,
            "kpi_name": self.kpi_name,
            "business_definition": self.business_definition,
            "formula": self.formula,
            "metric_definitions": metrics,
            "source_tables": self.source_tables,
            "source_columns": self.source_columns,
            "unit": self.unit,
            "description": self.description,
            "version": self.version,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data):
        metrics = []
        for m in data.get("metric_definitions", []):
            filters = []
            if m.get("filters"):
                for f in m["filters"]:
                    filters.append(FilterDefinition(**f))
            metrics.append(MetricDefinition(
                metric_name=m["metric_name"],
                operation=m["operation"],
                source_table=m["source_table"],
                source_column=m["source_column"],
                filters=filters if filters else None
            ))
        data["metric_definitions"] = metrics
        return cls(**data)

def normalize_missing(val):
    if val is None or pd.isna(val) or pd.isnull(val):
        return "MISSING"
    return val

class SQLValidator:
    def __init__(self, engine: DuckDBEngine):
        self.engine = engine
        
    def _build_where(self, filters: List[FilterDefinition]) -> str:
        if not filters:
            return ""
        conds = []
        for f in filters:
            op = "=" if f.operator == "==" else f.operator
            if isinstance(f.value, str):
                escaped = f.value.replace("'", "''")
                val = f"'{escaped}'"
            else:
                val = str(f.value)
            conds.append(f'"{f.column}" {op} {val}')
        return " WHERE " + " AND ".join(conds)

    def calculate(self, metric: MetricDefinition) -> Any:
        where_clause = self._build_where(metric.filters)
        
        if metric.operation == "COUNT_DISTINCT":
            op_str = f'COUNT(DISTINCT "{metric.source_column}")'
        else:
            op_str = f'{metric.operation}("{metric.source_column}")'
            
        q = f'SELECT {op_str} FROM "{metric.source_table}"{where_clause}'
        df = self.engine.conn.execute(q).df()
        val = df.iloc[0, 0] if not df.empty else None
        
        norm = normalize_missing(val)
        if norm == "MISSING" and metric.operation in ("COUNT", "COUNT_DISTINCT"):
            return 0
        return norm

class PandasValidator:
    def __init__(self, engine: DuckDBEngine):
        self.engine = engine

    def _build_where(self, filters: List[FilterDefinition]) -> str:
        if not filters:
            return ""
        conds = []
        for f in filters:
            op = "=" if f.operator == "==" else f.operator
            if isinstance(f.value, str):
                escaped = f.value.replace("'", "''")
                val = f"'{escaped}'"
            else:
                val = str(f.value)
            conds.append(f'"{f.column}" {op} {val}')
        return " WHERE " + " AND ".join(conds)
        
    def calculate(self, metric: MetricDefinition) -> Any:
        cols = [metric.source_column]
        if metric.filters:
            for f in metric.filters:
                if f.column not in cols:
                    cols.append(f.column)
        cols_sql = ", ".join([f'"{c}"' for c in cols])
        q = f'SELECT {cols_sql} FROM "{metric.source_table}"'
        
        try:
            df = self.engine.conn.execute(q).df()
        except Exception as e:
            raise TypeError(str(e))
            
        if metric.filters:
            for f in metric.filters:
                op = f.operator
                col = f.column
                if op in ("==", "="):
                    df = df[df[col] == f.value]
                elif op == "!=":
                    df = df[df[col] != f.value]
                elif op == ">":
                    df = df[df[col] > f.value]
                elif op == ">=":
                    df = df[df[col] >= f.value]
                elif op == "<":
                    df = df[df[col] < f.value]
                elif op == "<=":
                    df = df[df[col] <= f.value]

        if df.empty:
            if metric.operation in ("COUNT", "COUNT_DISTINCT"):
                return 0
            return "MISSING"
            
        s = df[metric.source_column]
        
        if metric.operation == "COUNT":
            val = s.count()
        elif metric.operation == "COUNT_DISTINCT":
            val = s.nunique(dropna=True)
        elif metric.operation == "SUM":
            if s.dropna().empty:
                val = "MISSING"
            else:
                val = s.sum()
        elif metric.operation == "AVG":
            if s.dropna().empty:
                val = "MISSING"
            else:
                val = s.mean()
        elif metric.operation == "MIN":
            if s.dropna().empty:
                val = "MISSING"
            else:
                val = s.min()
        elif metric.operation == "MAX":
            if s.dropna().empty:
                val = "MISSING"
            else:
                val = s.max()
                
        if val == "MISSING":
            return val
            
        norm = normalize_missing(val)
        return norm

class CrossValidator:
    def __init__(self, sql_validator: SQLValidator, pandas_validator: PandasValidator):
        self.sql = sql_validator
        self.pd = pandas_validator
        
    def validate(self, metric: MetricDefinition) -> Dict[str, Any]:
        sql_res = self.sql.calculate(metric)
        pd_res = self.pd.calculate(metric)
        
        match = self._compare(sql_res, pd_res)
        
        return {
            "metric_name": metric.metric_name,
            "sql_result": sql_res,
            "pandas_result": pd_res,
            "status": "MATCH" if match else "MISMATCH",
            "absolute_diff": abs(sql_res - pd_res) if isinstance(sql_res, (int, float)) and isinstance(pd_res, (int, float)) else None,
        }

    def _compare(self, a, b):
        if a == "MISSING" and b == "MISSING":
            return True
        if a == "MISSING" or b == "MISSING":
            return False
            
        if type(a) == int and type(b) == int:
            return a == b
            
        try:
            a, b = float(a), float(b)
            return math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
        except:
            return a == b


@dataclass
class KPISnapshot:
    snapshot_id: str
    kpi_id: str
    kpi_name: str
    dataset_version_id: Optional[str]
    value: Any
    recorded_at: str

    def to_dict(self):
        return {
            "snapshot_id": self.snapshot_id,
            "kpi_id": self.kpi_id,
            "kpi_name": self.kpi_name,
            "dataset_version_id": self.dataset_version_id,
            "value": self.value,
            "recorded_at": self.recorded_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            kpi_id=data.get("kpi_id", ""),
            kpi_name=data.get("kpi_name", ""),
            dataset_version_id=data.get("dataset_version_id"),
            value=data.get("value"),
            recorded_at=data.get("recorded_at", "")
        )

class KPIManager:
    def __init__(self, workspace):
        self.workspace = workspace
        self.file_path = os.path.join(workspace.project_root, ".dataforge", "kpis.json")
        self.snapshot_file = os.path.join(workspace.project_root, ".dataforge", "kpi_snapshots.json")
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
    def load_snapshots(self) -> List['KPISnapshot']:
        if not os.path.exists(self.snapshot_file):
            return []
        try:
            import json
            with open(self.snapshot_file, "r") as f:
                data = json.load(f)
            return [KPISnapshot.from_dict(s) for s in data]
        except Exception:
            return []

    def save_snapshot(self, snapshot: 'KPISnapshot'):
        import json
        snaps = self.load_snapshots()
        snaps.append(snapshot)
        with open(self.snapshot_file, "w") as f:
            json.dump([s.to_dict() for s in snaps], f, indent=2)

    def get_snapshot(self, snapshot_id: str) -> Optional['KPISnapshot']:
        for s in self.load_snapshots():
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def calculate_kpi_value(self, kpi: Any, ws: Any = None) -> Tuple[Optional[float], str]:
        """
        Calculates the KPI value using actual formula/metric logic.
        Does NOT approximate distinct counts or ratios from a single column alone.
        Returns (value, status_or_error_message).
        If unsupported or calculation fails, returns (None, error_description).
        """
        workspace = ws or self.workspace

        # 1. If KPI is marked UNAVAILABLE or calculation_logic is N/A
        status_attr = getattr(kpi, "status", None)
        if status_attr == "UNAVAILABLE":
            return None, "KPI is marked UNAVAILABLE due to missing requirements"

        # 2. Case A: KPIDefinition (has metric_definitions)
        metric_defs = getattr(kpi, "metric_definitions", None)
        if metric_defs:
            from src.sql_engine import DuckDBEngine
            engine = DuckDBEngine(workspace)
            val_results = {}
            for m in metric_defs:
                try:
                    q_col = f'"{m.source_column}"'
                    if m.operation in ("COUNT_DISTINCT", "DISTINCTCOUNT"):
                        op_expr = f'COUNT(DISTINCT {q_col})'
                    elif m.operation in ("COUNT", "SUM", "AVG", "MIN", "MAX"):
                        op_expr = f'{m.operation}({q_col})'
                    else:
                        return None, f"Unsupported metric operation: {m.operation}"

                    where = ""
                    if m.filters:
                        conds = []
                        for f in m.filters:
                            op = "=" if f.operator == "==" else f.operator
                            clean_val = str(f.value).replace("'", "''")
                            val_str = f"'{clean_val}'" if isinstance(f.value, str) else str(f.value)
                            conds.append(f'"{f.column}" {op} {val_str}')
                        where = " WHERE " + " AND ".join(conds)

                    q = f'SELECT {op_expr} FROM "{m.source_table}"{where}'
                    res = engine.conn.execute(q).fetchone()[0]
                    if res is None:
                        val_results[m.metric_name] = 0.0 if "COUNT" in m.operation else None
                    else:
                        val_results[m.metric_name] = float(res)
                except Exception as ex:
                    return None, f"Calculation failed for metric {m.metric_name}: {ex}"

            formula = getattr(kpi, "formula", "") or ""
            if formula and all(m.metric_name in formula for m in metric_defs):
                try:
                    eval_expr = formula
                    for m_name, m_val in val_results.items():
                        if m_val is None:
                            return None, f"Metric {m_name} returned null"
                        eval_expr = eval_expr.replace(m_name, str(m_val))
                    if not re.match(r'^[0-9\.\s\+\-\*\/\(\)]+$', eval_expr):
                        return None, f"Unsupported characters in formula: {formula}"
                    res_val = float(eval(eval_expr, {"__builtins__": None}, {}))
                    return round(res_val, 4), "SUCCESS"
                except ZeroDivisionError:
                    return None, "Division by zero in formula"
                except Exception as ex:
                    return None, f"Formula evaluation error: {ex}"
            elif len(metric_defs) == 1:
                val = list(val_results.values())[0]
                return (round(val, 4) if val is not None else None), "SUCCESS"

        # 3. Case B: KPIRecommendation or object with calculation_logic
        calc_logic = getattr(kpi, "calculation_logic", None)
        if not calc_logic or calc_logic.strip() in ("", "N/A"):
            return None, "Missing or N/A calculation logic"

        calc_str = calc_logic.strip()
        if " grouped by " in calc_str.lower():
            return None, "Grouped calculation logic is not supported for single-value snapshot"

        from src.sql_engine import DuckDBEngine
        engine = DuckDBEngine(workspace)

        def _eval_agg(func: str, col_raw: str) -> Tuple[Optional[float], Optional[str]]:
            col = col_raw.strip().strip("[]").strip('"')
            target_tbl = None
            if hasattr(workspace, "registry"):
                for tname in workspace.registry.keys():
                    try:
                        cols = [desc[0] for desc in engine.conn.execute(f'DESCRIBE "{tname}"').fetchall()]
                        if col in cols:
                            target_tbl = tname
                            break
                    except Exception:
                        pass
            if not target_tbl:
                try:
                    tbls = [r[0] for r in engine.conn.execute("SHOW TABLES").fetchall()]
                    for t in tbls:
                        cols = [desc[0] for desc in engine.conn.execute(f'DESCRIBE "{t}"').fetchall()]
                        if col in cols:
                            target_tbl = t
                            break
                except Exception:
                    pass

            if not target_tbl:
                return None, f"Column '{col}' not found in workspace"

            q_col = f'"{col}"'
            func_up = func.upper()
            if func_up in ("COUNT_DISTINCT", "DISTINCTCOUNT"):
                sql = f'SELECT COUNT(DISTINCT {q_col}) FROM "{target_tbl}"'
            elif func_up in ("COUNT", "SUM", "AVERAGE", "AVG", "MIN", "MAX"):
                sql_func = "AVG" if func_up == "AVERAGE" else func_up
                sql = f'SELECT {sql_func}({q_col}) FROM "{target_tbl}"'
            else:
                return None, f"Unsupported aggregate function: {func}"

            try:
                res = engine.conn.execute(sql).fetchone()[0]
                if res is None:
                    return (0.0 if "COUNT" in func_up else None), None
                return float(res), None
            except Exception as e:
                return None, str(e)

        # Parse ratio: A / B
        if " / " in calc_str:
            parts = calc_str.split(" / ", 1)
            m1 = re.match(r'^([A-Z_]+)\(([^)]+)\)$', parts[0].strip(), re.IGNORECASE)
            m2 = re.match(r'^([A-Z_]+)\(([^)]+)\)$', parts[1].strip(), re.IGNORECASE)
            if not m1 or not m2:
                return None, f"Unsupported ratio formula syntax: {calc_str}"
            val1, err1 = _eval_agg(m1.group(1), m1.group(2))
            if err1:
                return None, err1
            val2, err2 = _eval_agg(m2.group(1), m2.group(2))
            if err2:
                return None, err2
            if val1 is None or val2 is None:
                return None, "Operand returned NULL"
            if val2 == 0:
                return None, "Division by zero in ratio"
            return round(val1 / val2, 4), "SUCCESS"

        # Parse single aggregation: FUNC(col)
        m = re.match(r'^([A-Z_]+)\(([^)]+)\)$', calc_str, re.IGNORECASE)
        if m:
            val, err = _eval_agg(m.group(1), m.group(2))
            if err:
                return None, err
            return (round(val, 4) if val is not None else None), "SUCCESS"

        return None, f"Unsupported calculation format: {calc_str}"

    def compare_snapshots(self, snap_a: Any, snap_b: Any) -> Dict[str, Any]:
        """
        Compare two KPI snapshots.

        Zero-baseline handling:
        - When baseline is 0 and comparison is non-zero, relative_change_pct is explicitly None
          (division by zero is undefined). relative_change_note documents this state.
          absolute_difference and directional status ('INCREASED' / 'DECREASED') are preserved.
        - When both baseline and comparison are 0, relative_change_pct is 0.0, absolute_difference
          is 0.0, and status is 'UNCHANGED'.
        - When baseline is non-zero, standard relative percentage change ((val_b - val_a) / abs(val_a)) * 100
          is computed with ddof/sign preserved.
        """
        if isinstance(snap_a, str):
            s1 = self.get_snapshot(snap_a)
            if not s1:
                raise ValueError(f"Snapshot not found: {snap_a}")
        else:
            s1 = snap_a

        if isinstance(snap_b, str):
            s2 = self.get_snapshot(snap_b)
            if not s2:
                raise ValueError(f"Snapshot not found: {snap_b}")
        else:
            s2 = snap_b

        val_a, val_b = s1.value, s2.value
        abs_diff = None
        rel_change_pct = None
        rel_change_note = None

        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            abs_diff = float(val_b - val_a)
            if val_a != 0:
                rel_change_pct = float(((val_b - val_a) / abs(val_a)) * 100.0)
            else:
                if val_b == 0:
                    rel_change_pct = 0.0
                    rel_change_note = "Zero baseline with zero change (0.0%)"
                else:
                    rel_change_pct = None
                    rel_change_note = "Undefined (baseline is zero)"
            status = "INCREASED" if abs_diff > 0 else ("DECREASED" if abs_diff < 0 else "UNCHANGED")
        else:
            status = "UNCHANGED" if val_a == val_b else "DIFFERENT"
            rel_change_note = "Non-numeric values"

        return {
            "snapshot_id_a": s1.snapshot_id,
            "snapshot_id_b": s2.snapshot_id,
            "kpi_id": s2.kpi_id or s1.kpi_id,
            "kpi_name": s2.kpi_name or s1.kpi_name,
            "dataset_version_id_a": s1.dataset_version_id,
            "dataset_version_id_b": s2.dataset_version_id,
            "versions_distinguishable": s1.dataset_version_id != s2.dataset_version_id,
            "value_a": val_a,
            "value_b": val_b,
            "absolute_difference": abs_diff,
            "relative_change_pct": rel_change_pct,
            "relative_change_note": rel_change_note,
            "status": status,
            "recorded_at_a": s1.recorded_at,
            "recorded_at_b": s2.recorded_at,
        }
    def load_kpis(self) -> List[KPIDefinition]:
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r") as f:
            data = json.load(f)
        return [KPIDefinition.from_dict(k) for k in data]
        
    def save_kpi(self, kpi: KPIDefinition, overwrite: bool = False):
        kpis = self.load_kpis()
        existing = [k for k in kpis if k.kpi_name == kpi.kpi_name]
        
        if existing and not overwrite:
            raise ValueError(f"Duplicate KPI name: {kpi.kpi_name}")
            
        if overwrite:
            kpis = [k for k in kpis if k.kpi_name != kpi.kpi_name]
            
        kpi.updated_at = time.time()
        kpis.append(kpi)
        
        with open(self.file_path, "w") as f:
            json.dump([k.to_dict() for k in kpis], f, indent=2)
            
    def get_kpi_by_name(self, name: str) -> Optional[KPIDefinition]:
        for k in self.load_kpis():
            if k.kpi_name == name:
                return k
        return None

class KPISemanticChecker:
    def check_consistency(self, metric: MetricDefinition) -> Dict[str, Any]:
        where_conds = []
        if metric.filters:
            for f in metric.filters:
                op = "=" if f.operator == "==" else f.operator
                if isinstance(f.value, str):
                    escaped = f.value.replace("'", "''")
                    val = f"'{escaped}'"
                else:
                    val = str(f.value)
                where_conds.append(f'"{f.column}" {op} {val}')
        where = f" WHERE {' AND '.join(where_conds)}" if where_conds else ""
        sql_rep = f"{metric.operation}({metric.source_column}) FROM {metric.source_table}{where}"
        
        if metric.filters:
            pd_conds = []
            for f in metric.filters:
                val_repr = repr(f.value) if isinstance(f.value, str) else str(f.value)
                op_pd = "==" if f.operator in ("=", "==") else f.operator
                pd_conds.append(f"(df['{f.column}'] {op_pd} {val_repr})")
            filter_expr = " & ".join(pd_conds)
            pd_rep = f"df[{filter_expr}]['{metric.source_column}'].{metric.operation.lower()}()"
        else:
            pd_rep = f"df['{metric.source_column}'].{metric.operation.lower()}()"
        
        pbi_rep = f"{metric.operation}('{metric.source_table}'[{metric.source_column}]){where}"
        
        return {
            "status": "CONSISTENT", 
            "sql_representation": sql_rep,
            "pandas_representation": pd_rep,
            "powerbi_representation": pbi_rep
        }
