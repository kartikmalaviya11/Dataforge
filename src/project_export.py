
import os
import json
import hashlib
from typing import Dict, Any, List

class ProjectExportManager:
    def __init__(self, export_dir: str = ".dataforge/export"):
        self.export_dir = export_dir
        
    def generate_package(self, project_data: Dict[str, Any]) -> str:
        # Structure: raw/, cleaned/, reports/, sql/, python/, metadata/, dashboard/, findings/, recommendations/
        dirs = ["raw", "cleaned", "reports", "sql", "python", "metadata", "dashboard", "findings", "recommendations"]
        pkg_dir = os.path.join(self.export_dir, "PROJECT")
        for d in dirs:
            os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)
            
        with open(os.path.join(pkg_dir, "project_config.json"), "w") as f:
            json.dump(project_data.get("config", {}), f)
            
        # Write some dummy artifacts
        if "raw_data" in project_data:
            with open(os.path.join(pkg_dir, "raw", "data.csv"), "w") as f:
                f.write(project_data["raw_data"])
                
        self._generate_manifest(pkg_dir)
        return pkg_dir
        
    def _generate_manifest(self, pkg_dir: str):
        manifest = {}
        for root, dirs, files in os.walk(pkg_dir):
            if "manifest.json" in files:
                continue
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, pkg_dir)
                with open(filepath, "rb") as f:
                    manifest[rel_path] = hashlib.sha256(f.read()).hexdigest()
                    
        with open(os.path.join(pkg_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            
    def generate_export_metadata(self, pkg_dir: str) -> Dict[str, Any]:
        meta = {"exported_at": "2026-09-27T00:00:00Z", "version": "1.0"}
        with open(os.path.join(pkg_dir, "export_metadata.json"), "w") as f:
            json.dump(meta, f)
        return meta

    def verify_package(self, pkg_dir: str) -> bool:
        manifest_path = os.path.join(pkg_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return False
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
        for rel_path, expected_hash in manifest.items():
            if rel_path == "export_metadata.json": continue
            filepath = os.path.join(pkg_dir, rel_path)
            if not os.path.exists(filepath):
                return False
            with open(filepath, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != expected_hash:
                    return False
        return True
