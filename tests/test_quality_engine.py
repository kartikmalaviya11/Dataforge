"""Tests for Phase 4: Data Quality Engine"""

import pytest
import pandas as pd
import numpy as np

from src.type_detector import TypeDetectionResult
from src.profiler import profile_dataset
from src.quality_engine import (
    QualityIssue,
    run_quality_checks,
    check_missing_values,
    check_blank_values,
    check_duplicate_rows,
    check_duplicate_ids,
    check_invalid_emails,
    check_invalid_dates,
    check_invalid_numeric,
    check_invalid_categories,
    check_range_violations,
    check_consistency,
    ISSUE_MISSING_VALUE,
    ISSUE_BLANK_VALUE,
    ISSUE_DUPLICATE_ROW,
    ISSUE_DUPLICATE_ID,
    ISSUE_INVALID_EMAIL,
    ISSUE_INVALID_DATE,
    ISSUE_INVALID_NUMERIC,
    ISSUE_INVALID_CATEGORY,
    ISSUE_OUT_OF_RANGE,
    ISSUE_CONSISTENCY_VIOLATION,
)


def _tr(column_name, detected_type, storage_type="object"):
    """Build a TypeDetectionResult fixture without depending on Phase 3's
    actual detection heuristics -- keeps Phase 4 tests isolated."""
    return TypeDetectionResult(
        column_name=column_name,
        storage_type=storage_type,
        detected_type=detected_type,
        confidence=0.9,
        evidence="test fixture",
        status="OK",
        recommended_action="No action needed",
    )


# ─── Missing Values ──────────────────────────────────────────────────

class TestMissingValues:
    def test_flags_each_null_cell(self):
        df = pd.DataFrame({"a": [1, None, 3, None]})
        profiles = profile_dataset(df)
        issues = check_missing_values(df, profiles)
        assert len(issues) == 2
        assert all(i.issue_type == ISSUE_MISSING_VALUE for i in issues)
        assert {i.row_index for i in issues} == {1, 3}
        assert all(i.column == "a" for i in issues)

    def test_no_issues_when_no_nulls(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        profiles = profile_dataset(df)
        issues = check_missing_values(df, profiles)
        assert issues == []

    def test_all_null_column(self):
        df = pd.DataFrame({"a": [None, None, None]})
        profiles = profile_dataset(df)
        issues = check_missing_values(df, profiles)
        assert len(issues) == 3


# ─── Blank Values ────────────────────────────────────────────────────

class TestBlankValues:
    def test_flags_empty_and_whitespace_strings(self):
        df = pd.DataFrame({"name": ["Alice", "", "   ", "Bob", None]})
        profiles = profile_dataset(df)
        issues = check_blank_values(df, profiles)
        # "" and "   " are blank; None is missing (handled by a different check)
        assert len(issues) == 2
        assert {i.row_index for i in issues} == {1, 2}
        assert all(i.issue_type == ISSUE_BLANK_VALUE for i in issues)

    def test_does_not_flag_numeric_columns(self):
        df = pd.DataFrame({"amount": [0, 1, 2]})
        profiles = profile_dataset(df)
        issues = check_blank_values(df, profiles)
        assert issues == []

    def test_no_blanks(self):
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        profiles = profile_dataset(df)
        issues = check_blank_values(df, profiles)
        assert issues == []


# ─── Duplicate Rows ──────────────────────────────────────────────────

class TestDuplicateRows:
    def test_flags_later_copies_only(self):
        df = pd.DataFrame({
            "a": [1, 2, 1, 1],
            "b": ["x", "y", "x", "x"],
        })
        issues = check_duplicate_rows(df)
        # Row 0 is the original; rows 2 and 3 are duplicates of it.
        assert len(issues) == 2
        assert {i.row_index for i in issues} == {2, 3}
        assert all(i.column is None for i in issues)
        assert all(i.issue_type == ISSUE_DUPLICATE_ROW for i in issues)

    def test_no_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        issues = check_duplicate_rows(df)
        assert issues == []

    def test_empty_dataframe(self):
        df = pd.DataFrame({"a": []})
        issues = check_duplicate_rows(df)
        assert issues == []


# ─── Duplicate IDs ───────────────────────────────────────────────────

class TestDuplicateIds:
    def test_auto_detected_id_column(self):
        df = pd.DataFrame({"customer_id": [1, 2, 2, 3]})
        type_results = [_tr("customer_id", "ID")]
        issues = check_duplicate_ids(df, type_results)
        # Both rows sharing the value 2 are flagged (keep=False semantics).
        assert len(issues) == 2
        assert {i.row_index for i in issues} == {1, 2}
        assert all(i.issue_type == ISSUE_DUPLICATE_ID for i in issues)

    def test_explicit_override_for_numeric_id(self):
        # Phase 3 often classifies a purely numeric ID column as "Integer",
        # not "ID" -- id_columns lets the caller flag it anyway.
        df = pd.DataFrame({"customer_id": [1, 2, 3, 3, 5]})
        type_results = [_tr("customer_id", "Integer", storage_type="int64")]
        issues_auto = check_duplicate_ids(df, type_results)
        assert issues_auto == []
        issues_override = check_duplicate_ids(df, type_results, id_columns=["customer_id"])
        assert len(issues_override) == 2
        assert {i.row_index for i in issues_override} == {2, 3}

    def test_no_duplicates(self):
        df = pd.DataFrame({"customer_id": [1, 2, 3]})
        type_results = [_tr("customer_id", "ID")]
        issues = check_duplicate_ids(df, type_results)
        assert issues == []

    def test_nulls_not_flagged_as_duplicates(self):
        df = pd.DataFrame({"customer_id": [1, None, None, 3]})
        type_results = [_tr("customer_id", "ID")]
        issues = check_duplicate_ids(df, type_results)
        assert issues == []

    def test_missing_column_in_id_columns_is_ignored(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        issues = check_duplicate_ids(df, [], id_columns=["does_not_exist"])
        assert issues == []


# ─── Invalid Emails ──────────────────────────────────────────────────

class TestInvalidEmails:
    def test_flags_malformed_emails(self):
        df = pd.DataFrame({"email": ["a@b.com", "not-an-email", "c@d.com", None]})
        type_results = [_tr("email", "Email")]
        issues = check_invalid_emails(df, type_results)
        assert len(issues) == 1
        assert issues[0].row_index == 1
        assert issues[0].actual_value == "not-an-email"
        assert issues[0].issue_type == ISSUE_INVALID_EMAIL

    def test_all_valid(self):
        df = pd.DataFrame({"email": ["a@b.com", "c@d.org"]})
        type_results = [_tr("email", "Email")]
        issues = check_invalid_emails(df, type_results)
        assert issues == []

    def test_ignores_non_email_columns(self):
        df = pd.DataFrame({"name": ["not-an-email-but-not-checked"]})
        type_results = [_tr("name", "String")]
        issues = check_invalid_emails(df, type_results)
        assert issues == []


# ─── Invalid Dates ───────────────────────────────────────────────────

class TestInvalidDates:
    def test_flags_unparseable_dates(self):
        df = pd.DataFrame({"order_date": ["2024-01-01", "not-a-date", "2024-03-01"]})
        type_results = [_tr("order_date", "Date")]
        issues = check_invalid_dates(df, type_results)
        assert len(issues) == 1
        assert issues[0].row_index == 1
        assert issues[0].actual_value == "not-a-date"
        assert issues[0].issue_type == ISSUE_INVALID_DATE

    def test_skips_already_datetime_dtype(self):
        df = pd.DataFrame({"order_date": pd.to_datetime(["2024-01-01", "2024-02-01"])})
        type_results = [_tr("order_date", "Date", storage_type="datetime64[ns]")]
        issues = check_invalid_dates(df, type_results)
        assert issues == []

    def test_all_valid_strings(self):
        df = pd.DataFrame({"order_date": ["2024-01-01", "2024-02-01"]})
        type_results = [_tr("order_date", "Date")]
        issues = check_invalid_dates(df, type_results)
        assert issues == []


# ─── Invalid Numeric ─────────────────────────────────────────────────

class TestInvalidNumeric:
    def test_flags_non_numeric_currency_strings(self):
        df = pd.DataFrame({"amount": ["$100.00", "abc", "$2,500.50"]})
        type_results = [_tr("amount", "Currency")]
        issues = check_invalid_numeric(df, type_results)
        assert len(issues) == 1
        assert issues[0].row_index == 1
        assert issues[0].actual_value == "abc"
        assert issues[0].issue_type == ISSUE_INVALID_NUMERIC

    def test_tolerates_percentage_symbol(self):
        df = pd.DataFrame({"discount": ["10%", "not-a-number", "25.5%"]})
        type_results = [_tr("discount", "Percentage")]
        issues = check_invalid_numeric(df, type_results)
        assert len(issues) == 1
        assert issues[0].actual_value == "not-a-number"

    def test_skips_already_numeric_dtype(self):
        df = pd.DataFrame({"amount": [100, 200, 300]})
        type_results = [_tr("amount", "Integer", storage_type="int64")]
        issues = check_invalid_numeric(df, type_results)
        assert issues == []


# ─── Invalid Categories (opt-in) ─────────────────────────────────────

class TestInvalidCategories:
    def test_no_config_means_no_issues(self):
        df = pd.DataFrame({"status": ["active", "unknown_status"]})
        issues = check_invalid_categories(df)
        assert issues == []

    def test_flags_values_outside_allowed_set(self):
        df = pd.DataFrame({"status": ["active", "inactive", "bogus"]})
        issues = check_invalid_categories(df, allowed_categories={"status": {"active", "inactive"}})
        assert len(issues) == 1
        assert issues[0].row_index == 2
        assert issues[0].actual_value == "bogus"
        assert issues[0].issue_type == ISSUE_INVALID_CATEGORY

    def test_column_not_in_config_is_skipped(self):
        df = pd.DataFrame({"status": ["active"], "other": ["whatever"]})
        issues = check_invalid_categories(df, allowed_categories={"status": {"active"}})
        assert issues == []


# ─── Range Violations (opt-in) ───────────────────────────────────────

class TestRangeViolations:
    def test_no_config_means_no_issues(self):
        df = pd.DataFrame({"age": [-5, 200]})
        issues = check_range_violations(df)
        assert issues == []

    def test_flags_out_of_range_values(self):
        df = pd.DataFrame({"age": [25, -5, 150, 40]})
        issues = check_range_violations(df, column_ranges={"age": (18, 100)})
        assert len(issues) == 2
        assert {i.row_index for i in issues} == {1, 2}
        assert all(i.issue_type == ISSUE_OUT_OF_RANGE for i in issues)

    def test_boundary_values_are_not_flagged(self):
        df = pd.DataFrame({"age": [18, 100]})
        issues = check_range_violations(df, column_ranges={"age": (18, 100)})
        assert issues == []

    def test_open_ended_range(self):
        # Only a minimum is configured -- no upper bound check.
        df = pd.DataFrame({"quantity": [5, -1, 0, 10]})
        issues = check_range_violations(df, column_ranges={"quantity": (0, None)})
        assert len(issues) == 1
        assert issues[0].row_index == 1

    def test_negative_profit_not_flagged_without_explicit_rule(self):
        # Negative profit can be legitimate; the engine must not invent a rule.
        df = pd.DataFrame({"profit": [-500, 1000, -20]})
        issues = check_range_violations(df)
        assert issues == []


# ─── Consistency (opt-in) ────────────────────────────────────────────

class TestConsistency:
    def test_no_config_means_no_issues(self):
        df = pd.DataFrame({
            "order_date": ["2024-01-05", "2024-02-01"],
            "delivery_date": ["2024-01-01", "2024-02-10"],
        })
        issues = check_consistency(df, [])
        assert issues == []

    def test_flags_date_order_violation(self):
        df = pd.DataFrame({
            "order_date": ["2024-01-01", "2024-03-05"],
            "delivery_date": ["2024-01-10", "2024-03-01"],  # row 1: delivery before order
        })
        type_results = [_tr("order_date", "Date"), _tr("delivery_date", "Date")]
        rules = [{"name": "order_before_delivery", "column_a": "order_date",
                  "column_b": "delivery_date", "operator": "<="}]
        issues = check_consistency(df, type_results, consistency_rules=rules)
        assert len(issues) == 1
        assert issues[0].row_index == 1
        assert issues[0].issue_type == ISSUE_CONSISTENCY_VIOLATION
        assert issues[0].check_name == "order_before_delivery"

    def test_numeric_consistency(self):
        df = pd.DataFrame({"min_price": [10, 50], "max_price": [20, 40]})
        type_results = [_tr("min_price", "Currency"), _tr("max_price", "Currency")]
        rules = [{"name": "min_le_max", "column_a": "min_price",
                  "column_b": "max_price", "operator": "<="}]
        issues = check_consistency(df, type_results, consistency_rules=rules)
        assert len(issues) == 1
        assert issues[0].row_index == 1

    def test_unknown_columns_in_rule_are_ignored(self):
        df = pd.DataFrame({"a": [1, 2]})
        rules = [{"name": "bad_rule", "column_a": "a", "column_b": "does_not_exist", "operator": "<="}]
        issues = check_consistency(df, [], consistency_rules=rules)
        assert issues == []


# ─── Full Orchestrator ───────────────────────────────────────────────

class TestRunQualityChecks:
    def test_backward_compatible_three_arg_call(self):
        """main.py calls run_quality_checks(df, column_profiles, type_results)
        with no extra arguments -- this must keep working unmodified."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "email": ["a@b.com", "b@c.com", "c@d.com"],
        })
        profiles = profile_dataset(df)
        type_results = [_tr("id", "Integer", "int64"), _tr("email", "Email")]
        issues = run_quality_checks(df, profiles, type_results)
        assert issues == []

    def test_combines_multiple_issue_types(self):
        df = pd.DataFrame({
            "id": [1, 2, 2, 4],
            "email": ["a@b.com", "bad-email", "c@d.com", None],
        })
        profiles = profile_dataset(df)
        type_results = [_tr("id", "ID", "int64"), _tr("email", "Email")]
        issues = run_quality_checks(df, profiles, type_results)

        issue_types = {i.issue_type for i in issues}
        assert ISSUE_DUPLICATE_ID in issue_types
        assert ISSUE_INVALID_EMAIL in issue_types
        assert ISSUE_MISSING_VALUE in issue_types

    def test_configurable_checks_included_when_supplied(self):
        df = pd.DataFrame({"age": [25, 200], "status": ["active", "bogus"]})
        profiles = profile_dataset(df)
        type_results = [_tr("age", "Integer", "int64"), _tr("status", "Category")]
        issues = run_quality_checks(
            df, profiles, type_results,
            allowed_categories={"status": {"active", "inactive"}},
            column_ranges={"age": (0, 120)},
        )
        issue_types = {i.issue_type for i in issues}
        assert ISSUE_OUT_OF_RANGE in issue_types
        assert ISSUE_INVALID_CATEGORY in issue_types

    def test_full_pipeline_integration_with_real_phase3_detection(self):
        """End-to-end wiring check using the real Phase 1/2/3 output, not
        hand-built fixtures -- confirms Phase 4 integrates cleanly with
        the existing pipeline."""
        df = pd.DataFrame({
            "order_id": [f"ORD{i:04d}" for i in range(30)],
            "customer_email": [f"user{i}@example.com" for i in range(30)],
        })
        # Introduce a duplicate ID and an invalid email.
        df.loc[5, "order_id"] = df.loc[0, "order_id"]
        df.loc[10, "customer_email"] = "not-an-email"

        from src.type_detector import detect_semantic_types
        profiles = profile_dataset(df)
        type_results = detect_semantic_types(df, profiles)
        detected = {tr.column_name: tr.detected_type for tr in type_results}
        assert detected["order_id"] == "ID"
        assert detected["customer_email"] == "Email"

        issues = run_quality_checks(df, profiles, type_results)
        issue_types = {i.issue_type for i in issues}
        assert ISSUE_DUPLICATE_ID in issue_types
        assert ISSUE_INVALID_EMAIL in issue_types

    def test_empty_dataframe_does_not_crash(self):
        df = pd.DataFrame({"a": pd.Series(dtype="object"), "b": pd.Series(dtype="float64")})
        profiles = profile_dataset(df)
        type_results = [_tr("a", "String"), _tr("b", "Decimal", "float64")]
        issues = run_quality_checks(df, profiles, type_results)
        assert issues == []

    def test_single_row_dataframe(self):
        df = pd.DataFrame({"email": ["a@b.com"]})
        profiles = profile_dataset(df)
        type_results = [_tr("email", "Email")]
        issues = run_quality_checks(df, profiles, type_results)
        assert issues == []

    def test_custom_index_is_preserved_in_row_index(self):
        df = pd.DataFrame(
            {"email": ["a@b.com", "bad-email"]},
            index=["row_a", "row_b"],
        )
        profiles = profile_dataset(df)
        type_results = [_tr("email", "Email")]
        issues = run_quality_checks(df, profiles, type_results)
        assert len(issues) == 1
        assert issues[0].row_index == "row_b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])