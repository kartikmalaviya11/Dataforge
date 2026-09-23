import pytest
import os
from src.query_manager import QueryManager, SavedQuery

def test_query_manager_save_and_load(tmp_path):
    qm = QueryManager(tmp_path)
    
    # Save a query
    qm.save_query("My Query", "SELECT * FROM data")
    
    # Load queries
    queries = qm.get_saved_queries()
    assert len(queries) == 1
    assert queries[0].name == "My Query"
    assert queries[0].sql == "SELECT * FROM data"
    
    # Log history
    qm.log_history("SELECT * FROM data", status="SUCCESS", duration_ms=150, rows=500)
    history = qm.get_history()
    assert len(history) == 1
    assert history[0].status == "SUCCESS"
    assert history[0].rows_returned == 500

def test_query_persistence_across_instances(tmp_path):
    qm1 = QueryManager(tmp_path)
    qm1.save_query("Q1", "SELECT 1")
    
    qm2 = QueryManager(tmp_path)
    queries = qm2.get_saved_queries()
    assert len(queries) == 1
    assert queries[0].name == "Q1"
