import os
import json
import tempfile
import pytest
from src.dashboard_blueprint import DashboardBlueprintManager, DashboardBlueprint, DashboardPage, Visual

@pytest.fixture
def workspace_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_generate_blueprint(workspace_dir):
    manager = DashboardBlueprintManager(workspace_dir)
    kpis = [
        {"id": "k1", "name": "Total Revenue", "description": "Sum of all sales"}
    ]
    questions = [
        {"id": "q1", "text": "What is the revenue by region?"}
    ]
    
    bp = manager.generate_blueprint("Sales Dashboard", kpis, questions)
    
    assert bp.title == "Sales Dashboard"
    assert len(bp.pages) == 2
    assert bp.pages[0].title == "Overview"
    assert len(bp.pages[0].visuals) == 1
    assert bp.pages[0].visuals[0].type == "scorecard"
    assert "k1" in bp.pages[0].visuals[0].kpi_refs
    
    assert bp.pages[1].title == "Detailed Analysis"
    assert len(bp.pages[1].visuals) == 1
    assert bp.pages[1].visuals[0].type == "bar_chart"
    assert "q1" in bp.pages[1].visuals[0].question_refs

def test_persistence(workspace_dir):
    manager1 = DashboardBlueprintManager(workspace_dir)
    kpis = [{"id": "k1", "name": "Total Revenue"}]
    questions = []
    
    bp = manager1.generate_blueprint("My Dashboard", kpis, questions)
    bp_id = bp.id
    
    # Reload manager
    manager2 = DashboardBlueprintManager(workspace_dir)
    loaded_bp = manager2.get_blueprint(bp_id)
    
    assert loaded_bp is not None
    assert loaded_bp.title == "My Dashboard"
    assert len(loaded_bp.pages) == 2
    assert len(loaded_bp.pages[0].visuals) == 1
    assert loaded_bp.pages[0].visuals[0].kpi_refs == ["k1"]

def test_delete_blueprint(workspace_dir):
    manager = DashboardBlueprintManager(workspace_dir)
    bp = manager.generate_blueprint("To Delete", [], [])
    
    assert manager.get_blueprint(bp.id) is not None
    
    deleted = manager.delete_blueprint(bp.id)
    assert deleted is True
    assert manager.get_blueprint(bp.id) is None
    
    # Reload to ensure deleted on disk
    manager2 = DashboardBlueprintManager(workspace_dir)
    assert manager2.get_blueprint(bp.id) is None
