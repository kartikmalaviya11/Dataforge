import os
import json
import pytest
from src.workspace import ProjectWorkspace
from src.finding_engine import FindingDefinition
from src.insight_mapping import InsightVisualMapper, ChartMapping

@pytest.fixture
def temp_workspace(tmp_path):
    ws = ProjectWorkspace(str(tmp_path))
    return ws

@pytest.fixture
def mapper(temp_workspace):
    return InsightVisualMapper(temp_workspace)

def test_generate_mapping_trend(mapper):
    finding = FindingDefinition(
        finding_id="fnd_123",
        problem="Revenue trend analysis",
        evidence_statement="Revenue is growing over time",
        created_at=123.0,
        updated_at=123.0
    )
    mapping = mapper.generate_mapping(finding)
    assert mapping.chart_type == "Line"
    assert mapping.finding_id == "fnd_123"
    assert mapping.metric == "Unknown Metric"

def test_generate_mapping_comparison(mapper):
    finding = FindingDefinition(
        finding_id="fnd_456",
        problem="Sales by region",
        evidence_statement="Compare sales in US vs EU",
        created_at=123.0,
        updated_at=123.0,
        comparison_value=50.0
    )
    mapping = mapper.generate_mapping(finding)
    assert mapping.chart_type == "Bar"
    assert mapping.metric == "Unknown Metric"

def test_generate_mapping_comparison_fixed(mapper):
    finding = FindingDefinition(
        finding_id="fnd_456",
        problem="Sales by region",
        evidence_statement="Compare sales in US vs EU",
        created_at=123.0,
        updated_at=123.0,
        comparison_value=50.0,
        metric_value=100.0
    )
    mapping = mapper.generate_mapping(finding)
    assert mapping.chart_type == "Bar"
    assert mapping.metric == "Metric Value"

def test_validate_mapping(mapper):
    finding = FindingDefinition(
        finding_id="fnd_789",
        problem="Sales distribution",
        evidence_statement="Distribution of order values",
        created_at=123.0,
        updated_at=123.0
    )
    mapping = mapper.generate_mapping(finding)
    assert mapping.chart_type == "Histogram"
    
    assert mapper.validate_mapping(mapping.mapping_id) == True

    # Test invalid chart type
    mapping.chart_type = "Pie"
    mapper.save_mappings()
    assert mapper.validate_mapping(mapping.mapping_id) == False

def test_edit_mapping(mapper):
    finding = FindingDefinition(
        finding_id="fnd_111",
        problem="Some relationship",
        evidence_statement="Correlation between X and Y",
        created_at=123.0,
        updated_at=123.0
    )
    mapping = mapper.generate_mapping(finding)
    assert mapping.chart_type == "Scatter"

    edited = mapper.edit_mapping(mapping.mapping_id, chart_type="Line", dashboard_page="New Page")
    assert edited.chart_type == "Line"
    assert edited.dashboard_page == "New Page"

    fetched = mapper.get_mapping(mapping.mapping_id)
    assert fetched.chart_type == "Line"
    assert fetched.dashboard_page == "New Page"

def test_export_mappings(mapper, tmp_path):
    finding = FindingDefinition(
        finding_id="fnd_222",
        problem="General insight",
        evidence_statement="Something happened",
        created_at=123.0,
        updated_at=123.0
    )
    mapper.generate_mapping(finding)
    
    export_path = tmp_path / "exports.json"
    success = mapper.export_mappings(str(export_path))
    assert success == True
    
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["chart_type"] == "KPI Card"

def test_persistence(temp_workspace):
    mapper1 = InsightVisualMapper(temp_workspace)
    finding = FindingDefinition(
        finding_id="fnd_333",
        problem="Trend",
        evidence_statement="Upward",
        created_at=123.0,
        updated_at=123.0
    )
    mapping = mapper1.generate_mapping(finding)
    
    mapper2 = InsightVisualMapper(temp_workspace)
    assert len(mapper2.mappings) == 1
    assert mapper2.mappings[0].mapping_id == mapping.mapping_id
    assert mapper2.mappings[0].chart_type == "Line"
