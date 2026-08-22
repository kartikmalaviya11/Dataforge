import pandas as pd
import numpy as np
import pytest

from src.issue_manager import IssueClassification
from src.repair_engine import (
    RepairEngine,
    RepairInstruction,
    RepairError
)

@pytest.fixture
def repair_engine():
    return RepairEngine()

def test_trim_whitespace(repair_engine):
    df = pd.DataFrame({"col_str": ["  A  ", "B", " C", "D "], "col_int": [1, 2, 3, 4]})
    inst = RepairInstruction(
        action="trim_whitespace",
        classification=IssueClassification.AUTO_FIXABLE,
        column="col_str"
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    
    res = results["instruction_0"]
    assert res.success is True
    assert res.affected_rows == 3
    assert len(res.change_records) == 3
    
    # Original dataset should not be mutated
    assert df.at[0, "col_str"] == "  A  "
    
    # Repaired dataset should be trimmed
    assert repaired_df.at[0, "col_str"] == "A"
    assert repaired_df.at[2, "col_str"] == "C"
    assert repaired_df.at[3, "col_str"] == "D"
    
def test_remove_exact_duplicates(repair_engine):
    df = pd.DataFrame({"A": [1, 2, 2, 3], "B": ["x", "y", "y", "z"]})
    inst = RepairInstruction(
        action="remove_exact_duplicates",
        classification=IssueClassification.AUTO_FIXABLE
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    
    res = results["instruction_0"]
    assert res.success is True
    assert res.affected_rows == 1
    assert len(repaired_df) == 3
    assert list(repaired_df["A"]) == [1, 2, 3]
    
    # Original should have 4 rows
    assert len(df) == 4

def test_convert_obvious_numeric(repair_engine):
    df = pd.DataFrame({"num": ["10", "25.5", "$100", "10%", "abc"]})
    inst = RepairInstruction(
        action="convert_obvious_numeric",
        classification=IssueClassification.AUTO_FIXABLE,
        column="num"
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    
    res = results["instruction_0"]
    assert res.success is True
    assert res.affected_rows == 2
    
    assert repaired_df.at[0, "num"] == 10
    assert repaired_df.at[1, "num"] == 25.5
    assert repaired_df.at[2, "num"] == "$100"  # untouched
    assert repaired_df.at[3, "num"] == "10%"   # untouched
    assert repaired_df.at[4, "num"] == "abc"   # untouched

def test_normalize_obvious_date(repair_engine):
    df = pd.DataFrame({"date_col": ["2023-01-01", "2023/12/31", "01-01-2023", "not_a_date"]})
    inst = RepairInstruction(
        action="normalize_obvious_date",
        classification=IssueClassification.AUTO_FIXABLE,
        column="date_col"
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    
    res = results["instruction_0"]
    assert res.success is True
    assert res.affected_rows == 2 # 2023-01-01 and 2023/12/31 are unambiguous in our list
    
    assert isinstance(repaired_df.at[0, "date_col"], pd.Timestamp)
    assert isinstance(repaired_df.at[1, "date_col"], pd.Timestamp)
    assert repaired_df.at[2, "date_col"] == "01-01-2023" # untouched (ambiguous to our rules)
    assert repaired_df.at[3, "date_col"] == "not_a_date"

def test_normalize_column_name_whitespace(repair_engine):
    df = pd.DataFrame({" Customer ID ": [1], "Email": ["a@b.com"]})
    inst = RepairInstruction(
        action="normalize_column_name_whitespace",
        classification=IssueClassification.AUTO_FIXABLE
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    
    res = results["instruction_0"]
    assert res.success is True
    assert res.affected_rows == 1
    
    assert list(repaired_df.columns) == ["Customer ID", "Email"]
    assert list(df.columns) == [" Customer ID ", "Email"]

def test_safety_rejects_unsafe(repair_engine):
    df = pd.DataFrame({"A": [1]})
    inst = RepairInstruction(
        action="trim_whitespace",
        classification=IssueClassification.UNSAFE_TO_FIX,
        column="A"
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    res = results["instruction_0"]
    assert res.success is False
    assert "UNSAFE_TO_FIX" in res.errors[0]

def test_safety_rejects_unapproved_review_required(repair_engine):
    df = pd.DataFrame({"A": [1]})
    inst = RepairInstruction(
        action="trim_whitespace",
        classification=IssueClassification.REVIEW_REQUIRED,
        column="A",
        approved=False
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    res = results["instruction_0"]
    assert res.success is False
    assert "REVIEW_REQUIRED" in res.errors[0]

def test_safety_allows_approved_review_required(repair_engine):
    df = pd.DataFrame({"A": ["  val  "]})
    inst = RepairInstruction(
        action="trim_whitespace",
        classification=IssueClassification.REVIEW_REQUIRED,
        column="A",
        approved=True
    )
    
    repaired_df, results = repair_engine.apply(df, [inst])
    res = results["instruction_0"]
    assert res.success is True
    assert res.affected_rows == 1

def test_invalid_instructions(repair_engine):
    df = pd.DataFrame({"A": [1]})
    inst1 = RepairInstruction(
        action="unknown_action",
        classification=IssueClassification.AUTO_FIXABLE
    )
    inst2 = RepairInstruction(
        action="trim_whitespace",
        classification=IssueClassification.AUTO_FIXABLE,
        column="missing_col"
    )
    
    repaired_df, results = repair_engine.apply(df, [inst1, inst2])
    
    assert results["instruction_0"].success is False
    assert "Unsupported repair action" in results["instruction_0"].errors[0]
    
    assert results["instruction_1"].success is False
    assert "missing_col" in results["instruction_1"].errors[0]

def test_convert_obvious_numeric_protect_identifiers(repair_engine):
    # Fix 1: Identifiers should not be converted, even if they look numeric
    df = pd.DataFrame({
        "Customer_ID": ["00123", "0007"], 
        "Reference number": ["000045", "99"],
        "Product Code": ["001", "123"],
        "Normal_Col": ["00123", "0.5"] # Normal col but with leading zero
    })
    
    inst1 = RepairInstruction(action="convert_obvious_numeric", classification=IssueClassification.AUTO_FIXABLE, column="Customer_ID")
    inst2 = RepairInstruction(action="convert_obvious_numeric", classification=IssueClassification.AUTO_FIXABLE, column="Reference number")
    inst3 = RepairInstruction(action="convert_obvious_numeric", classification=IssueClassification.AUTO_FIXABLE, column="Product Code")
    inst4 = RepairInstruction(action="convert_obvious_numeric", classification=IssueClassification.AUTO_FIXABLE, column="Normal_Col")
    
    repaired_df, results = repair_engine.apply(df, [inst1, inst2, inst3, inst4])
    
    assert results["instruction_0"].affected_rows == 0
    assert repaired_df.at[0, "Customer_ID"] == "00123"
    
    assert results["instruction_1"].affected_rows == 0
    assert repaired_df.at[0, "Reference number"] == "000045"
    
    assert results["instruction_2"].affected_rows == 0
    assert repaired_df.at[0, "Product Code"] == "001"
    
    # Even in a non-identifier column, leading zeros are skipped by the extra safety rule,
    # except "0.5" which is a valid decimal
    assert results["instruction_3"].affected_rows == 1
    assert repaired_df.at[0, "Normal_Col"] == "00123" # untouched
    assert repaired_df.at[1, "Normal_Col"] == 0.5 # converted

def test_convert_obvious_numeric_reject_special_floats(repair_engine):
    # Fix 2: Special numeric values should not be converted
    df = pd.DataFrame({
        "num": ["nan", "NaN", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "10"]
    })
    
    inst = RepairInstruction(action="convert_obvious_numeric", classification=IssueClassification.AUTO_FIXABLE, column="num")
    repaired_df, results = repair_engine.apply(df, [inst])
    
    assert results["instruction_0"].affected_rows == 1
    # Only "10" should have been converted
    assert repaired_df.at[10, "num"] == 10
    # Everything else should remain string
    for i in range(10):
        assert isinstance(repaired_df.at[i, "num"], str)

def test_regression_row_specific_instructions_do_not_sweep(repair_engine):
    # Setup dataframe with 3 identical errors
    df = pd.DataFrame({"num": ["10", "20", "30", "40"]})
    
    # We only approve repairing index 1 ("20" -> 20)
    inst = RepairInstruction(
        action="convert_obvious_numeric",
        classification=IssueClassification.REVIEW_REQUIRED,
        column="num",
        row_index=1,
        expected_state="20",
        proposed_value=20,
        reason="Test",
        approved=True
    )
    
    repaired_df, result = repair_engine.apply(df.copy(), [inst])
    
    # Only ONE row should have been affected
    assert result["instruction_0"].affected_rows == 1
    assert len(result["instruction_0"].change_records) == 1
    
    # Check that only index 1 was mutated
    assert isinstance(repaired_df.at[0, "num"], str)
    assert isinstance(repaired_df.at[1, "num"], int)
    assert isinstance(repaired_df.at[2, "num"], str)
