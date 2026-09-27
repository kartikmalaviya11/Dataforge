import pytest
import os
import tempfile
import time
from src.workspace import ProjectWorkspace
from src.finding_engine import FindingEngine, FindingDefinition, InterpretationType

@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory() as tmp:
        ws = ProjectWorkspace(tmp)
        yield ws

@pytest.fixture
def finding_engine(workspace):
    return FindingEngine(workspace)

def test_create_and_load_finding(finding_engine, workspace):
    f = FindingDefinition(
        finding_id="f1",
        problem="High bounce rate",
        evidence_statement="Bounce rate increased by 20%",
        created_at=time.time(),
        updated_at=time.time(),
        metric_value=0.6,
        comparison_value=0.5,
        comparison_context="last month",
        system_generated_association="Observed Association: 20% increase",
        analyst_interpretation="Might be due to new layout",
        interpretation_type="ANALYST_HYPOTHESIS",
        impact="Low conversion",
        recommendation="A/B test old layout"
    )
    
    finding_engine.save_finding(f)
    
    fe2 = FindingEngine(workspace)
    loaded = fe2.load_findings()
    assert len(loaded) == 1
    l = loaded[0]
    assert l.problem == "High bounce rate"
    assert l.evidence_statement == "Bounce rate increased by 20%"
    assert l.system_generated_association == "Observed Association: 20% increase"
    assert l.analyst_interpretation == "Might be due to new layout"
    assert l.interpretation_type == "ANALYST_HYPOTHESIS"
    assert l.is_archived is False

def test_causality_safety_invalid_type(finding_engine):
    f = FindingDefinition(
        finding_id="f2",
        problem="Test",
        evidence_statement="Test",
        created_at=time.time(),
        updated_at=time.time(),
        interpretation_type="ROOT_CAUSE" # Invalid
    )
    with pytest.raises(ValueError, match="Invalid interpretation_type"):
        finding_engine.save_finding(f)

def test_archive_finding(finding_engine):
    f = FindingDefinition(
        finding_id="f_arch",
        problem="Test",
        evidence_statement="Test",
        created_at=time.time(),
        updated_at=time.time()
    )
    finding_engine.save_finding(f)
    finding_engine.archive_finding("f_arch")
    assert finding_engine.get_finding("f_arch").is_archived is True

def test_orphan_handling(finding_engine):
    f = FindingDefinition(
        finding_id="f_orp",
        problem="Test",
        evidence_statement="Test",
        created_at=time.time(),
        updated_at=time.time(),
        linked_business_question_id="bq_1",
        linked_kpi_id="kpi_1",
        linked_rca_analysis_id="rca_1"
    )
    
    assert f.is_orphaned(bq_ids=["bq_1"], kpi_ids=["kpi_1"], rca_ids=["rca_1"]) is False
    assert f.is_orphaned(bq_ids=["bq_2"]) is True
    assert f.is_orphaned(kpi_ids=["kpi_2"]) is True
    assert f.is_orphaned(rca_ids=["rca_2"]) is True

def test_rca_less_finding(finding_engine):
    f = FindingDefinition(
        finding_id="f_no_rca",
        problem="User reported lag",
        evidence_statement="Spikes in APM",
        created_at=time.time(),
        updated_at=time.time(),
        linked_rca_analysis_id=None,
        analyst_interpretation="Could be DB locks",
        interpretation_type="ANALYST_HYPOTHESIS"
    )
    finding_engine.save_finding(f)
    assert finding_engine.get_finding("f_no_rca").linked_rca_analysis_id is None
