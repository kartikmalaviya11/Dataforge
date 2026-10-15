from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
import hashlib
import pandas as pd

@dataclass
class DatasetVersion:
    version_id: str
    parent_version_id: Optional[str]
    version_type: str
    created_at: str
    source_hash: str
    row_count: int
    table_count: int
    schema_hash: str
    change_summary: Dict[str, Any] = field(default_factory=dict)
    status: str = "ACTIVE"
    column_count: Optional[int] = None

class DatasetVersioningManager:
    def __init__(self, persistence_dir: str = ".dataforge/dataset_versioning"):
        self.persistence_dir = persistence_dir
        os.makedirs(self.persistence_dir, exist_ok=True)
        self.versions: Dict[str, DatasetVersion] = {}
        self.load()

    def _get_path(self) -> str:
        return os.path.join(self.persistence_dir, "versions.json")

    def load(self):
        path = self._get_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    # Preserve original table_count. Do not pop it to column_count.
                    # Missing optional fields (e.g. column_count in legacy records)
                    # will safely fall back to the dataclass default of None.
                    self.versions[k] = DatasetVersion(**v)

    def save(self):
        path = self._get_path()
        with open(path, "w", encoding="utf-8") as f:
            data = {k: asdict(v) for k, v in sorted(self.versions.items())}
            json.dump(data, f, indent=2, sort_keys=True)

    def create_version(self, version_type: str, source_hash: str, row_count: int, table_count: int, schema_hash: str, parent_version_id: Optional[str] = None, change_summary: Dict[str, Any] = None, column_count: Optional[int] = None) -> str:
        version_id = hashlib.sha256(f"{parent_version_id}_{version_type}_{source_hash}".encode()).hexdigest()[:16]
        record = DatasetVersion(
            version_id=version_id,
            parent_version_id=parent_version_id,
            version_type=version_type,
            created_at=datetime.utcnow().isoformat(),
            source_hash=source_hash,
            row_count=row_count,
            table_count=table_count,
            schema_hash=schema_hash,
            change_summary=change_summary or {},
            column_count=column_count
        )
        self.versions[version_id] = record
        self.save()
        return version_id

    def get_version(self, version_id: str) -> Optional[DatasetVersion]:
        return self.versions.get(version_id)

    def get_all_versions(self) -> List[DatasetVersion]:
        return [self.versions[k] for k in sorted(self.versions.keys())]

    def compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def compute_df_hash(self, df: pd.DataFrame) -> str:
        return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values).hexdigest()
