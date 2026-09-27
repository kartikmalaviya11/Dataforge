
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
import json
import os
import hashlib

@dataclass
class Assumption:
    assumption_id: str
    title: str
    description: str
    reason: str
    risk: str
    used_in: List[str]
    status: str = "ACTIVE" # ACTIVE, REVIEWED, RETIRED
    created_at: str = ""

class AssumptionRegisterManager:
    def __init__(self, persistence_dir: str = ".dataforge/assumptions"):
        self.persistence_dir = persistence_dir
        os.makedirs(self.persistence_dir, exist_ok=True)
        self.assumptions: Dict[str, Assumption] = {}
        self.load()

    def _get_path(self) -> str:
        return os.path.join(self.persistence_dir, "assumptions.json")

    def load(self):
        path = self._get_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self.assumptions[k] = Assumption(**v)

    def save(self):
        path = self._get_path()
        with open(path, "w", encoding="utf-8") as f:
            # stable serialization
            data = {k: asdict(v) for k, v in sorted(self.assumptions.items())}
            json.dump(data, f, indent=2, sort_keys=True)

    def create(self, title: str, description: str, reason: str, risk: str, used_in: List[str]) -> str:
        a_id = hashlib.sha256(f"{title}_{description}".encode()).hexdigest()[:16]
        self.assumptions[a_id] = Assumption(
            assumption_id=a_id,
            title=title,
            description=description,
            reason=reason,
            risk=risk,
            used_in=used_in,
            created_at=datetime.utcnow().isoformat()
        )
        self.save()
        return a_id

    def update(self, a_id: str, title: str = None, description: str = None):
        a = self.assumptions.get(a_id)
        if not a: return
        if title: a.title = title
        if description: a.description = description
        self.save()

    def review(self, a_id: str):
        a = self.assumptions.get(a_id)
        if a:
            a.status = "REVIEWED"
            self.save()

    def retire(self, a_id: str):
        a = self.assumptions.get(a_id)
        if a:
            a.status = "RETIRED"
            self.save()
            
    def get_all(self) -> List[Assumption]:
        return [self.assumptions[k] for k in sorted(self.assumptions.keys())]
