"""Tests for Phase 2: Dataset Profiling"""

import pytest
import pandas as pd
import numpy as np
from src.profiler import profile_dataset, profile_column, ColumnProfile, is_numeric_type, is_datetime_type, is_string_type


class TestTypeHelpers:
    def test_is_numeric_type(self):
        assert is_numeric_type("int64")
        assert is_numeric_type("float64")
        assert is_numeric_type("Int64")  # nullable int
        assert is_numeric_type("INT64")  # case insensitive
        assert not is_numeric_type("object")
        assert not is_numeric_type("datetime64[ns]")
    
    def test_is_datetime_type(self):
        assert is_datetime_type("datetime64[ns]")
        assert is_datetime_type("datetimetz")
        assert is_datetime_type("DATETIME64[NS]")  # case insensitive
        assert not is_datetime_type("int64")
        assert not is_datetime_type("object")
    
    def test_is_string_type(self):
        assert is_string_type("object")
        assert is_string_type("string")
        assert is_string_type("str")  # pandas 2.x+ uses 'str'
        assert is_string_type("OBJECT")  # case insensitive
        assert not is_string_type("int64")
        assert not is_string_type("datetime64[ns]")


class TestProfileColumn:
    def test_numeric_column(self):
        s = pd.Series([1, 2, 3, 4, 5], name="test")
        profile = profile_column(s)
        
        assert profile.name == "test"
        assert profile.storage_type == "int64"
        assert profile.total_rows == 5
        assert profile.non_null_count == 5
        assert profile.null_count == 0
        assert profile.null_percentage == 0.0
        assert profile.unique_count == 5
        assert profile.unique_percentage == 100.0
        assert profile.min_value == 1.0
        assert profile.max_value == 5.0
        assert profile.mean_value == 3.0
        assert profile.median_value == 3.0
        assert profile.std_value == pytest.approx(1.581, rel=0.01)
    
    def test_numeric_with_nulls(self):
        s = pd.Series([1, 2, None, 4, 5], name="test")
        profile = profile_column(s)
        
        assert profile.null_count == 1
        assert profile.null_percentage == 20.0
        assert profile.non_null_count == 4
        assert profile.unique_count == 4
    
    def test_string_column(self):
        s = pd.Series(["apple", "banana", "cherry"], name="fruits")
        profile = profile_column(s)
        
        # pandas 2.x+ uses 'str' dtype for string data
        assert profile.storage_type in ("object", "str", "string")
        assert profile.min_length == 5  # apple
        assert profile.max_length == 6  # banana
        assert profile.avg_length == pytest.approx(5.67, rel=0.01)
    
    def test_string_with_nulls(self):
        s = pd.Series(["a", None, "bb"], name="test")
        profile = profile_column(s)
        
        assert profile.null_count == 1
        assert profile.non_null_count == 2
        assert profile.min_length == 1
        assert profile.max_length == 2
    
    def test_datetime_column(self):
        s = pd.Series(pd.to_datetime(["2024-01-01", "2024-06-15", "2024-12-31"]), name="dates")
        profile = profile_column(s)
        
        assert profile.storage_type.startswith("datetime")
        assert profile.min_date == pd.Timestamp("2024-01-01")
        assert profile.max_date == pd.Timestamp("2024-12-31")
    
    def test_all_null_column(self):
        s = pd.Series([None, None, None], name="empty")
        profile = profile_column(s)
        
        assert profile.null_count == 3
        assert profile.null_percentage == 100.0
        assert profile.non_null_count == 0
        assert profile.unique_count == 0
        assert profile.unique_percentage == 0.0
    
    def test_single_row(self):
        s = pd.Series([42], name="single")
        profile = profile_column(s)
        
        assert profile.total_rows == 1
        assert profile.unique_count == 1
        assert profile.min_value == 42.0
        assert profile.max_value == 42.0
        assert profile.mean_value == 42.0
        assert profile.median_value == 42.0
        assert profile.std_value == 0.0  # std of single value is 0


class TestProfileDataset:
    def test_mixed_dataframe(self):
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["A", "B", "C", "D", "E"],
            "value": [10.5, 20.0, None, 40.0, 50.0],
            "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]),
        })
        profiles = profile_dataset(df)
        
        assert len(profiles) == 4
        names = [p.name for p in profiles]
        assert set(names) == {"id", "name", "value", "date"}
        
        # Check each profile
        id_profile = next(p for p in profiles if p.name == "id")
        assert id_profile.storage_type == "int64"
        assert id_profile.min_value == 1.0
        
        value_profile = next(p for p in profiles if p.name == "value")
        assert value_profile.null_count == 1
        assert value_profile.null_percentage == 20.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])