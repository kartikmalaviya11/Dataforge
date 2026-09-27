import os
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from loguru import logger

from src.workspace import ProjectWorkspace

class InterpretationType(str, Enum):
    ANALYST_HYPOTHESIS = "ANALYST_HYPOTHESIS"
    ANALYST_CONCLUSION = "ANALYST_CONCLUSION"

@dataclass
class FindingDefinition:
    finding_id: str
    problem: str
    evidence_statement: str
    created_at: float
    updated_at: float
    
    metric_value: Optional[float] = None
    comparison_value: Optional[float] = None
    comparison_context: Optional[str] = None
    
    system_generated_association: Optional[str] = None
    
    analyst_interpretation: Optional[str] = None
    interpretation_type: Optional[str] = None
    
    impact: Optional[str] = None
    recommendation: Optional[str] = None
    
    is_archived: bool = False
    
    linked_business_question_id: Optional[str] = None
    linked_kpi_id: Optional[str] = None
    linked_rca_analysis_id: Optional[str] = None

    def dict(self):
        return asdict(self)
        
    def is_orphaned(
        self, 
        kpi_ids: Optional[List[str]] = None,
        rca_ids: Optional[List[str]] = None,
        bq_ids: Optional[List[str]] = None
    ) -> bool:
        if self.linked_business_question_id and bq_ids is not None:
            if self.linked_business_question_id not in bq_ids: return True
        if self.linked_kpi_id and kpi_ids is not None:
            if self.linked_kpi_id not in kpi_ids: return True
        if self.linked_rca_analysis_id and rca_ids is not None:
            if self.linked_rca_analysis_id not in rca_ids: return True
        return False

class FindingEngine:
    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace
        self.file_path = os.path.join(workspace.project_root, ".dataforge", "findings.json")
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.findings: List[FindingDefinition] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.file_path):
            self.findings = []
            return
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.findings = []
            for item in data.get("findings", []):
                # Backwards compat if any old fields exist (they shouldn't)
                item.pop('name', None)
                item.pop('finding_type', None)
                item.pop('description', None)
                if 'linked_rca_id' in item:
                    item['linked_rca_analysis_id'] = item.pop('linked_rca_id')
                    
                self.findings.append(FindingDefinition(**item))
        except Exception as e:
            logger.error(f"Failed to load findings: {e}")
            self.findings = []

    def save_findings(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "2.0",
                    "findings": [f.dict() for f in self.findings]
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save findings: {e}")

    def save_finding(self, finding: FindingDefinition) -> FindingDefinition:
        # Validate causality safety
        if finding.interpretation_type and finding.interpretation_type not in ["ANALYST_HYPOTHESIS", "ANALYST_CONCLUSION"]:
            raise ValueError(f"Invalid interpretation_type: {finding.interpretation_type}")
            
        if not finding.finding_id:
            finding.finding_id = f"fnd_{uuid.uuid4().hex[:8]}"
            
        existing = self.get_finding(finding.finding_id)
        if existing:
            self.findings.remove(existing)
            
        self.findings.append(finding)
        # Ensure deterministic ordering
        self.findings.sort(key=lambda x: x.created_at)
        
        self.save_findings()
        return finding

    def archive_finding(self, finding_id: str):
        finding = self.get_finding(finding_id)
        if finding:
            finding.is_archived = True
            finding.updated_at = time.time()
            self.save_findings()

    def load_findings(self) -> List[FindingDefinition]:
        return list(self.findings)

    def get_finding(self, finding_id: str) -> Optional[FindingDefinition]:
        for finding in self.findings:
            if finding.finding_id == finding_id:
                return finding
        return None
