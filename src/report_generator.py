"""
Phase 13: Power BI Preparation & Output Generation

Deterministic serialization layer converting pipeline outputs into
clean, tabular, exportable CSV files for Power BI ingestion.
"""

import os
import pandas as pd
import numpy as np
from typing import Any, List, Dict
from loguru import logger

from .profiler import ColumnProfile
from .type_detector import TypeDetectionResult
from .issue_manager import StandardizedIssue
from .scoring import ReadinessScore
from .kpi_engine import KPIRecommendation
from .dax_generator import DAXMeasure

class ReportGenerator:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _serialize_value(self, val: Any) -> Any:
        """
        Normalize values for Power BI.
        - None, NaN, NaT -> ""
        - lists -> comma separated string
        - dicts -> key: value string
        """
        if val is None:
            return ""
        if isinstance(val, (float, np.floating)):
            if np.isnan(val):
                return ""
        if isinstance(val, list):
            return ", ".join(str(self._serialize_value(v)) for v in val)
        if isinstance(val, dict):
            return " | ".join(f"{k}: {self._serialize_value(v)}" for k, v in val.items())
        try:
            if pd.isna(val):
                return ""
        except ValueError:
            pass
        return val

    def _write_csv(self, df: pd.DataFrame, filename: str):
        """Standardized CSV writing to guarantee deterministic output."""
        if df.empty:
            # Write empty dataframe with just headers
            filepath = os.path.join(self.output_dir, filename)
            df.to_csv(filepath, index=False, encoding="utf-8")
            return
            
        # Apply serialization
        for col in df.columns:
            df[col] = df[col].apply(self._serialize_value)
            
        filepath = os.path.join(self.output_dir, filename)
        df.to_csv(filepath, index=False, encoding="utf-8")
        logger.info(f"Generated {filepath} ({len(df)} rows)")

    def generate_dataset_profile(self, dataset_name: str, row_count: int, column_count: int):
        data = [{
            "dataset_name": dataset_name,
            "row_count": row_count,
            "column_count": column_count
        }]
        df = pd.DataFrame(data)
        self._write_csv(df, "dataset_profile.csv")

    def generate_column_metadata(self, col_profiles: List[ColumnProfile], type_results: List[TypeDetectionResult]):
        # Merge profiling and type detection
        types_map = {t.column_name: t for t in type_results}
        
        data = []
        for p in col_profiles:
            t = types_map.get(p.name)
            row = {
                "column_name": p.name,
                "storage_type": p.storage_type,
                "null_count": p.null_count,
                "null_percentage": p.null_percentage,
                "unique_count": p.unique_count,
                "unique_percentage": p.unique_percentage,
                "min": p.min_value,
                "max": p.max_value,
                "mean": p.mean_value,
                "median": p.median_value,
                "semantic_type": t.detected_type if t else "",
                "recommended_action": t.recommended_action if t else "",
                "confidence": t.confidence if t else "",
                "status": t.status if t else "",
                "evidence": t.evidence if t else ""
            }
            data.append(row)
            
        df = pd.DataFrame(data, columns=[
            "column_name", "storage_type", "null_count", "null_percentage", 
            "unique_count", "unique_percentage", "min", "max", "mean", "median", 
            "semantic_type", "recommended_action", "confidence", "status", "evidence"
        ])
        if not df.empty:
            df = df.sort_values("column_name")
        self._write_csv(df, "column_metadata.csv")

    def generate_quality_issues(self, issues: List[StandardizedIssue]):
        data = []
        for i in issues:
            data.append({
                "issue_id": i.issue_id,
                "source": i.source,
                "issue_type": i.issue_type,
                "rule_or_check_name": i.rule_or_check_name,
                "row_index": i.row_index,
                "column": i.column,
                "actual_value": i.actual_value,
                "expected_condition": i.expected_condition,
                "severity": i.severity,
                "message": i.message,
                "recommendation": i.recommendation
            })
        df = pd.DataFrame(data, columns=[
            "issue_id", "source", "issue_type", "rule_or_check_name", "row_index",
            "column", "actual_value", "expected_condition", "severity", "message", "recommendation"
        ])
        if not df.empty:
            df = df.sort_values(by=["issue_id", "row_index", "column"], na_position="first")
        self._write_csv(df, "quality_issues.csv")

    def generate_quality_summary(self, issues: List[StandardizedIssue]):
        total_issues = len(issues)
        issues_by_severity = {}
        issues_by_type = {}
        issues_by_source = {}
        issues_by_column = {}
        
        for i in issues:
            issues_by_severity[i.severity] = issues_by_severity.get(i.severity, 0) + 1
            issues_by_type[i.issue_type] = issues_by_type.get(i.issue_type, 0) + 1
            issues_by_source[i.source] = issues_by_source.get(i.source, 0) + 1
            if i.column:
                issues_by_column[i.column] = issues_by_column.get(i.column, 0) + 1
                
        data = [{
            "total_issues": total_issues,
            "issues_by_severity": issues_by_severity,
            "issues_by_type": issues_by_type,
            "issues_by_source": issues_by_source,
            "issues_by_column": issues_by_column
        }]
        df = pd.DataFrame(data)
        self._write_csv(df, "quality_summary.csv")

    def generate_readiness_score(self, score: ReadinessScore):
        data = [{
            "overall_score": score.overall_score,
            "grade": score.grade,
            "status": score.status
        }]
        
        # Flatten dimensions for Power BI
        for dim, details in score.dimension_results.items():
            data[0][f"dim_{dim}_score"] = details.score
            data[0][f"dim_{dim}_applicable"] = details.is_applicable
            data[0][f"dim_{dim}_penalties"] = details.row_penalty + details.dataset_penalty
            data[0][f"dim_{dim}_explanation"] = details.reason
            
        df = pd.DataFrame(data)
        self._write_csv(df, "readiness_score.csv")

    def generate_kpi_recommendations(self, kpis: List[KPIRecommendation]):
        data = []
        for k in kpis:
            data.append({
                "kpi_name": k.kpi_name,
                "category": k.category,
                "priority": k.priority,
                "status": k.status,
                "required_columns": k.required_columns,
                "available_columns": k.available_columns,
                "calculation_logic": k.calculation_logic,
                "explanation": k.explanation,
                "missing_requirements": k.missing_requirements
            })
        df = pd.DataFrame(data, columns=[
            "kpi_name", "category", "priority", "status", "required_columns",
            "available_columns", "calculation_logic", "explanation", "missing_requirements"
        ])
        if not df.empty:
            df = df.sort_values("kpi_name")
        self._write_csv(df, "kpi_recommendations.csv")

    def generate_dax_measures(self, dax: List[DAXMeasure]):
        data = []
        for d in dax:
            data.append({
                "measure_name": d.measure_name,
                "kpi_name": d.kpi_name,
                "dax_expression": d.dax_expression,
                "status": d.status,
                "required_columns": d.required_columns,
                "referenced_columns": d.referenced_columns,
                "explanation": d.explanation,
                "warnings": d.warnings
            })
        df = pd.DataFrame(data, columns=[
            "measure_name", "kpi_name", "dax_expression", "status", 
            "required_columns", "referenced_columns", "explanation", "warnings"
        ])
        if not df.empty:
            df = df.sort_values("measure_name")
        self._write_csv(df, "dax_measures.csv")
        
    def export_all(self, 
                   dataset_name: str,
                   row_count: int,
                   column_count: int,
                   col_profiles: List[ColumnProfile], 
                   type_results: List[TypeDetectionResult],
                   issues: List[StandardizedIssue],
                   score: ReadinessScore,
                   kpis: List[KPIRecommendation],
                   dax: List[DAXMeasure]):
        """Orchestrates generation of all outputs."""
        logger.info(f"Generating Power BI outputs in directory: {self.output_dir}")
        self.generate_dataset_profile(dataset_name, row_count, column_count)
        self.generate_column_metadata(col_profiles, type_results)
        self.generate_quality_issues(issues)
        self.generate_quality_summary(issues)
        self.generate_readiness_score(score)
        self.generate_kpi_recommendations(kpis)
        self.generate_dax_measures(dax)
        logger.info("Power BI output generation complete.")
