import pytest
import pandas as pd
import numpy as np

from src.sql_analyzer import SQLAnalyzer, _safe_quote
from src.kpi_engine import KPIRecommendation

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "ID": [1, 2, 2, None, 5, 5, 5],
        "Sales": [100.50, 200.0, None, 50.0, 300.0, 300.0, -10.0],
        "Name": ["A", "B", "  ", "", "C", "C", "D"],
        "Complex Name!": [1, 2, 3, 4, 5, 6, 7]
    })

@pytest.fixture
def analyzer(sample_df):
    analyzer = SQLAnalyzer(sample_df)
    yield analyzer
    analyzer.close()

def test_safe_quote():
    assert _safe_quote("Normal") == '"Normal"'
    assert _safe_quote("Space Name") == '"Space Name"'
    assert _safe_quote("Double\"Quote") == '"Double""Quote"'

def test_compare_missing_values(analyzer):
    # In 'Sales', there is 1 missing value. Python count = 1.
    res = analyzer.check_missing_values("Sales", 1)
    assert res.match_status == "MATCH"
    assert res.sql_result == 1
    assert res.difference == 0
    
def test_compare_blank_values(analyzer):
    # In 'Name', there is 1 completely empty string "", and 1 whitespace string "  "
    # Phase 4 strips strings, so both count as blank. Python count = 2.
    res = analyzer.check_blank_values("Name", 2)
    assert res.match_status == "MATCH"
    assert res.sql_result == 2

def test_compare_duplicate_rows(analyzer):
    # Rows 4 and 5 (0-indexed) are identical: ID=5, Sales=300.0, Name='C', Complex Name!=5?
    # Wait, Complex Name! has 5 and 6. So they aren't identical.
    # Let's create an explicit dataframe with exact duplicates for this test.
    df = pd.DataFrame({
        "A": [1, 1, 1, 2],
        "B": ["X", "X", "X", "Y"]
    })
    # Phase 4 keeps first, flags 2 copies.
    an = SQLAnalyzer(df)
    res = an.check_duplicate_rows(2)
    assert res.match_status == "MATCH"
    assert res.sql_result == 2
    an.close()

def test_compare_duplicate_ids(analyzer):
    # In 'ID': 1, 2, 2, None, 5, 5, 5
    # Phase 4 keep=False ignores nulls. Flags all rows with shared IDs.
    # 2 is shared (2 rows). 5 is shared (3 rows). Total = 5.
    res = analyzer.check_duplicate_ids("ID", 5)
    assert res.match_status == "MATCH"
    assert res.sql_result == 5

def test_compare_range(analyzer):
    # Sales < 0 or > 250.
    # Sales = -10.0 (1), 300.0 (2). Total = 3 out of range.
    res = analyzer.check_range("Sales", 0.0, 250.0, 3)
    assert res.match_status == "MATCH"
    assert res.sql_result == 3

def test_forced_mismatch(analyzer):
    # Deliberately supply a wrong python count (99) to ensure it flags MISMATCH
    res = analyzer.check_missing_values("Sales", 99)
    assert res.match_status == "MISMATCH"
    assert res.sql_result == 1
    assert res.difference == 98
    
def test_kpi_total_and_average(analyzer):
    # Total Sales = 100.5 + 200 + 50 + 300 + 300 - 10 = 940.5
    # Python result would be 940.5
    kpi_tot = KPIRecommendation("Total Sales", "Aggregation", "HIGH", "AVAILABLE", ["Sales"], ["Sales"], "SUM(Sales)", "")
    res = analyzer.aggregate_kpi(kpi_tot, 940.5)
    assert res.match_status == "MATCH"
    assert res.sql_result == 940.5

    # Average Sales = 940.5 / 6 = 156.75
    kpi_avg = KPIRecommendation("Avg Sales", "Aggregation", "HIGH", "AVAILABLE", ["Sales"], ["Sales"], "AVERAGE(Sales)", "")
    res2 = analyzer.aggregate_kpi(kpi_avg, 156.75)
    assert res2.match_status == "MATCH"
    assert res2.sql_result == 156.75

def test_kpi_ratio_safe_divide():
    df = pd.DataFrame({"Profit": [10, 20], "Sales": [0, 0]})
    an = SQLAnalyzer(df)
    
    # Python calculates Ratio as np.inf or NaN or explicitly handles div-by-zero.
    # If Python gracefully returns None, SQL should return None via NULLIF.
    kpi_ratio = KPIRecommendation("Margin", "Ratio", "HIGH", "AVAILABLE", ["Profit", "Sales"], ["Profit", "Sales"], "SUM(Profit) / SUM(Sales)", "")
    res = an.aggregate_kpi(kpi_ratio, None)
    
    assert res.match_status == "NOT_AVAILABLE"
    assert res.sql_result is None
    an.close()

def test_kpi_distinct_count(analyzer):
    kpi = KPIRecommendation("Total Customers", "Transaction", "HIGH", "AVAILABLE", ["ID"], ["ID"], "DISTINCTCOUNT(ID)", "")
    # Distinct IDs (ignoring null via SQL default, pandas nunique() also ignores null by default)
    # IDs: 1, 2, 5 (3 distinct)
    res = analyzer.aggregate_kpi(kpi, 3)
    assert res.match_status == "MATCH"
    assert res.sql_result == 3

def test_kpi_unavailable(analyzer):
    kpi = KPIRecommendation("Total Missing", "Aggregation", "HIGH", "UNAVAILABLE", ["Missing"], [], "N/A", "")
    res = analyzer.aggregate_kpi(kpi, None)
    # Unavailable KPI yields NULL SQL query and matches None Python output
    assert res.match_status == "NOT_AVAILABLE"
    assert res.sql_result == "NOT_AVAILABLE"

def test_integration_pipeline():
    # A true integration test importing phases 4 and 10 logic over a dataframe
    from src.profiler import profile_dataset
    from src.type_detector import detect_semantic_types
    from src.quality_engine import run_quality_checks
    from src.kpi_engine import KPIEngine
    
    df = pd.DataFrame({
        "Order_ID": [1, 2, 3, 3, 4],
        "Revenue": [100.0, 150.0, -10.0, None, 200.0]
    })
    
    prof = profile_dataset(df)
    types = detect_semantic_types(df, prof)
    # Run generic quality checks, explicitly marking Order_ID as an ID column
    issues = run_quality_checks(df, prof, types, id_columns=["Order_ID"])
    
    # 1 duplicate ID (Order_ID=3) -> flagged twice
    dup_id_count = sum(1 for i in issues if i.issue_type == "DUPLICATE_ID")
    # 1 missing value (Revenue)
    missing_rev_count = sum(1 for i in issues if i.issue_type == "MISSING_VALUE" and i.column == "Revenue")
    
    analyzer = SQLAnalyzer(df)
    res_dup = analyzer.check_duplicate_ids("Order_ID", dup_id_count)
    assert res_dup.match_status == "MATCH", f"Expected {dup_id_count}, got {res_dup.sql_result}"
    
    res_missing = analyzer.check_missing_values("Revenue", missing_rev_count)
    assert res_missing.match_status == "MATCH"
    
    # Now KPIs
    kpi_engine = KPIEngine()
    # We need to map issues to StandardizedIssue for KPIEngine
    from src.issue_manager import IssueManager
    std_issues = IssueManager().consolidate(issues)
    kpis = kpi_engine.recommend_kpis(len(df), types, std_issues)
    
    tot_rev_kpi = next(k for k in kpis if k.kpi_name == "Total Sales")
    # Calculate python equivalent: sum skipping NA = 100+150-10+200 = 440
    res_kpi = analyzer.aggregate_kpi(tot_rev_kpi, 440.0)
    assert res_kpi.match_status == "MATCH"
    assert res_kpi.sql_result == 440.0
    
    analyzer.close()
