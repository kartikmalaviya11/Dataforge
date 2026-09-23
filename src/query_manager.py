import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
import time
import uuid

@dataclass
class SavedQuery:
    id: str
    name: str
    sql: str
    created_at: float
    updated_at: float

@dataclass
class QueryHistoryEntry:
    id: str
    sql: str
    timestamp: float
    status: str
    duration_ms: float
    rows_returned: Optional[int]
    error_message: Optional[str]

class QueryManager:
    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root)
        self.queries_file = self.project_root / "queries.json"
        self._ensure_file()
        
    def _ensure_file(self):
        if not self.queries_file.exists():
            self._write_data({"saved": [], "history": []})
            
    def _read_data(self) -> dict:
        try:
            with open(self.queries_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"saved": [], "history": []}
            
    def _write_data(self, data: dict):
        with open(self.queries_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def save_query(self, name: str, sql: str, query_id: str = None) -> SavedQuery:
        data = self._read_data()
        now = time.time()
        
        if query_id:
            for q in data["saved"]:
                if q["id"] == query_id:
                    q["name"] = name
                    q["sql"] = sql
                    q["updated_at"] = now
                    self._write_data(data)
                    return SavedQuery(**q)
                    
        # New query
        q = SavedQuery(
            id=query_id or str(uuid.uuid4()),
            name=name,
            sql=sql,
            created_at=now,
            updated_at=now
        )
        data["saved"].append(asdict(q))
        self._write_data(data)
        return q

    def get_saved_queries(self) -> List[SavedQuery]:
        data = self._read_data()
        return [SavedQuery(**q) for q in data.get("saved", [])]

    def log_history(self, sql: str, status: str, duration_ms: float, rows: Optional[int] = None, error: Optional[str] = None):
        data = self._read_data()
        entry = QueryHistoryEntry(
            id=str(uuid.uuid4()),
            sql=sql,
            timestamp=time.time(),
            status=status,
            duration_ms=duration_ms,
            rows_returned=rows,
            error_message=error
        )
        data["history"].append(asdict(entry))
        # Keep history bounded to last 100 entries
        if len(data["history"]) > 100:
            data["history"] = data["history"][-100:]
        self._write_data(data)

    def get_history(self) -> List[QueryHistoryEntry]:
        data = self._read_data()
        return [QueryHistoryEntry(**h) for h in data.get("history", [])]
