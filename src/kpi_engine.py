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
