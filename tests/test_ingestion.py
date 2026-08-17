"""Tests for Phase 1: Dataset Ingestion"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import os

from src.ingestion import load_dataset, IngestionError, detect_format, DatasetProfile


class TestDetectFormat:
    def test_csv(self):
        assert detect_format(Path("test.csv")) == "csv"
    def test_xlsx(self):
        assert detect_format(Path("test.xlsx")) == "xlsx"
    def test_xls(self):
        assert detect_format(Path("test.xls")) == "xlsx"
    def test_unsupported(self):
        with pytest.raises(IngestionError):
            detect_format(Path("test.txt"))


class TestLoadDataset:
    def test_load_csv(self, tmp_path):
        # Create a simple CSV
        csv_content = """id,name,value
1,Alice,100
2,Bob,200
3,Charlie,300
"""
        file_path = tmp_path / "test.csv"
        file_path.write_text(csv_content)
        
        df, profile = load_dataset(file_path)
        
        assert len(df) == 3
        assert list(df.columns) == ["id", "name", "value"]
        assert profile.row_count == 3
        assert profile.column_count == 3
        assert profile.file_format == "csv"
        assert profile.file_path == file_path
    
    def test_load_xlsx(self, tmp_path):
        # Create a simple Excel file
        df_orig = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "value": [100, 200, 300],
        })
        file_path = tmp_path / "test.xlsx"
        df_orig.to_excel(file_path, index=False)
        
        df, profile = load_dataset(file_path)
        
        assert len(df) == 3
        assert list(df.columns) == ["id", "name", "value"]
        assert profile.row_count == 3
        assert profile.column_count == 3
        assert profile.file_format == "xlsx"
    
    def test_file_not_found(self):
        with pytest.raises(IngestionError, match="File not found"):
            load_dataset(Path("nonexistent.csv"))
    
    def test_empty_file(self, tmp_path):
        file_path = tmp_path / "empty.csv"
        file_path.write_text("")
        with pytest.raises(IngestionError, match="empty"):
            load_dataset(file_path)
    
    def test_empty_data(self, tmp_path):
        file_path = tmp_path / "headers_only.csv"
        file_path.write_text("id,name,value\n")
        with pytest.raises(IngestionError, match="no rows"):
            load_dataset(file_path)
    
    def test_sample_size(self, tmp_path):
        csv_content = "id,value\n" + "\n".join(f"{i},{i*10}" for i in range(100))
        file_path = tmp_path / "large.csv"
        file_path.write_text(csv_content)
        
        df, profile = load_dataset(file_path, sample_size=10)
        
        assert len(df) == 10
        assert profile.sample_size == 10
        assert profile.row_count == 10  # Because we sampled
    
    def test_corrupted_csv(self, tmp_path):
        # Malformed CSV - unclosed quote
        file_path = tmp_path / "bad.csv"
        file_path.write_text('id,name\n1,"unclosed')
        with pytest.raises(IngestionError):
            load_dataset(file_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])