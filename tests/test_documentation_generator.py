
import os
import shutil
import pytest
from src.documentation_generator import DocumentationGenerator

@pytest.fixture
def generator():
    test_dir = ".dataforge_test/docs"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    yield DocumentationGenerator(test_dir)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_each_document(generator):
    meta = {
        "columns": [{"name": "id", "type": "int", "description": "ID"}],
        "quality_score": 99,
        "cleaning_logs": ["Cleaned nulls"],
        "relationships": [{"from": "A", "to": "B"}],
        "kpis": {"sales": "Sum of sales"},
        "sql_queries": ["SELECT * FROM A"],
        "findings": ["Sales increased"],
        "summary": "Great project"
    }
    docs = generator.generate_all(meta)
    assert "data_dictionary.md" in docs
    assert "**id** (int): ID" in docs["data_dictionary.md"]
    assert "Score: 99" in docs["data_quality_report.md"]

def test_deterministic_content(generator):
    meta = {
        "columns": [
            {"name": "b", "type": "int"},
            {"name": "a", "type": "int"}
        ]
    }
    doc = generator.generate_data_dictionary(meta)
    assert doc.index("**a**") < doc.index("**b**")

def test_missing_metadata(generator):
    docs = generator.generate_all({})
    assert "No columns metadata provided." in docs["data_dictionary.md"]

def test_persistence(generator):
    generator.generate_all({"summary": "test persist"})
    assert os.path.exists(os.path.join(generator.persistence_dir, "project_summary.md"))
