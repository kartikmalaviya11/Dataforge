"""
Phase 4: Data Quality Engine

Deterministic, explainable data-quality checks.
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
ISSUE_POTENTIAL_DUPLICATE = "POTENTIAL_DUPLICATE"
ISSUE_WHITESPACE = "WHITESPACE"
ISSUE_INCONSISTENT_CASE = "INCONSISTENT_CASE"

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


def _get_missing_mask(series: pd.Series, custom_missing_markers: Optional[set[str]] = None) -> pd.Series:
    """Returns a boolean mask of values that are conceptually missing."""
    mask = series.isna()
    # Check for empty strings or whitespace-only strings
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        str_s = series.astype(str).str.strip()
        mask = mask | (str_s == "")
        if custom_missing_markers:
            lower_s = str_s.str.lower()
            lower_markers = {m.lower() for m in custom_missing_markers}
            mask = mask | lower_s.isin(lower_markers)
    return mask

# ─── Individual Checks ──────────────────────────────────────────────

def check_missing_values(
    df: pd.DataFrame, 
    column_profiles: list, 
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for profile in column_profiles:
        col = profile.name
        if col not in df.columns:
            continue
        mask = _get_missing_mask(df[col], custom_missing_markers)
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


def check_whitespace_issues(df: pd.DataFrame, column_profiles: list, custom_missing_markers: Optional[set[str]] = None) -> list[QualityIssue]:
    """Flag non-null string values containing leading or trailing whitespace."""
    issues: list[QualityIssue] = []
    for profile in column_profiles:
        col = profile.name
        if col not in df.columns or not is_string_type(profile.storage_type):
            continue
        series = df[col]
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        # Identify rows that are not missing, but have leading/trailing whitespace
        str_series = series.astype(str)
        ws_mask = ~missing_mask & str_series.str.contains(r"^\s+|\s+$", regex=True)
        if not ws_mask.any():
            continue
        for idx in df.index[ws_mask]:
            issues.append(QualityIssue(
                row_index=_to_native(idx),
                column=col,
                issue_type=ISSUE_WHITESPACE,
                check_name="whitespace_check",
                actual_value=_to_native(series.loc[idx]),
                expected_condition="No leading/trailing whitespace",
                description=f"Value contains leading/trailing whitespace.",
            ))
    return issues


def check_case_inconsistencies(df: pd.DataFrame, column_profiles: list, custom_missing_markers: Optional[set[str]] = None) -> list[QualityIssue]:
    """Flag values that share the same case-insensitive string but have different raw casing variants."""
    issues: list[QualityIssue] = []
    for profile in column_profiles:
        col = profile.name
        if col not in df.columns or not is_string_type(profile.storage_type):
            continue
        series = df[col]
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        valid_series = series[~missing_mask].astype(str)
        if valid_series.empty:
            continue
        
        # Group by normalized lowercase value
        normalized = valid_series.str.strip().str.lower()
        grouped = valid_series.groupby(normalized)
        
        for norm_val, group in grouped:
            unique_raw_values = group.unique()
            if len(unique_raw_values) > 1:
                # We have inconsistencies
                for idx in group.index:
                    issues.append(QualityIssue(
                        row_index=_to_native(idx),
                        column=col,
                        issue_type=ISSUE_INCONSISTENT_CASE,
                        check_name="case_inconsistency_check",
                        actual_value=_to_native(series.loc[idx]),
                        expected_condition="Consistent casing across dataset",
                        description=f"Value has inconsistent casing variations in the dataset: {list(unique_raw_values)}",
                    ))
    return issues


def check_blank_values(df: pd.DataFrame, column_profiles: list) -> list[QualityIssue]:
    # Deprecated/Removed in favor of whitespace check and robust missing values,
    # but we will return an empty list to avoid breaking anything that strictly imports it.
    return []


def check_duplicate_rows(df: pd.DataFrame) -> list[QualityIssue]:
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


def check_potential_duplicates(
    df: pd.DataFrame,
    type_results: list,
    id_columns: Optional[list[str]] = None,
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
    """Flag rows that match on strong identifiers (Email/Phone) or match on all non-ID columns."""
    issues: list[QualityIssue] = []
    if df.empty:
        return issues
        
    detected_id_cols = {tr.column_name for tr in type_results if tr.detected_type == "ID"}
    candidate_id_cols = set(id_columns or []) | detected_id_cols
    candidate_id_cols = {c for c in candidate_id_cols if c in df.columns}
    
    non_id_cols = [c for c in df.columns if c not in candidate_id_cols]
    
    email_cols = [tr.column_name for tr in type_results if tr.detected_type == "Email" and tr.column_name in df.columns]
    phone_cols = [tr.column_name for tr in type_results if tr.detected_type == "Phone" and tr.column_name in df.columns]
    # In case Semantic type misses, fallback to names
    for c in df.columns:
        c_lower = str(c).lower()
        if "email" in c_lower and c not in email_cols:
            email_cols.append(c)
        if "phone" in c_lower and c not in phone_cols:
            phone_cols.append(c)

    # Normalize dataframe for comparison
    norm_df = df.copy()
    for col in norm_df.columns:
        missing_mask = _get_missing_mask(norm_df[col], custom_missing_markers)
        if norm_df[col].dtype == object or pd.api.types.is_string_dtype(norm_df[col]):
            norm_df.loc[~missing_mask, col] = norm_df.loc[~missing_mask, col].astype(str).str.strip().str.lower()
        norm_df.loc[missing_mask, col] = np.nan
        
    potential_indices = set()
    
    # 1. Match by Email
    for c in email_cols:
        non_null = norm_df[c].notna()
        dups = norm_df[non_null].duplicated(subset=[c], keep=False)
        potential_indices.update(dups[dups].index)
        
    # 2. Match by Phone
    for c in phone_cols:
        non_null = norm_df[c].notna()
        dups = norm_df[non_null].duplicated(subset=[c], keep=False)
        potential_indices.update(dups[dups].index)
        
    # 3. Match by all non-ID columns
    if non_id_cols:
        dups = norm_df.duplicated(subset=non_id_cols, keep=False)
        potential_indices.update(dups[dups].index)
        
    # Remove exact duplicates from potential
    exact_dups_mask = df.duplicated(keep=False)
    exact_dup_indices = set(df.index[exact_dups_mask])
    
    potential_indices = potential_indices - exact_dup_indices
    
    for idx in sorted(list(potential_indices)):
        issues.append(QualityIssue(
            row_index=_to_native(idx),
            column=None,
            issue_type=ISSUE_POTENTIAL_DUPLICATE,
            check_name="potential_duplicate_check",
            actual_value=None,
            expected_condition="Entities should be distinct or normalized",
            description="This row is a potential normalized duplicate of another record.",
        ))
        
    return issues


def check_duplicate_ids(
    df: pd.DataFrame,
    type_results: list,
    id_columns: Optional[list[str]] = None,
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    detected_id_cols = {tr.column_name for tr in type_results if tr.detected_type == "ID"}
    candidate_cols = set(id_columns or []) | detected_id_cols

    for col in candidate_cols:
        if col not in df.columns:
            continue
        series = df[col]
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        non_null_mask = ~missing_mask
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


def check_invalid_emails(df: pd.DataFrame, type_results: list, custom_missing_markers: Optional[set[str]] = None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    email_cols = [tr.column_name for tr in type_results if tr.detected_type == "Email"]

    for col in email_cols:
        if col not in df.columns:
            continue
        series = df[col]
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        non_null_series = series[~missing_mask]
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


def check_invalid_dates(df: pd.DataFrame, type_results: list, custom_missing_markers: Optional[set[str]] = None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    date_cols = [tr.column_name for tr in type_results if tr.detected_type in _DATE_SEMANTIC_TYPES]

    for col in date_cols:
        if col not in df.columns:
            continue
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            continue
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        non_null_mask = ~missing_mask
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


def check_invalid_numeric(df: pd.DataFrame, type_results: list, custom_missing_markers: Optional[set[str]] = None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    numeric_cols = [tr.column_name for tr in type_results if tr.detected_type in _NUMERIC_SEMANTIC_TYPES]

    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            continue
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        non_null_mask = ~missing_mask
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
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if not allowed_categories:
        return issues

    for col, allowed in allowed_categories.items():
        if col not in df.columns:
            continue
        allowed_set = set(allowed)
        series = df[col]
        missing_mask = _get_missing_mask(series, custom_missing_markers)
        non_null_mask = ~missing_mask
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
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if not column_ranges:
        return issues

    for col, bounds in column_ranges.items():
        if col not in df.columns:
            continue
        min_val, max_val = bounds
        raw = df[col]
        numeric = pd.to_numeric(raw, errors="coerce")
        missing_mask = _get_missing_mask(raw, custom_missing_markers)
        comparable_mask = ~missing_mask & numeric.notna()
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
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
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

        missing_a = _get_missing_mask(series_a, custom_missing_markers)
        missing_b = _get_missing_mask(series_b, custom_missing_markers)
        comparable_mask = ~missing_a & ~missing_b & cmp_a.notna() & cmp_b.notna()
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
    custom_missing_markers: Optional[set[str]] = None
) -> list[QualityIssue]:
    logger.info("Running Phase 4 data quality checks...")
    issues: list[QualityIssue] = []

    issues += check_missing_values(df, column_profiles, custom_missing_markers=custom_missing_markers)
    issues += check_whitespace_issues(df, column_profiles, custom_missing_markers=custom_missing_markers)
    issues += check_case_inconsistencies(df, column_profiles, custom_missing_markers=custom_missing_markers)
    issues += check_duplicate_rows(df)
    issues += check_potential_duplicates(df, type_results, id_columns=id_columns, custom_missing_markers=custom_missing_markers)
    issues += check_duplicate_ids(df, type_results, id_columns=id_columns, custom_missing_markers=custom_missing_markers)
    issues += check_invalid_emails(df, type_results, custom_missing_markers=custom_missing_markers)
    issues += check_invalid_dates(df, type_results, custom_missing_markers=custom_missing_markers)
    issues += check_invalid_numeric(df, type_results, custom_missing_markers=custom_missing_markers)
    issues += check_invalid_categories(df, allowed_categories=allowed_categories, custom_missing_markers=custom_missing_markers)
    issues += check_range_violations(df, column_ranges=column_ranges, custom_missing_markers=custom_missing_markers)
    issues += check_consistency(df, type_results, consistency_rules=consistency_rules, custom_missing_markers=custom_missing_markers)

    logger.info(f"Data quality checks complete: {len(issues)} issue(s) found")
    return issues
