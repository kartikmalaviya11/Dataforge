import json
import os
import copy
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field

from src.workspace import ProjectWorkspace
from src.business_questions import BusinessQuestion
from src.kpi_engine import KPIDefinition, MetricDefinition, FilterDefinition

@dataclass
class TemplateMapping:
    table_mapping: Dict[str, str] = field(default_factory=dict)
    column_mapping: Dict[str, str] = field(default_factory=dict)

# Built-in templates defining real questions and KPIs
BUILTIN_TEMPLATES = {
    "E-commerce": {
        "questions": [
            {"question": "What is the total revenue over time?", "description": "Track revenue trends."},
            {"question": "What is the conversion rate?", "description": "Measure how many visitors purchase."}
        ],
        "kpis": [
            {
                "kpi_name": "Total Revenue",
                "business_definition": "Total amount of revenue generated.",
                "formula": "SUM(revenue)",
                "metric_definitions": [
                    {
                        "metric_name": "Revenue Sum",
                        "operation": "SUM",
                        "source_table": "sales_data",
                        "source_column": "revenue"
                    }
                ],
                "source_tables": ["sales_data"],
                "source_columns": ["revenue"],
                "unit": "Currency",
                "description": "Total revenue"
            }
        ]
    },
    "Sales": {
        "questions": [
            {"question": "Who are the top performing sales reps?", "description": "Identify best sales personnel."},
            {"question": "What is the win rate for opportunities?", "description": "Percentage of won deals."}
        ],
        "kpis": [
            {
                "kpi_name": "Total Sales",
                "business_definition": "Total sales volume.",
                "formula": "SUM(amount)",
                "metric_definitions": [
                    {
                        "metric_name": "Sales Volume",
                        "operation": "SUM",
                        "source_table": "opportunities",
                        "source_column": "amount"
                    }
                ],
                "source_tables": ["opportunities"],
                "source_columns": ["amount"],
                "unit": "Currency",
                "description": "Sales volume"
            }
        ]
    },
    "Customer Retention": {
        "questions": [
            {"question": "What is the customer churn rate?", "description": "Percentage of customers lost."},
            {"question": "What is the average customer lifetime value?", "description": "CLV."}
        ],
        "kpis": [
            {
                "kpi_name": "Churn Rate",
                "business_definition": "Rate of churn.",
                "formula": "Churned / Total",
                "metric_definitions": [],
                "source_tables": ["customers"],
                "source_columns": ["status"],
                "unit": "Percentage",
                "description": "Churn rate"
            }
        ]
    },
    "Delivery": {
        "questions": [
            {"question": "What is the average delivery time?", "description": "Time taken to deliver."},
            {"question": "How many orders were delayed?", "description": "Count of delayed orders."}
        ],
        "kpis": [
            {
                "kpi_name": "Average Delivery Time",
                "business_definition": "Average days to deliver.",
                "formula": "AVG(delivery_days)",
                "metric_definitions": [],
                "source_tables": ["deliveries"],
                "source_columns": ["delivery_days"],
                "unit": "Days",
                "description": "Delivery Time"
            }
        ]
    },
    "Seller Performance": {
        "questions": [
            {"question": "Which sellers have the highest ratings?", "description": "Top rated sellers."}
        ],
        "kpis": [
            {
                "kpi_name": "Seller Rating",
                "business_definition": "Average rating of sellers.",
                "formula": "AVG(rating)",
                "metric_definitions": [],
                "source_tables": ["sellers"],
                "source_columns": ["rating"],
                "unit": "Score",
                "description": "Seller Rating"
            }
        ]
    },
    "Product Performance": {
        "questions": [
            {"question": "What are the best-selling products?", "description": "Top products by volume."}
        ],
        "kpis": [
            {
                "kpi_name": "Product Sales Volume",
                "business_definition": "Total volume of products sold.",
                "formula": "SUM(quantity)",
                "metric_definitions": [],
                "source_tables": ["products"],
                "source_columns": ["quantity"],
                "unit": "Count",
                "description": "Product Volume"
            }
        ]
    },
    "Reviews": {
        "questions": [
            {"question": "What is the average product review score?", "description": "Avg score."}
        ],
        "kpis": [
            {
                "kpi_name": "Average Review Score",
                "business_definition": "Average score of reviews.",
                "formula": "AVG(score)",
                "metric_definitions": [],
                "source_tables": ["reviews"],
                "source_columns": ["score"],
                "unit": "Score",
                "description": "Average Review Score"
            }
        ]
    }
}

class DomainTemplateManager:
    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace
        self.custom_templates_file = os.path.join(workspace.project_root, ".dataforge", "domain_templates.json")
        os.makedirs(os.path.dirname(self.custom_templates_file), exist_ok=True)
        self.custom_templates: Dict[str, Any] = {}
        self._load_custom_templates()

    def _load_custom_templates(self):
        if os.path.exists(self.custom_templates_file):
            try:
                with open(self.custom_templates_file, "r", encoding="utf-8") as f:
                    self.custom_templates = json.load(f)
            except (json.JSONDecodeError, ValueError):
                self.custom_templates = {}
                
    def _save_custom_templates(self):
        with open(self.custom_templates_file, "w", encoding="utf-8") as f:
            json.dump(self.custom_templates, f, indent=2)

    def get_available_templates(self) -> List[str]:
        return list(BUILTIN_TEMPLATES.keys()) + list(self.custom_templates.keys())

    def load_template(self, template_name: str) -> Dict[str, Any]:
        if template_name in self.custom_templates:
            return copy.deepcopy(self.custom_templates[template_name])
        elif template_name in BUILTIN_TEMPLATES:
            return copy.deepcopy(BUILTIN_TEMPLATES[template_name])
        else:
            raise ValueError(f"Template '{template_name}' not found.")

    def save_template(self, template_name: str, template_data: Dict[str, Any]):
        self.custom_templates[template_name] = template_data
        self._save_custom_templates()

    def apply_template(
        self, template_name: str, mapping: TemplateMapping
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Applies a template by mapping the generic tables and columns to user-specific ones.
        Returns a tuple of (questions, kpis) where kpis have their source tables and columns updated.
        We return dict representations ready to be instantiated as BusinessQuestion / KPIDefinition elsewhere.
        """
        template = self.load_template(template_name)
        
        questions = template.get("questions", [])
        kpis = template.get("kpis", [])
        
        # Apply mappings to KPIs
        for kpi in kpis:
            # Map source tables
            new_tables = []
            for t in kpi.get("source_tables", []):
                new_tables.append(mapping.table_mapping.get(t, t))
            kpi["source_tables"] = list(set(new_tables))
            
            # Map source columns
            new_columns = []
            for c in kpi.get("source_columns", []):
                new_columns.append(mapping.column_mapping.get(c, c))
            kpi["source_columns"] = list(set(new_columns))
            
            # Map within metric definitions
            for m in kpi.get("metric_definitions", []):
                if "source_table" in m:
                    m["source_table"] = mapping.table_mapping.get(m["source_table"], m["source_table"])
                if "source_column" in m:
                    m["source_column"] = mapping.column_mapping.get(m["source_column"], m["source_column"])
                    
                # Filters could also have column mappings applied
                if "filters" in m and m["filters"]:
                    for f in m["filters"]:
                        if "column" in f:
                            f["column"] = mapping.column_mapping.get(f["column"], f["column"])
                            
        return questions, kpis
