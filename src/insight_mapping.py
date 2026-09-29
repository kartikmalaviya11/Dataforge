import os
import json
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from loguru import logger
from src.workspace import ProjectWorkspace
from src.finding_engine import FindingDefinition

@dataclass
class ChartMapping:
    mapping_id: str
    finding_id: str
    chart_type: str
    metric: str
    filters: List[str] = field(default_factory=list)
    dashboard_page: str = "Default Page"

    def dict(self):
        return asdict(self)

class InsightVisualMapper:
    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace
        self.file_path = os.path.join(workspace.project_root, ".dataforge", "insight_mappings.json")
        self.mappings: List[ChartMapping] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.file_path):
            self.mappings = []
            return
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.mappings = []
            for item in data.get("mappings", []):
                self.mappings.append(ChartMapping(**item))
        except Exception as e:
            logger.error(f"Failed to load insight mappings: {e}")
            self.mappings = []

    def save_mappings(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "1.0",
                    "mappings": [m.dict() for m in self.mappings]
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save insight mappings: {e}")

    def generate_mapping(self, finding: FindingDefinition) -> ChartMapping:
        """
        Generate mapping based on finding properties.
        Trend -> Line, Comparison -> Bar, etc.
        """
        text_to_analyze = f"{finding.problem} {finding.evidence_statement} {finding.analyst_interpretation or ''}".lower()
        
        if "trend" in text_to_analyze or "over time" in text_to_analyze:
            chart_type = "Line"
        elif "compare" in text_to_analyze or "comparison" in text_to_analyze or finding.comparison_value is not None:
            chart_type = "Bar"
        elif "distribution" in text_to_analyze or "spread" in text_to_analyze:
            chart_type = "Histogram"
        elif "correlation" in text_to_analyze or "scatter" in text_to_analyze or "relationship" in text_to_analyze:
            chart_type = "Scatter"
        else:
            chart_type = "KPI Card"
            
        metric = "Unknown Metric"
        if finding.metric_value is not None:
            metric = "Metric Value"
        
        mapping = ChartMapping(
            mapping_id=f"map_{uuid.uuid4().hex[:8]}",
            finding_id=finding.finding_id,
            chart_type=chart_type,
            metric=metric,
            filters=[],
            dashboard_page="Insights Page"
        )
        
        self.mappings.append(mapping)
        self.save_mappings()
        return mapping
        
    def validate_mapping(self, mapping_id: str) -> bool:
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return False
        supported_charts = {"Bar", "Line", "KPI Card", "Scatter", "Histogram"}
        return mapping.chart_type in supported_charts
        
    def edit_mapping(self, mapping_id: str, **kwargs) -> Optional[ChartMapping]:
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return None
            
        for k, v in kwargs.items():
            if hasattr(mapping, k):
                setattr(mapping, k, v)
                
        self.save_mappings()
        return mapping
        
    def export_mappings(self, export_path: str):
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump([m.dict() for m in self.mappings], f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to export mappings: {e}")
            return False

    def get_mapping(self, mapping_id: str) -> Optional[ChartMapping]:
        for mapping in self.mappings:
            if mapping.mapping_id == mapping_id:
                return mapping
        return None
