import pytest
import pandas as pd
import duckdb
import uuid
import os
import time
from pathlib import Path

from src.workspace import ProjectWorkspace, TableRegistryEntry
from src.sql_engine import DuckDBEngine
from src.feature_engineering import (
    FeatureDefinition, FeatureEngine, FeatureBuilder, FeatureGenerationError, DuplicateFeatureError
)

@pytest.fixture
def workspace_with_data(tmp_path):
    # Setup test workspace with simple CSVs
    ws = ProjectWorkspace(tmp_path)
    
    # Orders
    orders_csv = tmp_path / "orders.csv"
    orders_csv.write_text("order_id,price,freight,status,purchase_date,delivery_date\n"
                          "O1,100,10,delivered,2023-01-01,2023-01-05\n"
                          "O2,200,20,shipped,2023-12-30,2024-01-02\n"
                          "O3,50,0,canceled,2023-05-15,2023-05-10\n"
                          "O4,0,5,delivered,2023-10-10,\n")
    
    ws.registry["orders"] = TableRegistryEntry(
        table_name="orders", file_name="orders.csv", file_path=str(orders_csv), file_type="csv", row_count=4, column_count=6, status="LOADED", last_modified=10000.0
    )
    
    return ws

def test_feature_date_difference(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    feat_def = FeatureBuilder.build_date_difference(
        feature_name="delivery_days",
        source_table="orders",
        start_col="purchase_date",
        end_col="delivery_date",
        unit="day"
    )
    
    fe_engine.create_feature(feat_def)
    
    # Query to verify
    df = sql_engine.execute_query('SELECT order_id, delivery_days FROM "orders" ORDER BY order_id')
    assert df.loc[0, "delivery_days"] == 4
    assert df.loc[1, "delivery_days"] == 3
    assert df.loc[2, "delivery_days"] == -5 # Negative difference
    assert pd.isna(df.loc[3, "delivery_days"]) # Null propagation

def test_feature_date_parts(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # Test YEAR
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_year", "orders", "purchase_date", "year"))
    # Test MONTH
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_month", "orders", "purchase_date", "month"))
    # Test QUARTER
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_quarter", "orders", "purchase_date", "quarter"))
    # Test WEEK (ISO-8601 explicitly)
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_week", "orders", "purchase_date", "week"))
    
    df = sql_engine.execute_query('SELECT * FROM "orders" ORDER BY order_id')
    
    # O1: 2023-01-01 is a Sunday. ISO week is 52 (of 2022).
    assert df.loc[0, "purchase_year"] == 2023
    assert df.loc[0, "purchase_month"] == 1
    assert df.loc[0, "purchase_quarter"] == 1
    # Note: DuckDB's EXTRACT('week' FROM ...) or date_part('week', ...) uses ISO-8601 week rules.
    # 2023-01-01 was a Sunday, so it belongs to the last week of 2022 (week 52).
    assert df.loc[0, "purchase_week"] == 52

def test_feature_boolean_flag(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    feat_def = FeatureBuilder.build_boolean_flag(
        feature_name="is_expensive",
        source_table="orders",
        col="price",
        operator=">",
        value="100"
    )
    fe_engine.create_feature(feat_def)
    
    df = sql_engine.execute_query('SELECT order_id, is_expensive FROM "orders" ORDER BY order_id')
    assert df.loc[0, "is_expensive"] == False # 100 > 100 is False
    assert df.loc[1, "is_expensive"] == True  # 200 > 100 is True

def test_feature_conditional_column(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # Status categorizer
    conditions = [
        {"col": "status", "op": "==", "val": "'delivered'", "result": "'done'"},
        {"col": "status", "op": "==", "val": "'canceled'", "result": "'aborted'"}
    ]
    feat_def = FeatureBuilder.build_conditional_column(
        feature_name="status_group",
        source_table="orders",
        conditions=conditions,
        default_val="'in_progress'"
    )
    fe_engine.create_feature(feat_def)
    
    df = sql_engine.execute_query('SELECT order_id, status_group FROM "orders" ORDER BY order_id')
    assert df.loc[0, "status_group"] == 'done'
    assert df.loc[1, "status_group"] == 'in_progress'
    assert df.loc[2, "status_group"] == 'aborted'

def test_feature_arithmetic(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # Addition
    fe_engine.create_feature(FeatureBuilder.build_arithmetic(
        "total_value", "orders", col1="price", op="+", col2="freight"
    ))
    
    # Division (Check divide by zero safely)
    fe_engine.create_feature(FeatureBuilder.build_arithmetic(
        "freight_ratio", "orders", col1="freight", op="/", col2="price"
    ))
    
    df = sql_engine.execute_query('SELECT order_id, total_value, freight_ratio FROM "orders" ORDER BY order_id')
    
    assert df.loc[0, "total_value"] == 110
    assert df.loc[0, "freight_ratio"] == 0.1 # 10 / 100
    assert pd.isna(df.loc[3, "freight_ratio"]) # 5 / 0 -> NULL

def test_feature_arithmetic_with_spaces_and_digits(tmp_path):
    # Regression test for column names with spaces and digits (e.g. 'Unit Price', 'sales_2024')
    ws = ProjectWorkspace(tmp_path)
    csv_path = tmp_path / "pricing.csv"
    csv_path.write_text("id,Unit Price,sales_2024\n1,50.0,2\n2,25.0,4\n")
    ws.registry["pricing"] = TableRegistryEntry(
        table_name="pricing", file_name="pricing.csv", file_path=str(csv_path), file_type="csv",
        row_count=2, column_count=3, status="LOADED", last_modified=1000.0
    )

    sql_engine = DuckDBEngine(ws)
    fe_engine = FeatureEngine(sql_engine, ws)

    # Arithmetic between columns with spaces and digits
    feat = FeatureBuilder.build_arithmetic("total_revenue", "pricing", "Unit Price", "*", "sales_2024")
    assert feat.source_columns == ["Unit Price", "sales_2024"]
    assert '"Unit Price"' in feat.expression
    assert '"sales_2024"' in feat.expression

    fe_engine.create_feature(feat)

    # Arithmetic with literal number
    feat_lit = FeatureBuilder.build_arithmetic("discounted_price", "pricing", "Unit Price", "*", "0.9")
    assert feat_lit.source_columns == ["Unit Price"]
    assert '"Unit Price"' in feat_lit.expression
    assert '0.9' in feat_lit.expression

    fe_engine.create_feature(feat_lit)

    res = sql_engine.execute_query('SELECT total_revenue, discounted_price FROM "pricing" ORDER BY id')
    assert list(res["total_revenue"]) == [100.0, 100.0]
    assert list(res["discounted_price"]) == [45.0, 22.5]
    sql_engine.close()

def test_feature_bucket_category(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # Bucket price: < 100 -> low, 100-200 -> medium, > 200 -> high
    # closed/open intervals tested
    buckets = [
        {"min": None, "max": "100", "label": "'low'"},
        {"min": "100", "max": "200", "label": "'medium'"},
        {"min": "200", "max": None, "label": "'high'"}
    ]
    feat_def = FeatureBuilder.build_bucket_category(
        feature_name="price_bucket",
        source_table="orders",
        col="price",
        buckets=buckets,
        default_label="'unknown'"
    )
    fe_engine.create_feature(feat_def)
    
    df = sql_engine.execute_query('SELECT order_id, price, price_bucket FROM "orders" ORDER BY order_id')
    # O1: 100 -> medium
    assert df.loc[0, "price_bucket"] == 'medium'
    # O2: 200 -> high
    assert df.loc[1, "price_bucket"] == 'high'
    # O3: 50 -> low
    assert df.loc[2, "price_bucket"] == 'low'

def test_feature_duplicate_name(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # Conflicting with base column
    with pytest.raises(DuplicateFeatureError):
        fe_engine.create_feature(FeatureBuilder.build_date_part("price", "orders", "purchase_date", "year"))
        
    # Conflicting with existing feature
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_year", "orders", "purchase_date", "year"))
    with pytest.raises(DuplicateFeatureError):
        fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_year", "orders", "purchase_date", "month"))

def test_feature_builder_safety(workspace_with_data):
    # Reject malicious inputs in operators or values
    with pytest.raises(ValueError):
        FeatureBuilder.build_boolean_flag("test", "orders", "price", operator="DROP TABLE", value="10")
        
    with pytest.raises(ValueError):
        FeatureBuilder.build_date_part("test", "orders", "purchase_date", unit="century; DROP TABLE orders")
        
    with pytest.raises(ValueError):
        FeatureBuilder.build_arithmetic("test", "orders", "price", op="*", col2="freight; DROP TABLE orders")

def test_feature_persistence(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_year", "orders", "purchase_date", "year"))
    
    # Simulate restart
    sql_engine.close()
    
    new_sql_engine = DuckDBEngine(workspace_with_data)
    new_fe_engine = FeatureEngine(new_sql_engine, workspace_with_data)
    
    # The new instance should have automatically loaded and applied features from disk
    assert len(new_fe_engine.get_features("orders")) == 1
    df = new_sql_engine.execute_query('SELECT purchase_year FROM "orders"')
    assert "purchase_year" in df.columns

def test_feature_chaining_rejection(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    fe_engine.create_feature(FeatureBuilder.build_date_part("purchase_year", "orders", "purchase_date", "year"))
    
    # Cannot use purchase_year to build another feature
    with pytest.raises(ValueError, match="chaining"):
        fe_engine.create_feature(FeatureBuilder.build_arithmetic(
            "future_year", "orders", col1="purchase_year", op="+", col2="1"
        ))

def test_1m_row_large_data(tmp_path):
    ws = ProjectWorkspace(tmp_path)
    
    csv_path = tmp_path / "large.csv"
    import csv
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "val1", "val2"])
        for i in range(1000000):
            writer.writerow([i, i*10, i*20])
            
    import hashlib
    def get_hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        
    orig_hash = get_hash(csv_path)
            
    ws.registry["large"] = TableRegistryEntry(
        table_name="large", file_name="large.csv", file_path=str(csv_path), file_type="csv", row_count=1000000, column_count=3, status="LOADED", last_modified=10000.0
    )
    
    sql_engine = DuckDBEngine(ws)
    fe_engine = FeatureEngine(sql_engine, ws)
    
    t0 = time.time()
    fe_engine.create_feature(FeatureBuilder.build_arithmetic(
        "val_sum", "large", "val1", "+", "val2"
    ))
    t1 = time.time()
    
    df = sql_engine.execute_query('SELECT * FROM "large"')
    
    # Result bounded preview checking
    assert len(df) == sql_engine.preview_limit
    assert df.loc[0, "val_sum"] == 0
    assert df.loc[1, "val_sum"] == 30 # 10 + 20
    
    # Force full evaluation on all 1M rows
    t2 = time.time()
    result = sql_engine.conn.execute('SELECT SUM(val_sum) FROM "large"').fetchone()[0]
    t3 = time.time()
    
    # Mathematical verification: sum of i*30 from i=0 to 999999
    # Formula: 30 * (n * (n - 1)) // 2 where n=1000000
    expected_sum = 30 * (1000000 * 999999) // 2
    assert int(result) == expected_sum
    
    # Hash immutability
    assert get_hash(csv_path) == orig_hash
    
    # Explicitly check speed is tracked but no strict time limit is enforced in assertion
    print(f"\n[Performance] View Creation took: {t1 - t0:.4f}s")
    print(f"[Performance] Full 1M Row Evaluation took: {t3 - t2:.4f}s")
    
    sql_engine.close()

def test_bucket_overlap_validation():
    # Should raise ValueError
    with pytest.raises(ValueError, match="Overlapping buckets detected"):
        FeatureBuilder.build_bucket_category(
            "bucket_test", "orders", "price", 
            [{"min": "0", "max": "100", "label": "'low'"}, {"min": "50", "max": "150", "label": "'medium'"}], 
            "'unknown'"
        )

def test_invalid_datatype_rejection(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # Try arithmetic on string column
    feat_def = FeatureBuilder.build_arithmetic(
        "invalid_arith", "orders", "status", "+", "price"
    )
    with pytest.raises(FeatureGenerationError, match="must be a numeric type"):
        fe_engine.create_feature(feat_def)
        
    # Try date diff on non-date column
    feat_def2 = FeatureBuilder.build_date_difference(
        "invalid_date", "orders", "status", "purchase_date", "day"
    )
    with pytest.raises(FeatureGenerationError, match="must be a DATE/TIMESTAMP type"):
        fe_engine.create_feature(feat_def2)

def test_cancel_workflow(workspace_with_data):
    sql_engine = DuckDBEngine(workspace_with_data)
    fe_engine = FeatureEngine(sql_engine, workspace_with_data)
    
    # User configures a feature and hits preview
    feat_def = FeatureBuilder.build_date_part("preview_feat", "orders", "purchase_date", "year")
    
    # We preview by running SELECT query locally without creating
    preview_df = sql_engine.execute_query(f'SELECT {feat_def.expression} AS "{feat_def.feature_name}" FROM "orders_raw" LIMIT 5')
    assert len(preview_df) > 0
    
    # User clicks Cancel/Reject, so fe_engine.create_feature is NEVER called
    # Prove the definition is not persisted
    assert len(fe_engine.get_features("orders")) == 0
    
    # Prove the view is unmodified (no feature column exists)
    df = sql_engine.execute_query('SELECT * FROM "orders"')
    assert "preview_feat" not in df.columns
