"""Tests for Phase 3: Semantic Data-Type Detection"""

import pytest
import pandas as pd
import numpy as np
from src.type_detector import (
    detect_semantic_types,
    TypeDetectionResult,
    is_integer_semantic,
    is_boolean_semantic,
    is_date_semantic,
    is_datetime_semantic,
    is_email_semantic,
    is_phone_semantic,
    is_url_semantic,
    is_currency_semantic,
    is_percentage_semantic,
    is_id_semantic,
    is_category_semantic,
    determine_status_and_action,
)


class TestIndividualDetectors:
    def test_is_integer_semantic(self):
        s = pd.Series([1, 2, 3, 4, 5])
        assert is_integer_semantic(s) is True
    
    def test_is_integer_semantic_false_for_decimals(self):
        s = pd.Series([1.5, 2.5, 3.0])
        assert is_integer_semantic(s) is False
    
    def test_is_integer_semantic_false_for_strings(self):
        s = pd.Series(["a", "b", "c"])
        assert is_integer_semantic(s) is False
    
    def test_is_boolean_semantic_true_false(self):
        s = pd.Series(["true", "false", "true"])
        assert is_boolean_semantic(s) is True
    
    def test_is_boolean_semantic_yes_no(self):
        s = pd.Series(["yes", "no", "yes"])
        assert is_boolean_semantic(s) is True
    
    def test_is_boolean_semantic_1_0(self):
        s = pd.Series([1, 0, 1, 0])
        assert is_boolean_semantic(s) is True
    
    def test_is_boolean_semantic_false(self):
        s = pd.Series(["a", "b", "c"])
        assert is_boolean_semantic(s) is False
    
    def test_is_date_semantic(self):
        s = pd.Series(pd.to_datetime(["2024-01-01", "2024-06-15", "2024-12-31"]))
        assert is_date_semantic(s) is True
    
    def test_is_date_semantic_false_for_datetime(self):
        s = pd.Series(pd.to_datetime(["2024-01-01 12:00", "2024-06-15 15:30"]))
        assert is_date_semantic(s) is False
    
    def test_is_datetime_semantic(self):
        s = pd.Series(pd.to_datetime(["2024-01-01 12:00", "2024-06-15 15:30"]))
        assert is_datetime_semantic(s) is True
    
    def test_is_email_semantic(self):
        s = pd.Series(["alice@example.com", "bob@test.org", "charlie@domain.net"])
        assert is_email_semantic(s) is True
    
    def test_is_email_semantic_partial(self):
        s = pd.Series(["alice@example.com", "bob@test.org", "not-an-email"])
        # 2/3 = 66% < 80% threshold
        assert is_email_semantic(s) is False
    
    def test_is_phone_semantic(self):
        s = pd.Series(["555-123-4567", "(555) 123-4567", "555.123.4567"])
        assert is_phone_semantic(s) is True
    
    def test_is_url_semantic(self):
        s = pd.Series(["https://example.com", "http://test.org", "https://domain.net/path"])
        assert is_url_semantic(s) is True
    
    def test_is_currency_semantic(self):
        s = pd.Series(["$100.00", "$2,500.50", "€99.99", "£1000.00"])
        assert is_currency_semantic(s) is True
    
    def test_is_currency_semantic_numeric(self):
        s = pd.Series([100.00, 2500.50, 99.99, 1000.00])
        assert is_currency_semantic(s) is True
    
    def test_is_percentage_semantic_with_symbol(self):
        s = pd.Series(["10%", "50%", "100%", "25.5%"])
        assert is_percentage_semantic(s) is True
    
    def test_is_percentage_semantic_numeric(self):
        s = pd.Series([10, 50, 100, 25.5])
        assert is_percentage_semantic(s) is True
    
    def test_is_percentage_semantic_out_of_range(self):
        s = pd.Series([150, 200, -10])
        assert is_percentage_semantic(s) is False
    
    def test_is_id_semantic_by_name(self):
        s = pd.Series(["ID001", "ID002", "ID003", "ID004"])
        assert is_id_semantic(s, "customer_id") is True
        assert is_id_semantic(s, "user_key") is True
        assert is_id_semantic(s, "order_number") is True
    
    def test_is_id_semantic_high_cardinality(self):
        s = pd.Series([f"ID{i:06d}" for i in range(1000)])
        assert is_id_semantic(s, "code") is True
    
    def test_is_id_semantic_false_low_cardinality(self):
        s = pd.Series(["A", "B", "C", "A", "B"])
        assert is_id_semantic(s, "id") is False
    
    def test_is_category_semantic_low_cardinality(self):
        s = pd.Series(["A", "B", "C", "A", "B", "C", "A"])
        assert is_category_semantic(s) is True
    
    def test_is_category_semantic_high_cardinality(self):
        s = pd.Series([f"Category_{i}" for i in range(100)])
        assert is_category_semantic(s) is False


class TestStatusDetermination:
    def test_ok_compatible_types(self):
        status, action = determine_status_and_action("int64", "Integer", 0.95)
        assert status == "OK"
        assert "No action" in action
    
    def test_mismatch_incompatible_types(self):
        status, action = determine_status_and_action("object", "Date", 0.95)
        assert status == "MISMATCH"
        assert "Convert" in action
    
    def test_ambiguous_low_confidence(self):
        status, action = determine_status_and_action("object", "Category", 0.5)
        assert status == "AMBIGUOUS"
        assert "Manual review" in action


class TestFullDetection:
    def test_detect_integer_column(self):
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5]})
        from src.profiler import profile_dataset
        profiles = profile_dataset(df)
        results = detect_semantic_types(df, profiles)
        
        assert len(results) == 1
        r = results[0]
        assert r.column_name == "id"
        assert r.detected_type in ("Integer", "ID")
        assert r.confidence > 0.7
    
    def test_detect_date_column(self):
        df = pd.DataFrame({"order_date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])})
        from src.profiler import profile_dataset
        profiles = profile_dataset(df)
        results = detect_semantic_types(df, profiles)
        
        r = results[0]
        assert r.detected_type == "Date"
        assert r.status == "OK"  # datetime storage compatible with Date
    
    def test_detect_email_column(self):
        df = pd.DataFrame({"email": ["a@b.com", "c@d.org", "e@f.net"]})
        from src.profiler import profile_dataset
        profiles = profile_dataset(df)
        results = detect_semantic_types(df, profiles)
        
        r = results[0]
        assert r.detected_type == "Email"
        assert r.status == "MISMATCH"  # object storage -> Email semantic
        assert "Convert" in r.recommended_action
    
    def test_detect_category_column(self):
        df = pd.DataFrame({"status": ["active", "inactive", "active", "pending", "active"]})
        from src.profiler import profile_dataset
        profiles = profile_dataset(df)
        results = detect_semantic_types(df, profiles)
        
        r = results[0]
        assert r.detected_type == "Category"
    
    def test_detect_mixed_dataframe(self):
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "email": ["a@b.com", "b@c.com", "c@d.com", "d@e.com", "e@f.com"],
            "amount": [100.00, 200.50, 300.00, 400.25, 500.00],
            "is_active": [True, False, True, True, False],
            "created": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]),
        })
        from src.profiler import profile_dataset
        profiles = profile_dataset(df)
        results = detect_semantic_types(df, profiles)
        
        assert len(results) == 6
        detected = {r.column_name: r.detected_type for r in results}
        assert detected["id"] in ("Integer", "ID")
        assert detected["name"] == "String"
        assert detected["email"] == "Email"
        assert detected["amount"] in ("Currency", "Decimal")
        assert detected["is_active"] == "Boolean"
        assert detected["created"] == "Date"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])