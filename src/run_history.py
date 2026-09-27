
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
import uuid

@dataclass
class RunRecord:
    run_id: str
    started_at: str
    dataset_version_id: Optional[str] = None
    cleaning_summary: Dict[str, Any] = field(default_factory=dict)
    quality_score: Optional[float] = None
    sql_results: List[Dict[str, Any]] = field(default_factory=list)
    kpi_results: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    export: Dict[str, Any] = field(default_factory=dict)
    status: str = "RUNNING"
    completed_at: Optional[str] = None

class RunHistoryManager:
    def __init__(self, persistence_dir: str = ".dataforge/run_history"):
        self.persistence_dir = persistence_dir
        os.makedirs(self.persistence_dir, exist_ok=True)
        self.runs: Dict[str, RunRecord] = {}
        self.load()

    def _get_path(self) -> str:
        return os.path.join(self.persistence_dir, "runs.json")

    def load(self):
        path = self._get_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self.runs[k] = RunRecord(**v)

    def save(self):
        path = self._get_path()
        with open(path, "w", encoding="utf-8") as f:
            data = {k: asdict(v) for k, v in sorted(self.runs.items())}
            json.dump(data, f, indent=2, sort_keys=True)

    def create_run(self) -> str:
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            started_at=datetime.utcnow().isoformat()
        )
        self.runs[run_id] = record
        self.save()
        return run_id

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        return self.runs.get(run_id)

    def update_run(self, run_id: str, updates: Dict[str, Any]):
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
            raise ValueError("Cannot modify completed run")
        
        for k, v in updates.items():
            if hasattr(run, k):
                setattr(run, k, v)
        self.save()

    def complete_run(self, run_id: str):
        self.update_run(run_id, {"status": "COMPLETED", "completed_at": datetime.utcnow().isoformat()})

    def fail_run(self, run_id: str):
        self.update_run(run_id, {"status": "FAILED", "completed_at": datetime.utcnow().isoformat()})

    def cancel_run(self, run_id: str):
        self.update_run(run_id, {"status": "CANCELLED", "completed_at": datetime.utcnow().isoformat()})

    def get_all_runs(self) -> List[RunRecord]:
        return [self.runs[k] for k in sorted(self.runs.keys())]
