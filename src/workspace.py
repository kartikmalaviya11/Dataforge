import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple
from enum import Enum
import pandas as pd
from loguru import logger

from src.ingestion import load_dataset, IngestionError, DatasetProfile

class TableStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    LOADED = "LOADED"
    ANALYZED = "ANALYZED"
    ERROR = "ERROR"
    MISSING = "MISSING"

@dataclass
class TableRegistryEntry:
    table_name: str
    file_name: str
    file_path: str
    file_type: str
    row_count: Optional[int]
    column_count: Optional[int]
    status: str  # Using str directly to easily serialize, but will be validated against TableStatus
    last_modified: float
    error_message: Optional[str] = None
    
class ProjectWorkspace:
    def __init__(self, project_root: str | Path, project_name: str = "DATAFORGE Project"):
        self.project_root = Path(project_root).resolve()
        self.project_name = project_name
        self.config_path = self.project_root / "project_config.json"
        self.registry: Dict[str, TableRegistryEntry] = {}
        
    def _normalize_table_name(self, filename: str) -> str:
        """Create a deterministic table name from filename."""
        name = Path(filename).stem.lower()
        # Strip common suffixes
        name = re.sub(r'_(dataset|table|data)$', '', name)
        # Replace non-alphanumeric with underscore
        name = re.sub(r'[^a-z0-9]', '_', name)
        name = name.strip('_')
        if not name:
            name = "table"
        return name
        
    def _resolve_collision(self, base_name: str) -> str:
        if base_name not in self.registry:
            return base_name
        counter = 1
        while f"{base_name}_{counter}" in self.registry:
            counter += 1
        return f"{base_name}_{counter}"

    def discover_datasets(self):
        """Scans the project_root for .csv and .xlsx files (non-recursive)."""
        if not self.project_root.exists():
            return
            
        for child in self.project_root.iterdir():
            if child.is_file() and child.suffix.lower() in [".csv", ".xlsx", ".xls"]:
                file_path_str = str(child.resolve())
                try:
                    last_mod = child.stat().st_mtime
                except Exception:
                    continue
                
                # Check if we already have this file by path
                existing_entry = next((e for e in self.registry.values() if e.file_path == file_path_str), None)
                
                if existing_entry:
                    if existing_entry.last_modified != last_mod:
                        # File changed
                        existing_entry.last_modified = last_mod
                        existing_entry.status = TableStatus.DISCOVERED.value
                        existing_entry.row_count = None
                        existing_entry.column_count = None
                        existing_entry.error_message = None
                    continue
                
                # New file
                base_name = self._normalize_table_name(child.name)
                table_name = self._resolve_collision(base_name)
                
                self.registry[table_name] = TableRegistryEntry(
                    table_name=table_name,
                    file_name=child.name,
                    file_path=file_path_str,
                    file_type=child.suffix.lower()[1:],
                    row_count=None,
                    column_count=None,
                    status=TableStatus.DISCOVERED.value,
                    last_modified=last_mod
                )

    def refresh_registry(self):
        """Checks for missing or changed files and updates the registry."""
        for table_name, entry in list(self.registry.items()):
            p = Path(entry.file_path)
            if not p.exists():
                entry.status = TableStatus.MISSING.value
            else:
                try:
                    last_mod = p.stat().st_mtime
                    if entry.last_modified != last_mod:
                        entry.last_modified = last_mod
                        entry.status = TableStatus.DISCOVERED.value
                        entry.row_count = None
                        entry.column_count = None
                        entry.error_message = None
                except Exception as e:
                    entry.status = TableStatus.ERROR.value
                    entry.error_message = f"Failed to access file: {e}"
        self.discover_datasets()
        
    def save(self):
        """Saves project configuration to disk."""
        # Ensure project root exists
        self.project_root.mkdir(parents=True, exist_ok=True)
        config = {
            "version": "1.0",
            "project_name": self.project_name,
            "project_root": str(self.project_root),
            "tables": {k: asdict(v) for k, v in self.registry.items()}
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            
    @classmethod
    def load(cls, project_root: str | Path):
        """Loads a project from the specified directory."""
        root = Path(project_root).resolve()
        workspace = cls(root)
        
        config_path = root / "project_config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                workspace.project_name = data.get("project_name", "DATAFORGE Project")
                
                tables_data = data.get("tables", {})
                for table_name, t_data in tables_data.items():
                    workspace.registry[table_name] = TableRegistryEntry(**t_data)
            except Exception as e:
                logger.error(f"Failed to load project config: {e}")
                try:
                    import shutil
                    backup_path = root / "project_config.corrupted.bak"
                    shutil.copy2(config_path, backup_path)
                    logger.warning(f"Preserved corrupted config to {backup_path}")
                except Exception as backup_err:
                    logger.error(f"Failed to backup corrupt config: {backup_err}")
                
        # Validate existing state
        workspace.refresh_registry()
        workspace.save() # save any changes from refresh
        return workspace
        
    def load_table(self, table_name: str, **kwargs) -> Tuple[pd.DataFrame, DatasetProfile]:
        """Loads the table's data and profile, caching row/col counts."""
        if table_name not in self.registry:
            raise ValueError(f"Table '{table_name}' not found in registry")
            
        entry = self.registry[table_name]
        if entry.status == TableStatus.MISSING.value:
            raise IngestionError(f"Cannot load missing file for table '{table_name}'")
            
        try:
            df, profile = load_dataset(entry.file_path, **kwargs)
            entry.row_count = profile.row_count
            entry.column_count = profile.column_count
            entry.status = TableStatus.LOADED.value
            entry.error_message = None
            self.save()
            return df, profile
        except Exception as e:
            entry.status = TableStatus.ERROR.value
            entry.error_message = str(e)
            self.save()
            raise e
            
    def mark_analyzed(self, table_name: str):
        if table_name in self.registry:
            self.registry[table_name].status = TableStatus.ANALYZED.value
            self.save()
