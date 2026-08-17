import pytest
from src.kpi_engine import KPIEngine, KPIRecommendation
from src.type_detector import TypeDetectionResult
from src.issue_manager import StandardizedIssue

@pytest.fixture
def engine():
    return KPIEngine(review_threshold=0.10)

def create_type_result(col, detected_type):
    return TypeDetectionResult(
        column_name=col,
        storage_type="object",
        detected_type=detected_type,
        confidence=0.9,
        evidence="test",
        status="OK",
        recommended_action="None"
    )

def create_issue(col):
    return StandardizedIssue(
        issue_id="test",
        source="quality",
        issue_type="MISSING_VALUE",
        rule_or_check_name="test",
        row_index=1,
        column=col,
        actual_value=None,
        expected_condition="not null",
        severity="MEDIUM",
        message="test",
        recommendation="test"
    )

def test_empty_dataset(engine):
    recs = engine.recommend_kpis(0, [], [])
    unavailable = [r for r in recs if r.status == "UNAVAILABLE"]
    available = [r for r in recs if r.status == "AVAILABLE"]
    assert len(available) == 0
    assert len(unavailable) > 0
    
def test_sales_only(engine):
    types = [create_type_result("Sales", "Currency")]
    recs = engine.recommend_kpis(100, types, [])
    
    total_sales = next(r for r in recs if r.kpi_name == "Total Sales")
    assert total_sales.status == "AVAILABLE"
    assert total_sales.category == "Aggregation"
    assert total_sales.calculation_logic == "SUM(Sales)"
    
    margin = next(r for r in recs if r.kpi_name == "Profit Margin")
    assert margin.status == "UNAVAILABLE"
    assert "Profit" not in margin.available_columns
    
def test_sales_and_profit_ratio(engine):
    types = [
        create_type_result("Sales", "Currency"),
        create_type_result("Profit", "Currency")
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    margin = next(r for r in recs if r.kpi_name == "Profit Margin")
    assert margin.status == "AVAILABLE"
    assert margin.calculation_logic == "SUM(Profit) / SUM(Sales)"
    
def test_requires_review_due_to_defects(engine):
    types = [create_type_result("Sales", "Currency")]
    issues = [create_issue("Sales") for _ in range(15)]
    
    recs = engine.recommend_kpis(100, types, issues)
    total_sales = next(r for r in recs if r.kpi_name == "Total Sales")
    
    assert total_sales.status == "REQUIRES_REVIEW"
    assert "defect rate of 15.0%" in total_sales.explanation
    
def test_not_a_measure_heuristics(engine):
    types = [
        create_type_result("Customer_ID", "Integer"),
        create_type_result("Age", "Integer"),
        create_type_result("Year", "Integer"),
        create_type_result("Quantity", "Integer"),
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    kpi_names = [r.kpi_name for r in recs]
    assert "Total Quantity" in kpi_names
    assert "Total Age" not in kpi_names
    assert "Total Year" not in kpi_names
    assert "Total Customer_ID" not in kpi_names
    
def test_time_and_dimension_kpis(engine):
    types = [
        create_type_result("Revenue", "Currency"),
        create_type_result("Order_Date", "Date"),
        create_type_result("Region", "Category")
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    time_kpi = next((r for r in recs if r.category == "Time"), None)
    assert time_kpi is not None
    assert time_kpi.status == "AVAILABLE"
    assert time_kpi.calculation_logic == "SUM(Revenue) grouped by Order_Date"
    
    dim_kpi = next((r for r in recs if r.category == "Dimension"), None)
    assert dim_kpi is not None
    assert dim_kpi.status == "AVAILABLE"
    assert dim_kpi.calculation_logic == "SUM(Revenue) grouped by Region"

def test_distinct_customers(engine):
    types = [
        create_type_result("customer_id", "ID")
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    cust_kpi = next((r for r in recs if r.kpi_name == "Distinct Customers"), None)
    assert cust_kpi is not None
    assert cust_kpi.status == "AVAILABLE"
    assert cust_kpi.calculation_logic == "DISTINCTCOUNT(customer_id)"

def test_no_date_no_time_kpi(engine):
    types = [
        create_type_result("Revenue", "Currency")
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    time_kpi = next((r for r in recs if r.category == "Time"), None)
    assert time_kpi is None

def test_duplicate_kpi_prevention(engine):
    # Setup that would previously generate "Total Quantity" twice
    types = [create_type_result("quantity", "Integer")]
    recs = engine.recommend_kpis(100, types, [])
    
    kpi_names = [r.kpi_name for r in recs]
    assert kpi_names.count("Total Quantity") == 1

def test_total_orders_with_valid_order_id(engine):
    types = [create_type_result("transaction_id", "ID")]
    recs = engine.recommend_kpis(100, types, [])
    
    orders = next(r for r in recs if r.kpi_name == "Total Orders")
    assert orders.status == "AVAILABLE"
    assert orders.calculation_logic == "DISTINCTCOUNT(transaction_id)"

def test_total_orders_without_order_id(engine):
    # Only customer ID, no order ID
    types = [create_type_result("customer_id", "ID")]
    recs = engine.recommend_kpis(100, types, [])
    
    orders = next(r for r in recs if r.kpi_name == "Total Orders")
    assert orders.status == "UNAVAILABLE"

def test_aov_with_sales_and_order_id(engine):
    types = [
        create_type_result("order_id", "ID"),
        create_type_result("sales", "Currency")
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    aov = next(r for r in recs if r.kpi_name == "Average Order Value")
    assert aov.status == "AVAILABLE"
    assert aov.calculation_logic == "SUM(sales) / DISTINCTCOUNT(order_id)"

def test_aov_without_sales(engine):
    types = [create_type_result("order_id", "ID")]
    recs = engine.recommend_kpis(100, types, [])
    
    aov = next(r for r in recs if r.kpi_name == "Average Order Value")
    assert aov.status == "UNAVAILABLE"

def test_aov_without_order_id(engine):
    types = [create_type_result("sales", "Currency")]
    recs = engine.recommend_kpis(100, types, [])
    
    aov = next(r for r in recs if r.kpi_name == "Average Order Value")
    assert aov.status == "UNAVAILABLE"

def test_ensuring_quantity_is_not_fallback_for_aov(engine):
    types = [
        create_type_result("customer_id", "ID"),
        create_type_result("quantity", "Integer")
    ]
    recs = engine.recommend_kpis(100, types, [])
    
    aov = next(r for r in recs if r.kpi_name == "Average Order Value")
    assert aov.status == "UNAVAILABLE"
    # Make sure we don't accidentally calculate SUM(quantity)/DISTINCTCOUNT(customer_id)
    assert aov.calculation_logic == "N/A"
