import os
import json
import pytest
import time
from unittest.mock import MagicMock
from src.business_questions import BusinessQuestion, QuestionManager, InvalidStatusError, InvalidTransitionError
from src.sql_engine import DuckDBEngine, SecurityError
from src.workspace import ProjectWorkspace
from src.kpi_engine import KPIManager, KPIDefinition

@pytest.fixture
def workspace(tmp_path):
    ws = ProjectWorkspace(str(tmp_path))
    return ws

@pytest.fixture
def q_manager(workspace):
    return QuestionManager(workspace)

def test_create_question_default_pending(q_manager):
    q = q_manager.create_question("What is our churn rate?")
    assert q.status == "Pending"
    assert q.question == "What is our churn rate?"
    assert len(q.status_history) == 1
    assert q.status_history[0]["new_status"] == "Pending"

def test_empty_question_rejection(q_manager):
    with pytest.raises(ValueError):
        q_manager.create_question("   ")
    with pytest.raises(ValueError):
        q_manager.create_question("")
    with pytest.raises(ValueError):
        q_manager.create_question(None)
        
def test_forward_transitions(q_manager):
    q = q_manager.create_question("Why did sales drop?")
    
    q_manager.transition_status(q.question_id, "Investigating", "Started looking into it")
    q = q_manager.get_question(q.question_id)
    assert q.status == "Investigating"
    assert len(q.status_history) == 2
    assert q.status_history[1]["reason"] == "Started looking into it"
    assert q.status_history[1]["new_status"] == "Investigating"
    assert q.status_history[1]["previous_status"] == "Pending"

    q_manager.transition_status(q.question_id, "Completed", "Found the issue")
    q = q_manager.get_question(q.question_id)
    assert q.status == "Completed"
    assert len(q.status_history) == 3
    assert q.status_history[2]["new_status"] == "Completed"

def test_backward_transition(q_manager):
    q = q_manager.create_question("Q1")
    q_manager.transition_status(q.question_id, "Investigating")
    q_manager.transition_status(q.question_id, "Completed")
    
    # Explicit backward transition
    q_manager.transition_status(q.question_id, "Investigating", "New data arrived")
    q = q_manager.get_question(q.question_id)
    assert q.status == "Investigating"
    assert q.status_history[-1]["previous_status"] == "Completed"
    assert q.status_history[-1]["reason"] == "New data arrived"

def test_invalid_status_rejection(q_manager):
    q = q_manager.create_question("Test")
    with pytest.raises(InvalidStatusError):
        q_manager.transition_status(q.question_id, "UnknownStatus")

def test_duplicate_same_status_rejection(q_manager):
    q = q_manager.create_question("Test")
    with pytest.raises(InvalidTransitionError):
        q_manager.transition_status(q.question_id, "Pending")

def test_question_update(q_manager):
    q = q_manager.create_question("Test")
    q_manager.update_question(q.question_id, description="Details", sql_query="SELECT *", pandas_analysis="groupby")
    q = q_manager.get_question(q.question_id)
    assert q.description == "Details"
    assert q.sql_query == "SELECT *"
    assert q.pandas_analysis == "groupby"
    assert q.status == "Pending" # Unchanged by fields

def test_sql_attachment_and_safety(q_manager, workspace):
    engine = DuckDBEngine(workspace)
    q = q_manager.create_question("Test")
    q_manager.update_question(q.question_id, sql_query="DROP TABLE users;")
    q = q_manager.get_question(q.question_id)
    
    with pytest.raises(SecurityError):
        engine.execute_query(q.sql_query)

def test_kpi_reference_and_orphan(q_manager, workspace):
    kpi_mgr = KPIManager(workspace)
    kpi = KPIDefinition(
        kpi_id="kpi-123",
        kpi_name="Churn",
        business_definition="Churn rate",
        formula="A/B",
        metric_definitions=[],
        source_tables=[],
        source_columns=[],
        unit="percentage",
        description="Desc",
        version=1,
        created_at=time.time(),
        updated_at=time.time()
    )
    kpi_mgr.save_kpi(kpi)
    
    q = q_manager.create_question("Test")
    q_manager.update_question(q.question_id, related_kpi_id="kpi-123")
    
    # Assert linkage is stable
    linked_kpi = q_manager.get_linked_kpi(q.question_id, kpi_mgr)
    assert linked_kpi is not None
    assert linked_kpi.kpi_name == "Churn"
    
    # Rename KPI (Simulate rename by rewriting the JSON manually since KPIManager relies on names)
    kpis = kpi_mgr.load_kpis()
    for k in kpis:
        if k.kpi_id == "kpi-123":
            k.kpi_name = "New Churn"
    with open(kpi_mgr.file_path, "w", encoding="utf-8") as f:
        json.dump([k.to_dict() for k in kpis], f, indent=2)
    
    linked_kpi = q_manager.get_linked_kpi(q.question_id, kpi_mgr)
    assert linked_kpi.kpi_name == "New Churn" # Survives rename
    
    # Delete KPI explicitly (simulate by removing from json)
    os.remove(kpi_mgr.file_path)
    
    # Check orphaned by delete
    q = q_manager.get_question(q.question_id)
    assert q.related_kpi_id == "kpi-123" # Link remains in question
    linked_kpi = q_manager.get_linked_kpi(q.question_id, kpi_mgr)
    assert linked_kpi is None # Orphaned
    
    # Check orphaned by archive
    kpi.is_active = False
    kpi_mgr.save_kpi(kpi)
    linked_kpi_archived = q_manager.get_linked_kpi(q.question_id, kpi_mgr)
    assert linked_kpi_archived is None # Orphaned due to inactivity

def test_archive_behavior(q_manager):
    q = q_manager.create_question("Test")
    q_manager.archive_question(q.question_id)
    
    q = q_manager.get_question(q.question_id)
    assert q.is_archived is True
    
    active = q_manager.get_active_questions()
    assert len(active) == 0
    
    archived = q_manager.get_archived_questions()
    assert len(archived) == 1
    
    q_manager.unarchive_question(q.question_id)
    assert q_manager.get_question(q.question_id).is_archived is False

def test_persistence_and_reload(workspace):
    qm = QuestionManager(workspace)
    q1 = qm.create_question("Q1")
    time.sleep(0.01)
    q2 = qm.create_question("Q2")
    
    qm.transition_status(q1.question_id, "Investigating", "started")
    qm.update_question(q1.question_id, result="Found an issue", finding="Needs fixing", related_kpi_id="kpi-99")
    qm.archive_question(q2.question_id)
    
    # Reload from disk
    qm2 = QuestionManager(workspace)
    active = qm2.get_active_questions()
    assert len(active) == 1
    assert active[0].question == "Q1"
    assert active[0].status == "Investigating"
    assert active[0].status_history[-1]["reason"] == "started"
    assert active[0].result == "Found an issue"
    assert active[0].finding == "Needs fixing"
    assert active[0].related_kpi_id == "kpi-99"
    
    archived = qm2.get_archived_questions()
    assert len(archived) == 1
    assert archived[0].question == "Q2"
    assert archived[0].is_archived is True

def test_duplicate_question_behavior(q_manager):
    # Questions with identical text are allowed and get unique IDs
    q1 = q_manager.create_question("What is our churn?")
    q2 = q_manager.create_question("What is our churn?")
    
    assert q1.question == q2.question
    assert q1.question_id != q2.question_id
    
    all_q = q_manager.get_active_questions()
    assert len(all_q) == 2

def test_deterministic_ordering(workspace):
    qm = QuestionManager(workspace)
    qm.create_question("A")
    time.sleep(0.01)
    qm.create_question("B")
    
    q_list = qm.get_active_questions()
    assert q_list[0].question == "B" # Decided on descending usually? We'll assert created_at ascending.
    # Wait, usually deterministic is created_at descending (newest first). Let's test ascending or descending.
    # We will implement descending (newest at top).
    
def test_no_raw_data_mutation(workspace):
    qm = QuestionManager(workspace)
    qm.create_question("Mutate test")
    assert not any(f.endswith('.csv') for f in os.listdir(workspace.project_root)) # Just ensuring it didn't write csvs
