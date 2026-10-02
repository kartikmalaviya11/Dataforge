import pytest
import time
from src.kpi_engine import KPIEngine
from src.type_detector import TypeDetectionResult
from src.issue_manager import StandardizedIssue

def test_kpi_generation_performance():
    num_rows = 1000
    type_results = []
    for i in range(26):
        if i < 10: sem_type = "Integer"
        elif i < 15: sem_type = "Category"
        elif i < 20: sem_type = "Date"
        else: sem_type = "ID"
            
        col_name = f"col_{i}"
        if i == 0: col_name = "sales"
        elif i == 1: col_name = "profit"
        elif i == 2: col_name = "quantity"
        elif i == 20: col_name = "order_id"
        
        type_results.append(TypeDetectionResult(
            column_name=col_name,
            storage_type="int64",
            detected_type=sem_type,
            confidence=1.0,
            evidence="none",
            status="OK",
            recommended_action="none"
        ))
        
    issues = [
        StandardizedIssue(
            issue_id=f"ISSUE_{i}",
            source="test",
            issue_type="MISSING",
            rule_or_check_name="test",
            row_index=i,
            column=f"col_{i%26}",
            actual_value=None,
            expected_condition="not null",
            severity="LOW",
            message="Missing value",
            recommendation="none"
        )
        for i in range(100)
    ]
    
    eng = KPIEngine()
    
    t0 = time.time()
    kpis = eng.recommend_kpis(num_rows, type_results, issues)
    t1 = time.time()
    
    elapsed = t1 - t0
    
    assert len(kpis) > 0, "Should generate at least some KPIs"
    assert elapsed < 1.0, f"KPI generation took {elapsed:.4f}s"
    print(f"\n[Performance] KPI generation completed in {elapsed:.4f}s")
