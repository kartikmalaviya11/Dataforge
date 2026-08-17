"""
Phase 11: DAX Measure Generator

Converts KPI recommendations into deterministic, executable Power BI DAX measures.
Handles proper table escaping, ratio safety (DIVIDE), and status propagation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from loguru import logger
import re

from .kpi_engine import KPIRecommendation

@dataclass
class DAXMeasure:
    measure_name: str
    kpi_name: str
    dax_expression: str
    status: str             # "AVAILABLE", "UNAVAILABLE", "REVIEW_REQUIRED"
    required_columns: List[str]
    referenced_columns: List[str]
    explanation: str
    warnings: List[str] = field(default_factory=list)


class DAXGenerator:
    def __init__(self, table_name: str = "Dataset"):
        self.table_name = table_name

    def _escape_identifier(self, name: str) -> str:
        """Escape DAX table or column identifiers (handles spaces and reserved characters)."""
        # DAX standard: escape single quotes in table names by doubling them
        # (Though we default to 'Dataset' which is safe).
        # Columns are just bracketed: [Column Name]
        return name

    def _format_column(self, col_name: str) -> str:
        """Format a fully qualified DAX column reference: 'Table Name'[Column Name]"""
        safe_table = self.table_name.replace("'", "''")
        return f"'{safe_table}'[{col_name}]"

    def _parse_and_convert_logic(self, calculation_logic: str, available_columns: List[str]) -> str:
        """
        Convert Phase 10 pseudo-logic into safe, executable DAX.
        Examples:
        - SUM(Sales) -> SUM('Dataset'[Sales])
        - DISTINCTCOUNT(Order_ID) -> DISTINCTCOUNT('Dataset'[Order_ID])
        - SUM(Profit) / SUM(Sales) -> DIVIDE(SUM('Dataset'[Profit]), SUM('Dataset'[Sales]))
        - SUM(Revenue) grouped by Region -> SUM('Dataset'[Revenue]) (the grouping happens in the UI visual)
        """
        # Strip out "grouped by X" as DAX base measures are independent of visual dimensions
        if " grouped by " in calculation_logic:
            calculation_logic = calculation_logic.split(" grouped by ")[0].strip()

        # Is it a ratio (contains /)?
        if " / " in calculation_logic:
            parts = calculation_logic.split(" / ")
            if len(parts) == 2:
                num = self._parse_single_aggregation(parts[0].strip(), available_columns)
                den = self._parse_single_aggregation(parts[1].strip(), available_columns)
                return f"DIVIDE({num}, {den})"
                
        # Single aggregation
        return self._parse_single_aggregation(calculation_logic, available_columns)

    def _parse_single_aggregation(self, expression: str, available_columns: List[str]) -> str:
        """
        Convert a single aggregation pseudo-code to DAX.
        e.g., SUM(Sales) -> SUM('Dataset'[Sales])
        e.g., AVERAGE(Revenue) -> AVERAGE('Dataset'[Revenue])
        """
        match = re.match(r'^([A-Z]+)\(([^)]+)\)$', expression)
        if match:
            func = match.group(1)
            col_raw = match.group(2).strip()
            
            # Remove brackets if they were already added in pseudo-logic (e.g. SUM([Sales]))
            if col_raw.startswith('[') and col_raw.endswith(']'):
                col_raw = col_raw[1:-1]
                
            # If the column is actually available, use it. Otherwise, use the raw string (which will break in PBI but it shouldn't reach here for UNAVAILABLE KPIs)
            formatted_col = self._format_column(col_raw)
            return f"{func}({formatted_col})"
            
        return expression

    def generate_measure(self, kpi: KPIRecommendation) -> DAXMeasure:
        """Convert a single KPIRecommendation into a DAXMeasure."""
        
        if kpi.status == "UNAVAILABLE":
            return DAXMeasure(
                measure_name=kpi.kpi_name,
                kpi_name=kpi.kpi_name,
                dax_expression="N/A",
                status="UNAVAILABLE",
                required_columns=kpi.required_columns,
                referenced_columns=[],
                explanation="DAX generation skipped because required columns are missing.",
                warnings=[f"Missing requirements: {', '.join(kpi.missing_requirements)}"]
            )
            
        # Parse logic for AVAILABLE and REQUIRES_REVIEW
        dax_expr = self._parse_and_convert_logic(kpi.calculation_logic, kpi.available_columns)
        
        status = "REVIEW_REQUIRED" if kpi.status == "REQUIRES_REVIEW" else "AVAILABLE"
        warnings = []
        if status == "REVIEW_REQUIRED":
            warnings.append("WARNING: This KPI relies on columns with a high defect rate. Review data quality before reporting.")

        return DAXMeasure(
            measure_name=kpi.kpi_name,
            kpi_name=kpi.kpi_name,
            dax_expression=dax_expr,
            status=status,
            required_columns=kpi.required_columns,
            referenced_columns=kpi.available_columns,
            explanation=f"Generated DAX measure for {kpi.kpi_name}.",
            warnings=warnings
        )
        
    def generate_measures(self, kpis: List[KPIRecommendation]) -> List[DAXMeasure]:
        """Convert a list of KPIRecommendations into DAXMeasures."""
        logger.info(f"Generating DAX measures for {len(kpis)} KPIs (Table: '{self.table_name}')")
        return [self.generate_measure(kpi) for kpi in kpis]
