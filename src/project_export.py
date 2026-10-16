import os
import json
import hashlib
import shutil
from typing import Dict, Any, List, Optional
import pandas as pd

class ProjectExportManager:
    def __init__(self, export_dir: str = ".dataforge/export"):
        self.export_dir = export_dir
        
    def generate_package(
        self,
        project_data: Dict[str, Any] = None,
        workspace=None,
        cleaned_tables: Optional[Dict[str, Any]] = None
    ) -> str:
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
            for root, _, files in os.walk(df_dir):
                # Don't recurse into export directory itself
                if os.path.abspath(root).startswith(os.path.abspath(self.export_dir)):
                    continue
                for f in files:
                    fpath = os.path.join(root, f)
                    if f.endswith(".json"):
                        # Keep filename or prefix with subdir name if not in root
                        rel_sub = os.path.relpath(root, df_dir)
                        dest_name = f if rel_sub == "." else f"{rel_sub}_{f}"
                        shutil.copy(fpath, os.path.join(meta_dir, dest_name))

            # Copy real persisted findings if present
            findings_src = os.path.join(df_dir, "findings.json")
            if os.path.exists(findings_src):
                shutil.copy(findings_src, os.path.join(pkg_dir, "findings", "findings.json"))

            # Copy real persisted model specification if present
            model_src = os.path.join(df_dir, "model_specification.json")
            if os.path.exists(model_src):
                shutil.copy(model_src, os.path.join(pkg_dir, "dashboard", "model_specification.json"))

            # Copy real generated reports/docs if present
            docs_src = os.path.join(df_dir, "docs")
            if os.path.exists(docs_src):
                for df_doc in os.listdir(docs_src):
                    src_doc_path = os.path.join(docs_src, df_doc)
                    if os.path.isfile(src_doc_path):
                        shutil.copy(src_doc_path, os.path.join(pkg_dir, "reports", df_doc))

            # Copy genuine persisted cleaned datasets if present
            cleaned_src = os.path.join(df_dir, "cleaned")
            if os.path.exists(cleaned_src):
                for cf in os.listdir(cleaned_src):
                    cf_path = os.path.join(cleaned_src, cf)
                    if os.path.isfile(cf_path):
                        shutil.copy(cf_path, os.path.join(pkg_dir, "cleaned", cf))

        # Write explicit cleaned tables if provided (e.g. from session state repair results)
        if cleaned_tables:
            cleaned_pkg_dir = os.path.join(pkg_dir, "cleaned")
            os.makedirs(cleaned_pkg_dir, exist_ok=True)
            df_cleaned_dir = os.path.join(workspace.project_root, ".dataforge", "cleaned")
            os.makedirs(df_cleaned_dir, exist_ok=True)
            for tname, tdata in cleaned_tables.items():
                if tdata is None:
                    continue
                out_name = f"{tname}_cleaned.csv" if not (tname.endswith(".csv") or tname.endswith(".parquet")) else tname
                pkg_out = os.path.join(cleaned_pkg_dir, out_name)
                df_out = os.path.join(df_cleaned_dir, out_name)
                if isinstance(tdata, pd.DataFrame):
                    tdata.to_csv(pkg_out, index=False)
                    tdata.to_csv(df_out, index=False)
                elif isinstance(tdata, str) and os.path.exists(tdata):
                    shutil.copy(tdata, pkg_out)
                    shutil.copy(tdata, df_out)

        # 3. Export metadata
        from datetime import datetime, timezone
        export_meta = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "project_name": getattr(workspace, "project_name", "DATAFORGE Project"),
            "table_count": len(workspace.registry),
            "tables": list(workspace.registry.keys()),
            "version": "1.0"
        }
        with open(os.path.join(pkg_dir, "export_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(export_meta, f, indent=2)

        # 4. Raw Data (immutably copied)
        for table_name, entry in workspace.registry.items():
            if os.path.exists(entry.file_path):
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
            for file in files:
                if file == "manifest.json":
                    continue
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, pkg_dir).replace('\\', '/')
                with open(filepath, "rb") as f:
                    manifest[rel_path] = hashlib.sha256(f.read()).hexdigest()
                    
        with open(os.path.join(pkg_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            
    def generate_export_metadata(self, pkg_dir: str) -> Dict[str, Any]:
        from datetime import datetime, timezone
        meta = {"exported_at": datetime.now(timezone.utc).isoformat(), "version": "1.0"}
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
            filepath = os.path.join(pkg_dir, rel_path)
            if not os.path.exists(filepath):
                return False
            with open(filepath, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != expected_hash:
                    return False
        return True
