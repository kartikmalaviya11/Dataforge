
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
