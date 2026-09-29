import pytest
import os
import json
from src.domain_templates import DomainTemplateManager, TemplateMapping
from src.workspace import ProjectWorkspace

@pytest.fixture
def workspace(tmp_path):
    return ProjectWorkspace(tmp_path)

def test_list_templates(workspace):
    manager = DomainTemplateManager(workspace)
    templates = manager.get_available_templates()
    assert "E-commerce" in templates
    assert "Sales" in templates
    assert "Customer Retention" in templates
    assert "Delivery" in templates
    assert "Seller Performance" in templates
    assert "Product Performance" in templates
    assert "Reviews" in templates

def test_load_template(workspace):
    manager = DomainTemplateManager(workspace)
    template = manager.load_template("E-commerce")
    assert "questions" in template
    assert "kpis" in template
    assert len(template["questions"]) > 0
    assert len(template["kpis"]) > 0
    
def test_apply_template_explicit_mapping(workspace):
    manager = DomainTemplateManager(workspace)
    template = manager.load_template("Sales")
    
    mapping = TemplateMapping(
        table_mapping={"sales_data": "my_sales_table"},
        column_mapping={"revenue": "total_revenue", "order_date": "date"}
    )
    
    questions, kpis = manager.apply_template("Sales", mapping)
    
    assert len(questions) > 0
    assert len(kpis) > 0
    
def test_save_custom_template(workspace):
    manager = DomainTemplateManager(workspace)
    custom_template = {
        "questions": [{"question": "What is the custom metric?", "description": "Custom"}],
        "kpis": [{
            "kpi_name": "Custom KPI", 
            "business_definition": "Custom", 
            "metric_definitions": [],
            "source_tables": [],
            "source_columns": [],
            "unit": "Count",
            "description": "None"
        }]
    }
    
    manager.save_template("My Custom Domain", custom_template)
    
    templates = manager.get_available_templates()
    assert "My Custom Domain" in templates
    
    loaded = manager.load_template("My Custom Domain")
    assert loaded["questions"][0]["question"] == "What is the custom metric?"
