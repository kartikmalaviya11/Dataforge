"""
Phase 3: Semantic Data-Type Detection

Detects analytical/semantic types from storage types and data patterns.
Distinguishes Storage Type (pandas dtype) from Semantic Type (analytical meaning).
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np
import re
from loguru import logger


# ─── Semantic Type Definitions ──────────────────────────────────────

SEMANTIC_TYPES = [
    "Integer",
    "Decimal",
    "Boolean",
    "Date",
    "DateTime",
    "Email",
    "Phone",
    "ID",
    "Currency",
    "Percentage",
    "URL",
    "Category",
    "String",  # fallback
]


def is_integer_semantic(series: pd.Series) -> bool:
    """Check if series represents integer values (no decimals)."""
    numeric = pd.to_numeric(series, errors='coerce')
    valid = numeric.dropna()
    if valid.empty:
        return False
    # All values must be whole numbers
    return bool((valid % 1 == 0).all())


def is_boolean_semantic(series: pd.Series) -> bool:
    """Check if series represents boolean values."""
    unique_vals = set(str(v).strip().lower() for v in series.dropna().unique())
    if not unique_vals:
        return False
    # Common boolean representations
    boolean_sets = [
        {"true", "false"},
        {"yes", "no"},
        {"y", "n"},
        {"1", "0"},
        {"t", "f"},
    ]
    return any(unique_vals.issubset(bs) for bs in boolean_sets)


def is_date_semantic(series: pd.Series) -> bool:
    """Check if series represents dates (no time component)."""
    # Skip numeric data - integers/floats can be parsed as timestamps
    if pd.api.types.is_numeric_dtype(series):
        return False
    parsed = pd.to_datetime(series, errors='coerce')
    valid = parsed.dropna()
    if valid.empty:
        return False
    # Check if all times are midnight (00:00:00)
    return bool((valid.dt.time == pd.Timestamp('00:00:00').time()).all())


def is_datetime_semantic(series: pd.Series) -> bool:
    """Check if series represents datetimes (has time component)."""
    # Skip numeric data - integers/floats can be parsed as timestamps
    if pd.api.types.is_numeric_dtype(series):
        return False
    parsed = pd.to_datetime(series, errors='coerce')
    valid = parsed.dropna()
    if valid.empty:
        return False
    # At least one non-midnight time
    return bool(not (valid.dt.time == pd.Timestamp('00:00:00').time()).all())


def is_email_semantic(series: pd.Series) -> bool:
    """Check if series contains email addresses."""
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False
    matches = non_null.apply(lambda x: bool(email_pattern.match(x.strip())))
    # At least 80% match rate for emails
    return bool(matches.mean() >= 0.8)


def is_phone_semantic(series: pd.Series) -> bool:
    """Check if series contains phone numbers."""
    # Common phone patterns
    phone_pattern = re.compile(r'^(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$')
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False
    matches = non_null.apply(lambda x: bool(phone_pattern.match(x.strip())))
    return bool(matches.mean() >= 0.7)


def is_url_semantic(series: pd.Series) -> bool:
    """Check if series contains URLs."""
    url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False
    matches = non_null.apply(lambda x: bool(url_pattern.match(x.strip())))
    return bool(matches.mean() >= 0.8)


def is_currency_semantic(series: pd.Series) -> bool:
    """Check if series represents currency values."""
    currency_pattern = re.compile(r'^[$€£¥]?\s?\d{1,3}([,.]\d{3})*([.,]\d{2})?$')
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False
    matches = non_null.apply(lambda x: bool(currency_pattern.match(x.strip())))
    # Also check if numeric with 2 decimal places predominantly
    if bool(matches.mean() >= 0.7):
        return True
    # Check numeric with 2 decimal places
    numeric = pd.to_numeric(series, errors='coerce')
    valid = numeric.dropna()
    if valid.empty:
        return False
    # Most values have exactly 2 decimal places
    decimal_check = (valid * 100) % 1 == 0
    return bool(decimal_check.mean() >= 0.8)


def is_percentage_semantic(series: pd.Series) -> bool:
    """Check if series represents percentages."""
    pct_pattern = re.compile(r'^\d+(\.\d+)?%?$')
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False
    # Check for % symbol
    has_pct = non_null.str.contains('%').any()
    if has_pct:
        matches = non_null.apply(lambda x: bool(pct_pattern.match(x.strip().rstrip('%'))))
        if bool(matches.mean() >= 0.8):
            return True
    # Check numeric between 0-100
    numeric = pd.to_numeric(non_null.str.rstrip('%'), errors='coerce')
    valid = numeric.dropna()
    if valid.empty:
        return False
    return bool(((valid >= 0) & (valid <= 100)).mean() >= 0.9)


def _tokenize_column_name(column_name: str) -> list[str]:
    """
    Split a column name into lowercase word tokens.

    Splits on any non-alphanumeric separator (underscore, space, hyphen, etc.)
    and on camelCase boundaries, so "customer_id", "CustomerID", and
    "customer id" all tokenize to ["customer", "id"]. This is what lets
    keyword matching check for whole-word matches instead of raw substrings.
    """
    spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', column_name)
    tokens = re.split(r'[^a-zA-Z0-9]+', spaced)
    return [t.lower() for t in tokens if t]


def is_id_semantic(series: pd.Series, column_name: str) -> bool:
    """
    Check if series represents an ID column.

    Evidence: the column name contains a whole-word ID-style token
    (id, key, pk, fk, code, number, no, num) AND the values are
    high-cardinality (mostly unique).

    Uses whole-word token matching rather than raw substring matching,
    so names like "avoid", "valid", "paid", or "ignore_flag" are not
    falsely flagged just because they contain "id" or "no" as a substring.
    """
    id_keywords = {'id', 'key', 'pk', 'fk', 'code', 'number', 'no', 'num'}
    tokens = _tokenize_column_name(column_name)
    if any(tok in id_keywords for tok in tokens):
        non_null = series.dropna()
        if non_null.empty:
            return False
        unique_ratio = non_null.nunique() / len(non_null)
        if unique_ratio > 0.95:
            return True
    return False


def is_category_semantic(series: pd.Series) -> bool:
    """
    Check if series represents a categorical variable.

    Evidence used (in order):
      1. Uniqueness ratio, not a bare absolute count, is the primary signal.
         A column where every value is unique (ratio == 1.0) is never
         categorical, regardless of how few rows there are -- this is what
         previously caused small samples of fully-unique free text (e.g.
         5 unique names across 5 rows) to be misclassified as Category.
      2. Small absolute cardinality (<=20 distinct values) counts as
         categorical only when there is *meaningful* repetition in the
         data (at most 80% of values are unique) -- this distinguishes a
         real category column from a column that merely happens to have
         a handful of coincidentally-unique values in a small sample.
      3. For columns with a larger absolute number of distinct values, a
         strict low-ratio fallback still catches genuinely categorical
         columns, e.g. 25 distinct country codes spread across 500,000 rows.
    """
    non_null = series.dropna()
    total_count = len(non_null)
    if total_count == 0:
        return False

    unique_count = non_null.nunique()
    unique_ratio = unique_count / total_count

    # Fully (or effectively fully) unique values are never categorical.
    if unique_ratio >= 1.0:
        return False

    # Small absolute cardinality with meaningful repetition.
    if unique_count <= 20 and unique_ratio <= 0.8:
        return True

    # Larger cardinality, but distinct values are rare relative to the
    # dataset size (e.g. category/country codes in a large table).
    if unique_ratio < 0.05:
        return True

    return False


def detect_semantic_type(series: pd.Series, column_name: str, storage_type: str) -> tuple[str, float, str]:
    """
    Detect semantic type for a single column.

    Returns:
        tuple: (detected_type, confidence, evidence)
    """
    non_null = series.dropna()
    if non_null.empty:
        return "Unknown", 0.0, "All values are null"

        # Try specific detectors in order of specificity
    # Integer MUST come before Percentage AND Currency to avoid false positives on whole numbers
    detectors = [
        ("Email", is_email_semantic, "email pattern match"),
        ("URL", is_url_semantic, "URL pattern match"),
        ("Phone", is_phone_semantic, "phone pattern match"),
        ("Boolean", is_boolean_semantic, "boolean value set"),
        ("DateTime", is_datetime_semantic, "datetime with time component"),
        ("Date", is_date_semantic, "date-only values"),
        ("Integer", is_integer_semantic, "whole numbers only"),
        ("Percentage", is_percentage_semantic, "% symbol or 0-100 numeric"),
        ("ID", lambda s: is_id_semantic(s, column_name), "high-cardinality key-like column"),
        ("Currency", is_currency_semantic, "currency pattern or 2-decimal numeric"),
        ("Category", is_category_semantic, "low cardinality"),
        ("Decimal", lambda s: pd.to_numeric(s, errors='coerce').notna().mean() > 0.8, "mostly numeric with decimals"),
        ("String", lambda s: True, "fallback for any string data"),
    ]

    for sem_type, detector, evidence in detectors:
        try:
            if detector(non_null):
                confidence = 0.95  # High confidence for positive pattern matches
                # Adjust confidence for fallback types
                if sem_type in ("Decimal", "String", "Category", "ID"):
                    confidence = 0.7
                return sem_type, confidence, evidence
        except Exception:
            continue

    return "String", 0.5, "fallback"


# ─── Result Dataclass ───────────────────────────────────────────────

@dataclass
class TypeDetectionResult:
    column_name: str
    storage_type: str
    detected_type: str
    confidence: float
    evidence: str
    status: str  # "OK", "MISMATCH", "AMBIGUOUS"
    recommended_action: str


def determine_status_and_action(
    storage_type: str,
    detected_type: str,
    confidence: float
) -> tuple[str, str]:
    """Determine status and recommended action based on storage vs detected type."""
    # Normalize storage type
    storage_lower = storage_type.lower()
    # Type compatibility matrix
    compatible = {
        "Integer": ["int", "int64", "int32", "int16", "int8", "uint"],
        "Decimal": ["float", "float64", "float32", "decimal"],
        "Boolean": ["bool", "boolean"],
        "Date": ["datetime", "datetime64", "date"],
        "DateTime": ["datetime", "datetime64"],
        "String": ["object", "string", "str"],
        "Category": ["object", "string", "str", "category"],
        "ID": ["object", "string", "str", "int", "int64"],
        "Email": [],
        "Phone": [],
        "URL": [],
        "Currency": ["float", "float64"],
        "Percentage": ["float", "float64"],
    }

    compatible_storages = compatible.get(detected_type, [])
    is_compatible = any(cs in storage_lower for cs in compatible_storages)

    if confidence < 0.7:
        return "AMBIGUOUS", "Manual review required - low confidence detection"
    elif not is_compatible:
        return "MISMATCH", f"Convert from {storage_type} to {detected_type}"
    else:
        return "OK", "No action needed"


def detect_semantic_types(
    df: pd.DataFrame,
    column_profiles: list
) -> list[TypeDetectionResult]:
    """
    Detect semantic types for all columns in a DataFrame.

    Args:
        df: Input DataFrame
        column_profiles: List of ColumnProfile from profiler.py

    Returns:
        List of TypeDetectionResult
    """
    logger.info(f"Detecting semantic types for {len(df.columns)} columns...")
    results = []

    for profile in column_profiles:
        series = df[profile.name]
        detected_type, confidence, evidence = detect_semantic_type(
            series, profile.name, profile.storage_type
        )
        status, action = determine_status_and_action(
            profile.storage_type, detected_type, confidence
        )

        results.append(TypeDetectionResult(
            column_name=profile.name,
            storage_type=profile.storage_type,
            detected_type=detected_type,
            confidence=confidence,
            evidence=evidence,
            status=status,
            recommended_action=action,
        ))

    logger.info("Semantic type detection complete")
    return results