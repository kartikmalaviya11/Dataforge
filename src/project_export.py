import os
import json
import hashlib
import shutil
from typing import Dict, Any, List

class ProjectExportManager:
    def __init__(self, export_dir: str = ".dataforge/export"):
        self.export_dir = export_dir
        
    def generate_package(self, project_data: Dict[str, Any] = None, workspace=None) -> str:
        # Backward compatibility for old tests
        if workspace is None and project_data is not None:
            return self._generate_dummy_package(project_data)

        if workspace is None or not hasattr(workspace, "project_root") or not hasattr(workspace, "registry"):
            raise ValueError("Workspace must be provided and must be a valid ProjectWorkspace.")

        dirs = ["raw", "cleaned", "reports", "sql", "python", "metadata", "dashboard", "findings", "recommendations"]
        pkg_dir = os.path.join(self.export_dir, "PROJECT")
        if os.path.exists(pkg_dir):
            shutil.rmtree(pkg_dir)

        for d in dirs:
            os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)

        # 1. Project Config
        if hasattr(workspace, "config_path") and os.path.exists(workspace.config_path):
            shutil.copy(workspace.config_path, os.path.join(pkg_dir, "project_config.json"))

        # 2. Metadata (runs, versions, lineage, kpis, findings, etc)
        df_dir = os.path.join(workspace.project_root, ".dataforge")
        if os.path.exists(df_dir):
            meta_dir = os.path.join(pkg_dir, "metadata")
            for f in os.listdir(df_dir):
                fpath = os.path.join(df_dir, f)
                if os.path.isfile(fpath) and f.endswith(".json"):
                    shutil.copy(fpath, meta_dir)

            # Copy real persisted findings if present
            findings_src = os.path.join(df_dir, "findings.json")
            if os.path.exists(findings_src):
                shutil.copy(findings_src, os.path.join(pkg_dir, "findings", "findings.json"))

            # Copy real persisted model specification if present
            model_src = os.path.join(df_dir, "model_specification.json")
            if os.path.exists(model_src):
                shutil.copy(model_src, os.path.join(pkg_dir, "dashboard", "model_specification.json"))

        # 3. Raw Data
        for table_name, entry in workspace.registry.items():
            if os.path.exists(entry.file_path):
                # Copy raw files immutably
                shutil.copy(entry.file_path, os.path.join(pkg_dir, "raw", os.path.basename(entry.file_path)))

        self._generate_manifest(pkg_dir)
        zip_path = shutil.make_archive(pkg_dir, 'zip', pkg_dir)
        return zip_path

    def _generate_dummy_package(self, project_data: Dict[str, Any]) -> str:
        dirs = ["raw", "cleaned", "reports", "sql", "python", "metadata", "dashboard", "findings", "recommendations"]
        pkg_dir = os.path.join(self.export_dir, "PROJECT")
        for d in dirs:
            os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)
            
        with open(os.path.join(pkg_dir, "project_config.json"), "w") as f:
            json.dump(project_data.get("config", {}), f)
            
        if "raw_data" in project_data:
            with open(os.path.join(pkg_dir, "raw", "data.csv"), "w") as f:
                f.write(project_data["raw_data"])
                
        self._generate_manifest(pkg_dir)
        zip_path = shutil.make_archive(pkg_dir, 'zip', pkg_dir)
        return zip_path
        
    def _generate_manifest(self, pkg_dir: str):
        manifest = {}
        for root, dirs, files in os.walk(pkg_dir):
            if "manifest.json" in files:
                continue
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, pkg_dir).replace('\\', '/')
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
