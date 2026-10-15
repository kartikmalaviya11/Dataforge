
import json
import os
from typing import Dict, Any

class DocumentationGenerator:
    def __init__(self, persistence_dir: str = ".dataforge/docs"):
        self.persistence_dir = persistence_dir
        os.makedirs(self.persistence_dir, exist_ok=True)
        
    def generate_data_dictionary(self, metadata: Dict[str, Any]) -> str:
        cols = metadata.get("columns", [])
        if not cols:
            return "No columns metadata provided."
        doc = "# Data Dictionary\n\n"
        for c in sorted(cols, key=lambda x: x["name"]):
            doc += f"- **{c['name']}** ({c.get('type', 'Unknown')}): {c.get('description', '')}\n"
        return doc
        
    def generate_data_quality_report(self, metadata: Dict[str, Any]) -> str:
        score = metadata.get("quality_score", 0)
        return f"# Data Quality Report\n\nScore: {score}\n"
        
    def generate_cleaning_log(self, metadata: Dict[str, Any]) -> str:
        logs = metadata.get("cleaning_logs", [])
        doc = "# Cleaning Log\n\n"
        for l in logs:
            doc += f"- {l}\n"
        return doc
        
    def generate_relationship_report(self, metadata: Dict[str, Any]) -> str:
        rels = metadata.get("relationships", [])
        doc = "# Relationship Report\n\n"
        for r in rels:
            doc += f"- {r['from']} -> {r['to']}\n"
        return doc
        
    def generate_kpi_dictionary(self, metadata: Dict[str, Any]) -> str:
        return "# KPI Dictionary\n\n" + json.dumps(metadata.get("kpis", {}), indent=2)
        
    def generate_sql_documentation(self, metadata: Dict[str, Any]) -> str:
        return "# SQL Documentation\n\n" + "\n".join(metadata.get("sql_queries", []))
        
    def generate_findings_report(self, metadata: Dict[str, Any]) -> str:
        return "# Findings Report\n\n" + "\n".join(metadata.get("findings", []))
        
    def generate_project_summary(self, metadata: Dict[str, Any]) -> str:
        return "# Project Summary\n\n" + metadata.get("summary", "")

    @classmethod
    def compile_project_metadata(
        cls,
        workspace: Any,
        table_results: Optional[Dict[str, Any]] = None,
        kpis: Optional[List[Any]] = None,
        findings: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Compile genuine project metadata from workspace tables, profiles, quality metrics,
        accepted relationships, KPIs, run history, and findings.
        Never fabricates missing data.
        """
        cols = []
        if table_results:
            for tname, tres in sorted(table_results.items()):
                types_data = tres.get("types")
                if isinstance(types_data, dict):
                    for cname, tinfo in sorted(types_data.items()):
                        t_type = getattr(tinfo, "detected_type", str(tinfo))
                        cols.append({"name": f"{tname}.{cname}", "type": t_type, "description": f"Column {cname} in {tname}"})
                elif isinstance(types_data, list):
                    for tinfo in types_data:
                        cname = getattr(tinfo, "column_name", getattr(tinfo, "column", ""))
                        t_type = getattr(tinfo, "detected_type", "Unknown")
                        if cname:
                            cols.append({"name": f"{tname}.{cname}", "type": t_type, "description": f"Column {cname} in {tname}"})
                elif tres.get("df") is not None:
                    df = tres.get("repaired_df") if tres.get("repaired_df") is not None else tres.get("df")
                    for cname in df.columns:
                        cols.append({"name": f"{tname}.{cname}", "type": str(df[cname].dtype), "description": f"Column {cname} in {tname}"})

        if not cols and hasattr(workspace, "registry") and workspace.registry:
            for tname in sorted(workspace.registry.keys()):
                try:
                    df, _ = workspace.load_table(tname)
                    if df is not None:
                        for cname in df.columns:
                            cols.append({"name": f"{tname}.{cname}", "type": str(df[cname].dtype), "description": f"Column {cname} in {tname}"})
                except Exception:
                    pass

        # Quality score
        scores = []
        if table_results:
            for tres in table_results.values():
                if "quality" in tres and hasattr(tres["quality"], "overall_score"):
                    scores.append(tres["quality"].overall_score)
                elif "readiness" in tres and hasattr(tres["readiness"], "overall_score"):
                    scores.append(tres["readiness"].overall_score)
                elif isinstance(tres.get("quality_score"), (int, float)):
                    scores.append(tres["quality_score"])
        quality_score = round(sum(scores) / len(scores), 2) if scores else 0

        # Cleaning logs from RunHistory
        cleaning_logs = []
        try:
            from src.run_history import RunHistoryManager
            rhm = RunHistoryManager(workspace.project_root)
            runs = rhm.get_all_runs()
            for r in runs:
                op = r.cleaning_summary.get("operation") if isinstance(r.cleaning_summary, dict) else r.run_id
                cleaning_logs.append(f"Run {r.run_id} ({r.status}): {op}")
        except Exception:
            pass

        # Relationships
        relationships = []
        try:
            from src.model_generator import ModelGenerator
            spec = ModelGenerator.load_specification(os.path.join(workspace.project_root, ".dataforge"))
            if spec and "relationships" in spec:
                for r in spec["relationships"]:
                    status = r.get("relationship_status") or r.get("status")
                    if status in ("VALID", "ACCEPTED", "ModelStatus.VALID"):
                        src = f"{r.get('source_table')}.{r.get('source_column')}"
                        tgt = f"{r.get('target_table')}.{r.get('target_column')}"
                        relationships.append({"from": src, "to": tgt})
        except Exception:
            pass

        if not relationships and hasattr(workspace, "project_root"):
            rel_path = os.path.join(workspace.project_root, ".dataforge", "relationships.json")
            if os.path.exists(rel_path):
                try:
                    with open(rel_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        candidates = data if isinstance(data, list) else data.get("candidates", [])
                        for c in candidates:
                            if c.get("status") == "ACCEPTED":
                                relationships.append({
                                    "from": f"{c.get('source_table')}.{c.get('source_column')}",
                                    "to": f"{c.get('target_table')}.{c.get('target_column')}"
                                })
                except Exception:
                    pass

        # KPIs
        kpis_dict = {}
        if kpis:
            for k in kpis:
                k_name = getattr(k, "kpi_name", k.get("kpi_name", "KPI") if isinstance(k, dict) else str(k))
                k_val = getattr(k, "formula", k.get("formula", "") if isinstance(k, dict) else "")
                kpis_dict[k_name] = k_val
        elif hasattr(workspace, "project_root") or isinstance(workspace, str):
            try:
                from src.kpi_engine import KPIManager
                ws_obj = workspace if hasattr(workspace, "project_root") else type("Obj", (), {"project_root": str(workspace)})()
                km = KPIManager(ws_obj)
                loaded_kpis = km.load_kpis()
                for k in loaded_kpis:
                    kpis_dict[k.kpi_name] = k.formula or k.business_definition or "KPI Metric"
            except Exception:
                pass

        # Findings
        findings_list = []
        if findings:
            for f in findings:
                f_title = getattr(f, "problem", getattr(f, "title", str(f)))
                f_desc = getattr(f, "evidence_statement", getattr(f, "description", ""))
                findings_list.append(f"{f_title}: {f_desc}".strip(": "))
        elif hasattr(workspace, "project_root"):
            try:
                from src.finding_engine import FindingEngine
                fe = FindingEngine(workspace)
                loaded_f = fe.load_findings()
                for f in loaded_f:
                    f_title = getattr(f, "problem", getattr(f, "title", str(f)))
                    f_desc = getattr(f, "evidence_statement", getattr(f, "description", ""))
                    findings_list.append(f"{f_title}: {f_desc}".strip(": "))
            except Exception:
                pass

        # Summary
        table_names = sorted(workspace.registry.keys()) if hasattr(workspace, "registry") and workspace.registry else []
        if table_names:
            summary = f"Project workspace at {workspace.project_root} with {len(table_names)} registered table(s): {', '.join(table_names)}."
        else:
            p_root = getattr(workspace, "project_root", "Unknown")
            summary = f"Project workspace at {p_root} with 0 registered tables."

        return {
            "columns": cols,
            "quality_score": quality_score,
            "cleaning_logs": cleaning_logs,
            "relationships": relationships,
            "kpis": kpis_dict,
            "sql_queries": [],
            "findings": findings_list,
            "summary": summary
        }

    def generate_all(self, metadata: Dict[str, Any]):
        docs = {
            "data_dictionary.md": self.generate_data_dictionary(metadata),
            "data_quality_report.md": self.generate_data_quality_report(metadata),
            "cleaning_log.md": self.generate_cleaning_log(metadata),
            "relationship_report.md": self.generate_relationship_report(metadata),
            "kpi_dictionary.md": self.generate_kpi_dictionary(metadata),
            "sql_documentation.md": self.generate_sql_documentation(metadata),
            "findings_report.md": self.generate_findings_report(metadata),
            "project_summary.md": self.generate_project_summary(metadata),
        }
        for name, content in docs.items():
            with open(os.path.join(self.persistence_dir, name), "w", encoding="utf-8") as f:
                f.write(content)
        return docs
