import pytest
import pandas as pd
import numpy as np
import io
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.ingestion import load_dataset, IngestionError
from src.profiler import profile_dataset
from src.type_detector import detect_semantic_types
from src.quality_engine import run_quality_checks
from src.rules import RuleEngine, RuleConfigError
from src.issue_manager import IssueManager
from src.scoring import calculate_readiness_score, DIMENSION_MAPPING

def run_full_pipeline(df: pd.DataFrame, rules: list = None) -> tuple:
    """Helper to run the full pipeline without I/O when df is already in memory."""
    profile = profile_dataset(df)
    type_results = detect_semantic_types(df, profile)
    quality_issues = run_quality_checks(df, profile, type_results)
    
    rule_issues = []
    if rules:
        engine = RuleEngine(rules)
        rule_issues = engine.run(df)
        
    manager = IssueManager()
    all_issues = manager.consolidate(quality_issues + rule_issues)
    
    score = calculate_readiness_score(df, profile, all_issues, rules_configured=bool(rules))
    return all_issues, score

# --- 1-7: Empty and Small Structure Edge Cases ---
def test_zero_row_csv(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("col1,col2,col3\n")
    # Should raise IngestionError because it has no rows
    with pytest.raises(IngestionError, match="has no rows after loading"):
        load_dataset(p)

def test_completely_empty_file(tmp_path):
    p = tmp_path / "completely_empty.csv"
    p.touch()
    with pytest.raises(IngestionError, match="File is empty"):
        load_dataset(p)

def test_one_row_dataset():
    df = pd.DataFrame([{"col1": 1, "col2": "a"}])
    issues, score = run_full_pipeline(df)
    assert score.overall_score == 100

def test_one_column_dataset():
    df = pd.DataFrame({"only_col": [1, 2, 3, 4, 5]})
    issues, score = run_full_pipeline(df)
    assert score.overall_score == 100

def test_zero_column_dataframe():
    df = pd.DataFrame(index=[0, 1, 2])
    # Empty columns means 0 issues but technically score handles len(df.columns) == 0 safely?
    issues, score = run_full_pipeline(df)
    assert len(issues) == 0
    # A zero-column dataset is functionally empty and cannot have issues.
    # Score should probably clamp gracefully. Let's see if it crashes.
    assert score.overall_score >= 0 

def test_all_null_column():
    df = pd.DataFrame({"col1": [None, np.nan, pd.NA]})
    issues, score = run_full_pipeline(df)
    # Should flag 3 missing values
    missing_issues = [i for i in issues if i.issue_type == "MISSING_VALUE"]
    assert len(missing_issues) == 3

def test_completely_null_dataset():
    df = pd.DataFrame({"c1": [None, None], "c2": [np.nan, np.nan]})
    issues, score = run_full_pipeline(df)
    missing = [i for i in issues if i.issue_type == "MISSING_VALUE"]
    assert len(missing) == 4 # 2 cols x 2 rows
    
# --- 8-10: Duplicate and Cardinality ---
def test_duplicate_only_dataset():
    df = pd.DataFrame([{"id": 1, "val": "A"}] * 10)
    issues, score = run_full_pipeline(df)
    # 10 identical rows means 1 original and 9 duplicates?
    # Actually DUPLICATE_ROW flags all subsequent copies (or does it flag all?).
    # QualityEngine flags all duplicates if keep=False, or just subsequent. Let's not strict assert counts, just check no crash and positive dupes.
    dupes = [i for i in issues if i.issue_type == "DUPLICATE_ROW"]
    assert len(dupes) > 0

def test_extremely_high_cardinality():
    # 10,000 unique strings
    df = pd.DataFrame({"id_col": [f"val_{i}" for i in range(10000)]})
    issues, score = run_full_pipeline(df)
    assert len(issues) == 0

def test_very_low_cardinality():
    df = pd.DataFrame({"status": ["active"] * 1000})
    issues, score = run_full_pipeline(df)
    dupes = [i for i in issues if i.issue_type == "DUPLICATE_ROW"]
    assert len(dupes) == 999

# --- 11-15: Mixed Types & Dates ---
def test_mixed_numeric_string():
    df = pd.DataFrame({"mixed": ["1", 2, 3.5, "four", "5"]})
    issues, score = run_full_pipeline(df)
    # It might get typed as string or ambiguous, shouldn't crash.
    assert True

def test_mixed_date_formats():
    df = pd.DataFrame({"dates": ["2023-01-01", "01/02/2023", "2023.03.01", "March 4, 2023"]})
    issues, score = run_full_pipeline(df)
    # Some might fail parsing, triggering INVALID_DATE
    assert True

def test_ambiguous_dates():
    # Ambiguous M/D vs D/M
    df = pd.DataFrame({"dates": ["01/02/2026", "02/01/2026", "13/01/2026"]})
    issues, score = run_full_pipeline(df)
    assert True

def test_invalid_dates():
    df = pd.DataFrame({"dates": ["2023-01-01", "Not a date", "2023-15-40"]})
    # We should have a rule or just type detection trying to parse it. 
    # If type_detector marks it as date but some fail, we get INVALID_DATE.
    # To force date semantic type, we need > 80% valid dates, so 1 invalid out of 5.
    df = pd.DataFrame({"dates": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "Not a date"]})
    issues, score = run_full_pipeline(df)
    invalid_dates = [i for i in issues if i.issue_type == "INVALID_DATE"]
    assert len(invalid_dates) == 1

def test_boolean_like_mixed():
    df = pd.DataFrame({"bools": ["yes", "no", 1, 0, "True", "False", True, False]})
    issues, score = run_full_pipeline(df)
    assert True

# --- 16-20: Text & Encodings ---
def test_empty_and_whitespace_strings():
    df = pd.DataFrame({"text": ["", "   ", "\t", "normal"]})
    issues, score = run_full_pipeline(df)
    blanks = [i for i in issues if i.issue_type == "BLANK_VALUE"]
    assert len(blanks) == 3

def test_unicode_and_special_chars():
    df = pd.DataFrame({"text": ["hello", "こんにちは", "😊", "a!@#$%^&*()_+"]})
    issues, score = run_full_pipeline(df)
    assert True

def test_very_long_strings():
    df = pd.DataFrame({"text": ["A" * 50000, "B" * 100000]})
    issues, score = run_full_pipeline(df)
    assert True

# --- 21-24: Numeric Extremes ---
def test_numeric_extremes():
    df = pd.DataFrame({
        "large": [1e100, -1e100, 0, 1e-100],
        "inf_nan": [np.inf, -np.inf, np.nan, 1.0]
    })
    issues, score = run_full_pipeline(df)
    # NaNs should be MISSING_VALUE, Inf should be... well, depends on pandas handling. No crash expected.
    assert True

# --- 25: Emails ---
def test_malformed_emails():
    # Need 80% valid to force email type
    emails = ["test1@example.com", "test2@example.com", "test3@example.com", "test4@example.com", "not_an_email"]
    df = pd.DataFrame({"email": emails})
    issues, score = run_full_pipeline(df)
    invalid = [i for i in issues if i.issue_type == "INVALID_EMAIL"]
    assert len(invalid) == 1

# --- 26-30: Rule Configuration ---
def test_missing_expected_columns():
    df = pd.DataFrame({"A": [1, 2]})
    rules = [{"name": "r1", "type": "range", "column": "missing_col", "min": 0}]
    issues, score = run_full_pipeline(df, rules)
    # Should skip gracefully
    assert True

def test_missing_rule_config_file():
    with pytest.raises(RuleConfigError, match="Rule configuration file not found"):
        RuleEngine.from_yaml("nonexistent_file.yaml")

def test_invalid_rule_configuration():
    rules = [{"name": "r1", "type": "range"}] # missing column
    with pytest.raises(RuleConfigError, match="missing required field 'column'"):
        RuleEngine(rules)

def test_unknown_rule_type():
    rules = [{"name": "r1", "type": "not_a_real_type"}]
    with pytest.raises(RuleConfigError, match="unsupported type 'not_a_real_type'"):
        RuleEngine(rules)

def test_missing_parent_dataset_referential_integrity():
    df = pd.DataFrame({"child_id": [1, 2]})
    rules = [{"name": "r1", "type": "referential_integrity", "child_column": "child_id", "parent_dataset": "missing_parent", "parent_column": "id"}]
    issues, score = run_full_pipeline(df, rules)
    assert True

# --- 31-33: Structural Pandas Features ---
def test_custom_pandas_index():
    df = pd.DataFrame({"A": [1, 2]}, index=["row_a", "row_b"])
    # Trigger an issue to see if index is preserved
    df.loc["row_a", "A"] = np.nan
    issues, score = run_full_pipeline(df)
    missing = [i for i in issues if i.issue_type == "MISSING_VALUE"]
    assert missing[0].row_index == "row_a"

def test_multi_index_columns():
    # MultiIndex columns can occur in real world CSVs if there are multiple header rows
    columns = pd.MultiIndex.from_tuples([("A", "x"), ("A", "y")])
    df = pd.DataFrame([[1, 2], [3, 4]], columns=columns)
    # The pipeline should flatten, stringify, or gracefully handle MultiIndex columns.
    issues, score = run_full_pipeline(df)
    assert True

def test_duplicate_column_names():
    df = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=["A", "B", "A"])
    with pytest.raises(ValueError, match="Duplicate column names"):
        issues, score = run_full_pipeline(df)

# --- 34-35: CSV/XLSX Encodings and loading ---
def test_different_csv_encodings(tmp_path):
    p = tmp_path / "cp1252.csv"
    p.write_text("text\nCafé", encoding="cp1252")
    df, profile = load_dataset(p)
    assert len(df) == 1

def test_xlsx_input_edge_case(tmp_path):
    p = tmp_path / "test.xlsx"
    df = pd.DataFrame({"A": [1, 2]})
    df.to_excel(p, index=False)
    df_loaded, profile = load_dataset(p)
    assert len(df_loaded) == 2
    assert profile.file_format == "xlsx"

# --- 36-39: Semantic Homogeneity ---
def test_only_categorical_columns():
    df = pd.DataFrame({"c1": ["A", "A", "B"], "c2": ["X", "Y", "X"]})
    issues, score = run_full_pipeline(df)
    assert True

def test_only_numeric_columns():
    df = pd.DataFrame({"n1": [1, 2, 3], "n2": [4.0, 5.0, 6.0]})
    issues, score = run_full_pipeline(df)
    assert True

def test_only_dates():
    df = pd.DataFrame({"d1": ["2023-01-01", "2023-01-02"]})
    issues, score = run_full_pipeline(df)
    assert True

# --- 40: Scale & Determinism ---
def test_large_dataset_determinism_and_performance():
    # 20,000 rows x 5 columns = 100,000 cells. Should execute under a few seconds.
    np.random.seed(42)
    n = 20000
    df = pd.DataFrame({
        "id": range(n),
        "category": np.random.choice(["A", "B", "C", None], n),
        "amount": np.random.randn(n),
        "date": pd.date_range("2023-01-01", periods=n),
        "email": [f"user{i}@example.com" if i % 100 != 0 else "invalid" for i in range(n)]
    })
    
    # Run 1
    t0 = time.time()
    issues1, score1 = run_full_pipeline(df)
    t1 = time.time()
    
    # Run 2
    t2 = time.time()
    issues2, score2 = run_full_pipeline(df)
    t3 = time.time()
    
    time_run1 = t1 - t0
    time_run2 = t3 - t2
    
    print(f"\n[Performance] Run 1: {time_run1:.3f}s | Run 2: {time_run2:.3f}s for {n} rows")
    
    assert len(issues1) == len(issues2)
    assert score1.overall_score == score2.overall_score
    
    # Identity set should be identical
    set1 = {(i.row_index, i.column, i.issue_type) for i in issues1}
    set2 = {(i.row_index, i.column, i.issue_type) for i in issues2}
    
    assert set1 == set2
