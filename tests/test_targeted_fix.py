import pandas as pd
from src.type_detector import detect_semantic_types, TypeDetectionResult
from src.quality_engine import check_duplicate_ids
from src.profiler import profile_dataset

def test_sales_and_quantity_semantics():
    df = pd.DataFrame({
        'Sales': ['100.50', '200.75', '150.00', 'bad_value', '10-2'],
        'Quantity': [10, 20, 30, 'bad', 50],
        'Profit': [50.5, -10.0, 20.0, 30.5, 40.2],
        'Unit_Price': [10, 20, 30, 40, 50],
        'Discount_Pct': [0.1, 0.2, 0.3, 'bad', 0.5]
    })
    profile = profile_dataset(df)
    results = {r.column_name: r.detected_type for r in detect_semantic_types(df, profile)}
    
    assert results['Sales'] in ('Currency', 'Decimal', 'Integer')
    assert results['Quantity'] in ('Integer', 'Decimal', 'Numeric')
    assert results['Profit'] in ('Currency', 'Decimal', 'Integer')
    assert results['Unit_Price'] in ('Currency', 'Decimal', 'Integer')
    assert results['Discount_Pct'] == 'Percentage'

def test_id_vs_code_semantics():
    df = pd.DataFrame({
        'Customer_ID': ['A1', 'A2', 'A2', 'A3', 'A4'],
        'Order_ID': ['O1', 'O2', 'O2', 'O3', 'O4'],
        'Postal_Code': ['12345', '12345', '54321', '90210', '90210'],
        'Promo_Code': ['SUMMER', 'SUMMER', 'WINTER', 'FALL', 'FALL']
    })
    profile = profile_dataset(df)
    type_results = detect_semantic_types(df, profile)
    results_map = {r.column_name: r.detected_type for r in type_results}
    
    assert results_map['Customer_ID'] == 'ID'
    assert results_map['Order_ID'] == 'ID'
    assert results_map['Postal_Code'] == 'Code'
    assert results_map['Promo_Code'] == 'Code'
    
    # Check uniqueness engine
    issues = check_duplicate_ids(df, type_results)
    
    issue_cols = {iss.column for iss in issues}
    
    assert 'Customer_ID' in issue_cols
    assert 'Order_ID' in issue_cols
    assert 'Postal_Code' not in issue_cols
    assert 'Promo_Code' not in issue_cols
