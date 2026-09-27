
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List
from datetime import datetime
import json
import os
import uuid

@dataclass
class HistoricalReadiness:
    readiness_id: str
    run_id: str
    dataset_version_id: str
    quality_score: float
    validation_score: float
    readiness_status: str
    recorded_at: str

class HistoricalReadinessManager:
    def __init__(self, persistence_dir: str = ".dataforge/historical_readiness"):
        self.persistence_dir = persistence_dir
        os.makedirs(self.persistence_dir, exist_ok=True)
        self.records: Dict[str, HistoricalReadiness] = {}
        self.load()

    def _get_path(self) -> str:
        return os.path.join(self.persistence_dir, "records.json")

    def load(self):
        path = self._get_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self.records[k] = HistoricalReadiness(**v)

    def save(self):
        path = self._get_path()
        with open(path, "w", encoding="utf-8") as f:
            data = {k: asdict(v) for k, v in sorted(self.records.items())}
            json.dump(data, f, indent=2, sort_keys=True)

    def create_snapshot(self, run_id: str, dataset_version_id: str, quality_score: float, validation_score: float, readiness_status: str) -> str:
        r_id = str(uuid.uuid4())
        record = HistoricalReadiness(
            readiness_id=r_id,
            run_id=run_id,
            dataset_version_id=dataset_version_id,
            quality_score=quality_score,
            validation_score=validation_score,
            readiness_status=readiness_status,
            recorded_at=datetime.utcnow().isoformat()
        )
        self.records[r_id] = record
        self.save()
        return r_id
    
    def get_all(self) -> List[HistoricalReadiness]:
        # Return chronologically ordered
        return sorted(self.records.values(), key=lambda x: x.recorded_at)
