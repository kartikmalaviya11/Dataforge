"""
Phase 4: Data Quality Engine

Deterministic, explainable data-quality checks.

Design principles (see project master prompt, sections 13 / 27 / 38):
  - Generic checks (missing values, blanks, duplicate rows, duplicate IDs,
    invalid emails, invalid dates, invalid numeric values) require NO
    external configuration. They are driven entirely by what Phase 1
    (ingestion), Phase 2 (profiling), and Phase 3 (semantic type detection)
    already determined about the dataset.
  - Configurable checks (allowed categories, numeric ranges, cross-column
    consistency rules) are strictly opt-in. If the caller does not supply
    a rule for a given column, that column is skipped entirely -- this
    module never assumes a business rule that wasn't explicitly given.
  - This keeps "generic data quality" cleanly separated from "business
    rules": Phase 5 (rules.py / RuleEngine) will introduce a full
    YAML-driven rule system for business rules, and can either call the
    configurable checks here directly or build additional rule types on
    top of the same QualityIssue schema.
  - Every issue is a single, explainable record: which row, which column,
    what check flagged it, what the actual value was, and what was
    expected. Severity and remediation recommendations are intentionally
    NOT assigned here -- that is Phase 6's (Issue Manager's) job.
"""

from dataclasses import dataclass
from typing import Any, Optional
import operator
import re

import numpy as np
import pandas as pd
from loguru import logger

from .profiler import is_string_type

# ─── Issue Type Constants ───────────────────────────────────────────

ISSUE_MISSING_VALUE = "MISSING_VALUE"
ISSUE_BLANK_VALUE = "BLANK_VALUE"
ISSUE_DUPLICATE_ROW = "DUPLICATE_ROW"
ISSUE_DUPLICATE_ID = "DUPLICATE_ID"
ISSUE_INVALID_EMAIL = "INVALID_EMAIL"
ISSUE_INVALID_DATE = "INVALID_DATE"
ISSUE_INVALID_NUMERIC = "INVALID_NUMERIC"
ISSUE_INVALID_CATEGORY = "INVALID_CATEGORY"
ISSUE_OUT_OF_RANGE = "OUT_OF_RANGE"
ISSUE_CONSISTENCY_VIOLATION = "CONSISTENCY_VIOLATION"

# Semantic types (from Phase 3) that check_invalid_numeric applies to.
_NUMERIC_SEMANTIC_TYPES = {"Integer", "Decimal", "Currency", "Percentage"}

# Semantic types (from Phase 3) that count as "date-like" for consistency checks.
_DATE_SEMANTIC_TYPES = {"Date", "DateTime"}

# Characters stripped before attempting to parse a value as numeric.
# Covers common currency symbols, percentage signs, and thousands separators.
_NUMERIC_STRIP_TABLE = str.maketrans("", "", "$€£¥%,")

_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

_CONSISTENCY_OPERATORS = {
    "<=": operator.le,
    "<": operator.lt,
    ">=": operator.ge,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}


# ─── Result Dataclass ───────────────────────────────────────────────

@dataclass
class QualityIssue:
    """
    A single, explainable data-quality issue.

    Fields are intentionally minimal and generic so this schema can be
    reused by Phase 5 (business rules) and consumed by Phase 6 (issue
    management, which adds severity) and Phase 13 (Power BI-ready export).
    """
    row_index: Optional[Any]        # pandas index label of the affected row
    column: Optional[str]           # affected column (None for whole-row issues)
    issue_type: str                 # one of the ISSUE_* constants above
    check_name: str                 # name of the specific check/rule that fired
    actual_value: Optional[Any] = None
    expected_condition: Optional[str] = None
    description: str = ""           # short, human-readable explanation


def _to_native(value: Any) -> Any:
    """Convert numpy/pandas scalar types to plain Python types for clean export."""
    if value is None:
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _is_parseable_numeric(value: Any) -> bool:
    """Check whether a single value can be interpreted as a number, tolerating
    common currency/percentage formatting ($1,234.56, 45%, etc.)."""
    if isinstance(value, (int, float, np.integer, np.floating)):
        return not (isinstance(value, float) and np.isnan(value))
    text = str(value).strip()
    if not text:
        return False
    cleaned = text.translate(_NUMERIC_STRIP_TABLE).strip()
    if cleaned in ("", "-", ".", "-."):
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


# ─── Individual Checks ──────────────────────────────────────────────

def check_missing_values(df: pd.DataFrame, column_profiles: list) -> list[QualityIssue]:
    """Flag every null cell. Generic -- no configuration required."""
    issues: list[QualityIssue] = []
    for profile in column_profiles:
        col = profile.name
        if col not in df.columns:
            continue
        mask = df[col].isna()
        if not mask.any():
            continue
        for idx in df.index[mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_MISSING_VALUE,
                check_name="missing_value_check",
                actual_value=None,
                expected_condition="Non-null value expected",
                description=f"Column '{col}' is missing a value in this row.",
            ))
    return issues


def check_blank_values(df: pd.DataFrame, column_profiles: list) -> list[QualityIssue]:
    """Flag non-null but empty/whitespace-only text values. Only applies to
    string-like columns; generic -- no configuration required."""
    issues: list[QualityIssue] = []
    for profile in column_profiles:
        col = profile.name
        if col not in df.columns or not is_string_type(profile.storage_type):
            continue
        series = df[col]
        non_null_mask = series.notna()
        if not non_null_mask.any():
            continue
        str_series = series.astype(str)
        blank_mask = non_null_mask & (str_series.str.strip() == "")
        if not blank_mask.any():
            continue
        for idx in df.index[blank_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_BLANK_VALUE,
                check_name="blank_value_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition="Non-blank text value expected",
                description=f"Column '{col}' contains a blank or whitespace-only value.",
            ))
    return issues


def check_duplicate_rows(df: pd.DataFrame) -> list[QualityIssue]:
    """Flag rows that are exact duplicates of an earlier row (keeps the first
    occurrence clean, flags the later copies). Generic -- no configuration."""
    issues: list[QualityIssue] = []
    if df.empty:
        return issues
    dup_mask = df.duplicated(keep="first")
    if not dup_mask.any():
        return issues
    for idx in df.index[dup_mask]:
        issues.append(QualityIssue(
            row_index=_to_native(idx),
            column=None,
            issue_type=ISSUE_DUPLICATE_ROW,
            check_name="duplicate_row_check",
            actual_value=None,
            expected_condition="Row should be unique across all columns",
            description="This row is an exact duplicate of an earlier row in the dataset.",
        ))
    return issues


def check_duplicate_ids(
    df: pd.DataFrame,
    type_results: list,
    id_columns: Optional[list[str]] = None,
) -> list[QualityIssue]:
    """
    Flag rows whose value in an ID-like column is shared by another row.

    ID columns are identified automatically from Phase 3's semantic type
    detection (detected_type == "ID"), plus any explicit override supplied
    via `id_columns`. Unlike duplicate-row detection, ALL rows sharing a
    duplicate ID are flagged (not just the later copies) -- for a primary
    key, there is no way to tell which copy is "the real one," so the
    analyst needs to see every row involved.
    """
    issues: list[QualityIssue] = []
    detected_id_cols = {tr.column_name for tr in type_results if tr.detected_type == "ID"}
    candidate_cols = set(id_columns or []) | detected_id_cols

    for col in candidate_cols:
        if col not in df.columns:
            continue
        series = df[col]
        non_null_mask = series.notna()
        if not non_null_mask.any():
            continue
        dup_mask = non_null_mask & series.duplicated(keep=False)
        if not dup_mask.any():
            continue
        for idx in df.index[dup_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_DUPLICATE_ID,
                check_name="duplicate_id_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition=f"Values in '{col}' should be unique",
                description=f"The value in '{col}' is shared by more than one row.",
            ))
    return issues


def check_invalid_emails(df: pd.DataFrame, type_results: list) -> list[QualityIssue]:
    """Flag values that don't match a valid email pattern, in columns Phase 3
    detected as semantically Email. Generic -- no configuration required."""
    issues: list[QualityIssue] = []
    email_cols = [tr.column_name for tr in type_results if tr.detected_type == "Email"]

    for col in email_cols:
        if col not in df.columns:
            continue
        series = df[col]
        non_null_series = series.dropna()
        if non_null_series.empty:
            continue
        str_series = non_null_series.astype(str).str.strip()
        valid_mask = str_series.apply(lambda x: bool(_EMAIL_PATTERN.match(x)))
        invalid_index = str_series.index[~valid_mask]
        for idx in invalid_index:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_INVALID_EMAIL,
                check_name="invalid_email_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition="Value should match a valid email address pattern",
                description=f"Value in '{col}' does not look like a valid email address.",
            ))
    return issues


def check_invalid_dates(df: pd.DataFrame, type_results: list) -> list[QualityIssue]:
    """Flag values that can't be parsed as dates, in columns Phase 3 detected
    as semantically Date/DateTime. Generic -- no configuration required.

    Columns already stored as a proper datetime64 dtype are skipped: if
    ingestion/pandas already parsed every value successfully, there is
    nothing left to flag at the individual-value level.
    """
    issues: list[QualityIssue] = []
    date_cols = [tr.column_name for tr in type_results if tr.detected_type in _DATE_SEMANTIC_TYPES]

    for col in date_cols:
        if col not in df.columns:
            continue
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        non_null_mask = series.notna()
        if not non_null_mask.any():
            continue
        parsed = pd.to_datetime(series, errors="coerce")
        invalid_mask = non_null_mask & parsed.isna()
        for idx in df.index[invalid_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_INVALID_DATE,
                check_name="invalid_date_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition="Value should be a parseable date",
                description=f"Value in '{col}' could not be parsed as a date.",
            ))
    return issues


def check_invalid_numeric(df: pd.DataFrame, type_results: list) -> list[QualityIssue]:
    """Flag values that can't be interpreted as numeric, in columns Phase 3
    detected as semantically Integer/Decimal/Currency/Percentage. Tolerates
    common currency/percentage formatting. Generic -- no configuration.

    Columns already stored as a numeric dtype are skipped: there is no
    per-value parse failure possible once pandas has already stored the
    column as int/float.
    """
    issues: list[QualityIssue] = []
    numeric_cols = [tr.column_name for tr in type_results if tr.detected_type in _NUMERIC_SEMANTIC_TYPES]

    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            continue
        non_null_mask = series.notna()
        if not non_null_mask.any():
            continue
        valid_mask = series.apply(_is_parseable_numeric)
        invalid_mask = non_null_mask & ~valid_mask
        for idx in df.index[invalid_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_INVALID_NUMERIC,
                check_name="invalid_numeric_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition="Value should be numeric",
                description=f"Value in '{col}' could not be interpreted as a numeric value.",
            ))
    return issues


def check_invalid_categories(
    df: pd.DataFrame,
    allowed_categories: Optional[dict[str, set]] = None,
) -> list[QualityIssue]:
    """
    Flag values not in an explicitly configured allowed set for a column.

    Strictly opt-in: if `allowed_categories` is not supplied, or a column
    isn't a key in it, that column is skipped entirely. This module never
    guesses what a "valid" category is for a dataset it hasn't been told
    about -- that would violate "do not assume every dataset has the same
    business rules."
    """
    issues: list[QualityIssue] = []
    if not allowed_categories:
        return issues

    for col, allowed in allowed_categories.items():
        if col not in df.columns:
            continue
        allowed_set = set(allowed)
        series = df[col]
        non_null_mask = series.notna()
        if not non_null_mask.any():
            continue
        invalid_mask = non_null_mask & ~series.isin(allowed_set)
        if not invalid_mask.any():
            continue
        expected = f"Value should be one of: {sorted(str(a) for a in allowed_set)}"
        for idx in df.index[invalid_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_INVALID_CATEGORY,
                check_name="invalid_category_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition=expected,
                description=f"Value in '{col}' is not one of the allowed categories.",
            ))
    return issues


def check_range_violations(
    df: pd.DataFrame,
    column_ranges: Optional[dict[str, tuple[Optional[float], Optional[float]]]] = None,
) -> list[QualityIssue]:
    """
    Flag numeric values outside a configured [min, max] range (inclusive).

    Strictly opt-in: if `column_ranges` is not supplied, or a column isn't
    a key in it, that column is skipped entirely -- e.g. a negative Profit
    value is never flagged unless the caller explicitly configured a range
    for the Profit column.
    """
    issues: list[QualityIssue] = []
    if not column_ranges:
        return issues

    for col, bounds in column_ranges.items():
        if col not in df.columns:
            continue
        min_val, max_val = bounds
        raw = df[col]
        numeric = pd.to_numeric(raw, errors="coerce")
        comparable_mask = raw.notna() & numeric.notna()
        if not comparable_mask.any():
            continue

        below = pd.Series(False, index=df.index)
        above = pd.Series(False, index=df.index)
        if min_val is not None:
            below = numeric < min_val
        if max_val is not None:
            above = numeric > max_val
        violation_mask = comparable_mask & (below | above)
        if not violation_mask.any():
            continue

        condition_parts = []
        if min_val is not None:
            condition_parts.append(f">= {min_val}")
        if max_val is not None:
            condition_parts.append(f"<= {max_val}")
        expected = " and ".join(condition_parts)

        for idx in df.index[violation_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_OUT_OF_RANGE,
                check_name="range_check",
                actual_value=_to_native(raw.loc[idx]),
                expected_condition=expected,
                description=f"Value in '{col}' is outside the configured allowed range.",
            ))
    return issues


def check_consistency(
    df: pd.DataFrame,
    type_results: list,
    consistency_rules: Optional[list[dict]] = None,
) -> list[QualityIssue]:
    """
    Flag rows that violate a configured cross-column relationship, e.g.
    Order_Date <= Delivery_Date.

    Strictly opt-in: if `consistency_rules` is not supplied, nothing is
    checked. Each rule is a dict:
        {"name": str, "column_a": str, "column_b": str, "operator": str}
    where operator is one of "<=", "<", ">=", ">", "==", "!=", meaning
    `column_a <operator> column_b` is expected to hold.

    Comparison mode (datetime vs numeric) is chosen using Phase 3's
    semantic type detection for the two columns, so this reuses existing
    type information rather than re-guessing.
    """
    issues: list[QualityIssue] = []
    if not consistency_rules:
        return issues

    type_by_col = {tr.column_name: tr.detected_type for tr in type_results}

    for rule in consistency_rules:
        name = rule.get("name", "consistency_check")
        col_a = rule.get("column_a")
        col_b = rule.get("column_b")
        op_symbol = rule.get("operator", "<=")
        op_func = _CONSISTENCY_OPERATORS.get(op_symbol)

        if col_a not in df.columns or col_b not in df.columns or op_func is None:
            continue

        series_a = df[col_a]
        series_b = df[col_b]

        use_datetime = (
            type_by_col.get(col_a) in _DATE_SEMANTIC_TYPES
            or type_by_col.get(col_b) in _DATE_SEMANTIC_TYPES
        )
        if use_datetime:
            cmp_a = pd.to_datetime(series_a, errors="coerce")
            cmp_b = pd.to_datetime(series_b, errors="coerce")
        else:
            cmp_a = pd.to_numeric(series_a, errors="coerce")
            cmp_b = pd.to_numeric(series_b, errors="coerce")

        comparable_mask = cmp_a.notna() & cmp_b.notna()
        if not comparable_mask.any():
            continue

        violation_mask = comparable_mask & ~op_func(cmp_a, cmp_b)
        if not violation_mask.any():
            continue

        expected = f"{col_a} {op_symbol} {col_b}"
        for idx in df.index[violation_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=f"{col_a} / {col_b}",
                issue_type=ISSUE_CONSISTENCY_VIOLATION,
                check_name=name,
                actual_value=f"{col_a}={_to_native(series_a.loc[idx])!r}, {col_b}={_to_native(series_b.loc[idx])!r}",
                expected_condition=expected,
                description=f"Row violates consistency rule: {expected}.",
            ))
    return issues


# ─── Orchestrator ────────────────────────────────────────────────────

def run_quality_checks(
    df: pd.DataFrame,
    column_profiles: list,
    type_results: list,
    id_columns: Optional[list[str]] = None,
    allowed_categories: Optional[dict[str, set]] = None,
    column_ranges: Optional[dict[str, tuple[Optional[float], Optional[float]]]] = None,
    consistency_rules: Optional[list[dict]] = None,
) -> list[QualityIssue]:
    """
    Run all Phase 4 data-quality checks and return a combined, flat list of
    QualityIssue records.

    Generic checks (missing, blank, duplicate rows, duplicate IDs, invalid
    email/date/numeric) always run and require no configuration. The
    configurable checks (categories, ranges, consistency) only produce
    issues when the corresponding parameter is supplied -- omit them and
    those checks are simply skipped, not treated as "no issues found."

    This function's signature is backward compatible with a 3-argument
    call (df, column_profiles, type_results); the optional parameters
    exist so Phase 5's business-rule engine can pass configuration
    straight through without needing a different entry point.
    """
    logger.info("Running Phase 4 data quality checks...")
    issues: list[QualityIssue] = []

    issues += check_missing_values(df, column_profiles)
    issues += check_blank_values(df, column_profiles)
    issues += check_duplicate_rows(df)
    issues += check_duplicate_ids(df, type_results, id_columns=id_columns)
    issues += check_invalid_emails(df, type_results)
    issues += check_invalid_dates(df, type_results)
    issues += check_invalid_numeric(df, type_results)
    issues += check_invalid_categories(df, allowed_categories=allowed_categories)
    issues += check_range_violations(df, column_ranges=column_ranges)
    issues += check_consistency(df, type_results, consistency_rules=consistency_rules)

    logger.info(f"Data quality checks complete: {len(issues)} issue(s) found")
    return issues