import pytest
from src.kpi_engine import KPIRecommendation
from src.dax_generator import DAXGenerator, DAXMeasure

@pytest.fixture
def generator():
    return DAXGenerator(table_name="Financial Data")

def create_kpi(name, status, logic, cols):
    return KPIRecommendation(
        kpi_name=name,
        category="Test",
        priority="HIGH",
        status=status,
        required_columns=cols,
        available_columns=cols,
        calculation_logic=logic,
        explanation="test",
        missing_requirements=["test_req"] if status == "UNAVAILABLE" else []
    )

def test_available_total(generator):
    kpi = create_kpi("Total Sales", "AVAILABLE", "SUM(Sales)", ["Sales"])
    dax = generator.generate_measure(kpi)
    
    assert dax.status == "AVAILABLE"
    assert dax.dax_expression == "SUM('Financial Data'[Sales])"
    assert len(dax.warnings) == 0

def test_available_average(generator):
    kpi = create_kpi("Average Revenue", "AVAILABLE", "AVERAGE(Revenue)", ["Revenue"])
    dax = generator.generate_measure(kpi)
    
    assert dax.dax_expression == "AVERAGE('Financial Data'[Revenue])"

def test_available_distinct_count(generator):
    kpi = create_kpi("Total Orders", "AVAILABLE", "DISTINCTCOUNT(Order_ID)", ["Order_ID"])
    dax = generator.generate_measure(kpi)
    
    assert dax.dax_expression == "DISTINCTCOUNT('Financial Data'[Order_ID])"

def test_safe_ratio_divide(generator):
    kpi = create_kpi("Profit Margin", "AVAILABLE", "SUM(Profit) / SUM(Sales)", ["Profit", "Sales"])
    dax = generator.generate_measure(kpi)
    
    assert dax.dax_expression == "DIVIDE(SUM('Financial Data'[Profit]), SUM('Financial Data'[Sales]))"

def test_aov_ratio(generator):
    kpi = create_kpi("Average Order Value", "AVAILABLE", "SUM(Sales) / DISTINCTCOUNT(Order_ID)", ["Sales", "Order_ID"])
    dax = generator.generate_measure(kpi)
    
    assert dax.dax_expression == "DIVIDE(SUM('Financial Data'[Sales]), DISTINCTCOUNT('Financial Data'[Order_ID]))"

def test_unavailable_status(generator):
    kpi = create_kpi("Profit Margin", "UNAVAILABLE", "N/A", ["Profit", "Sales"])
    dax = generator.generate_measure(kpi)
    
    assert dax.status == "UNAVAILABLE"
    assert dax.dax_expression == "N/A"
    assert len(dax.warnings) == 1
    assert "Missing requirements: test_req" in dax.warnings[0]

def test_requires_review_status(generator):
    kpi = create_kpi("Total Sales", "REQUIRES_REVIEW", "SUM(Sales)", ["Sales"])
    dax = generator.generate_measure(kpi)
    
    assert dax.status == "REVIEW_REQUIRED"
    assert dax.dax_expression == "SUM('Financial Data'[Sales])" # Keep logic clean
    assert len(dax.warnings) == 1
    assert "WARNING" in dax.warnings[0]

def test_grouped_by_dimension_removed(generator):
    kpi = create_kpi("Sales by Region", "AVAILABLE", "SUM(Sales) grouped by Region", ["Sales", "Region"])
    dax = generator.generate_measure(kpi)
    
    # DAX base measures shouldn't have GROUP BY inside them; grouping is handled in visuals
    assert dax.dax_expression == "SUM('Financial Data'[Sales])"

def test_no_hallucinated_columns():
    gen = DAXGenerator(table_name="TestTable")
    # If the logic in Phase 10 returned bracketed pseudo code
    kpi = create_kpi("Test", "AVAILABLE", "SUM([My Column])", ["My Column"])
    dax = gen.generate_measure(kpi)
    
    assert dax.dax_expression == "SUM('TestTable'[My Column])"

def test_empty_kpi_input(generator):
    measures = generator.generate_measures([])
    assert len(measures) == 0
