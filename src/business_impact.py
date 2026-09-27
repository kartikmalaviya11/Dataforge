
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
import json
import os
import hashlib

@dataclass
class BusinessImpact:
    issue_id: str
    affected_records: int
    affected_kpi: str
    business_impact_description: str
    evidence: str
    status: str = "POTENTIAL_IMPACT" # POTENTIAL_IMPACT, OBSERVED_IMPACT, UNRESOLVED
    created_at: str = ""

class BusinessImpactManager:
    def __init__(self, persistence_dir: str = ".dataforge/business_impact"):
        self.persistence_dir = persistence_dir
        os.makedirs(self.persistence_dir, exist_ok=True)
        self.impacts: Dict[str, BusinessImpact] = {}
        self.load()

    def _get_path(self) -> str:
        return os.path.join(self.persistence_dir, "impacts.json")

    def load(self):
        path = self._get_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self.impacts[k] = BusinessImpact(**v)

    def save(self):
        path = self._get_path()
        with open(path, "w", encoding="utf-8") as f:
            data = {k: asdict(v) for k, v in sorted(self.impacts.items())}
            json.dump(data, f, indent=2, sort_keys=True)

    def create(self, affected_records: int, affected_kpi: str, description: str, evidence: str) -> str:
        issue_id = hashlib.sha256(f"{affected_kpi}_{description}".encode()).hexdigest()[:16]
        self.impacts[issue_id] = BusinessImpact(
            issue_id=issue_id,
            affected_records=affected_records,
            affected_kpi=affected_kpi,
            business_impact_description=description,
            evidence=evidence,
            created_at=datetime.utcnow().isoformat()
        )
        self.save()
        return issue_id

    def update_status(self, issue_id: str, status: str):
        i = self.impacts.get(issue_id)
        if i:
            i.status = status
            self.save()
            
    def get_all(self) -> List[BusinessImpact]:
        return [self.impacts[k] for k in sorted(self.impacts.keys())]
