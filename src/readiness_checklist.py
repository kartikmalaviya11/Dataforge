
from typing import Dict

class ReadinessChecklist:
    def __init__(self):
        self.items = {
            "Data Audit": "NOT_RUN",
            "Cleaning": "NOT_RUN",
            "Validation": "NOT_RUN",
            "Relationships": "NOT_RUN",
            "SQL Analysis": "NOT_RUN",
            "Pandas Analysis": "NOT_RUN",
            "KPI Validation": "NOT_RUN",
            "Business Problems": "NOT_RUN",
            "RCA": "NOT_RUN",
            "Recommendations": "NOT_RUN",
            "Power BI Model": "NOT_RUN",
            "Dashboard": "NOT_RUN",
            "Documentation": "NOT_RUN"
        }

    def update_item(self, item: str, status: str):
        if item in self.items and status in ["PASS", "FAIL", "WARNING", "NOT_RUN"]:
            self.items[item] = status

    def evaluate_overall(self) -> str:
        statuses = set(self.items.values())
        if "FAIL" in statuses or "NOT_RUN" in statuses:
            return "BLOCKED"
        elif "WARNING" in statuses:
            return "READY_WITH_WARNINGS"
        else:
            return "READY"

    def get_status(self) -> Dict[str, str]:
        # Return sorted for determinism
        return dict(sorted(self.items.items()))
