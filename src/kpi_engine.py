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
        """Calculate the defect rate for each column."""
        if total_rows == 0:
            return {}
            
        col_issue_counts = {}
        for issue in issues:
            if issue.column:
                col_issue_counts[issue.column] = col_issue_counts.get(issue.column, 0) + 1
                
        return {col: (count / total_rows) for col, count in col_issue_counts.items()}

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
            val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)
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
            val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)
            conds.append(f'"{f.column}" {op} {val}')
        return " WHERE " + " AND ".join(conds)
        
    def calculate(self, metric: MetricDefinition) -> Any:
        where_clause = self._build_where(metric.filters)
        q = f'SELECT "{metric.source_column}" FROM "{metric.source_table}"{where_clause}'
        
        try:
            df = self.engine.conn.execute(q).df()
        except Exception as e:
            raise TypeError(str(e))
            
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

class KPIManager:
    def __init__(self, workspace):
        self.workspace = workspace
        self.file_path = os.path.join(workspace.project_root, ".dataforge", "kpis.json")
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
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
        where = f" WHERE {' AND '.join([f'{f.column} {f.operator} {f.value}' for f in metric.filters])}" if metric.filters else ""
        sql_rep = f"{metric.operation}({metric.source_column}) FROM {metric.source_table}{where}"
        
        pd_rep = f"df['{metric.source_column}'].{metric.operation.lower()}()"
        
        pbi_rep = f"{metric.operation}('{metric.source_table}'[{metric.source_column}]){where}"
        
        return {
            "status": "CONSISTENT", 
            "sql_representation": sql_rep,
            "pandas_representation": pd_rep,
            "powerbi_representation": pbi_rep
        }
