"""
Phase 2: Dataset Profiling

Computes per-column statistics for data profiling.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class ColumnProfile:
    """Profile for a single column."""
    name: str
    storage_type: str
    total_rows: int
    non_null_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    unique_percentage: float
    sample_values: list[Any] = field(default_factory=list)
    
    # Numeric statistics (only for numeric columns)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    median_value: Optional[float] = None
    std_value: Optional[float] = None
    
    # Text statistics (only for object/string columns)
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    avg_length: Optional[float] = None
    
    # Date statistics (only for datetime-like columns)
    min_date: Optional[pd.Timestamp] = None
    max_date: Optional[pd.Timestamp] = None


def is_numeric_type(dtype: str) -> bool:
    """Check if pandas dtype is numeric."""
    dtype_lower = dtype.lower()
    return dtype_lower.startswith(('int', 'float', 'uint', 'complex'))


def is_datetime_type(dtype: str) -> bool:
    """Check if pandas dtype is datetime-like."""
    dtype_lower = dtype.lower()
    return dtype_lower.startswith(('datetime', 'datetimetz'))


def is_string_type(dtype: str) -> bool:
    """Check if pandas dtype is string/object."""
    dtype_lower = dtype.lower()
    return dtype_lower in ('object', 'string', 'str')


def profile_column(series: pd.Series) -> ColumnProfile:
    """Generate profile for a single column."""
    name = series.name
    storage_type = str(series.dtype)
    total_rows = len(series)
    non_null_count = int(series.notna().sum())
    null_count = total_rows - non_null_count
    null_percentage = (null_count / total_rows * 100) if total_rows > 0 else 0.0
    unique_count = int(series.nunique(dropna=True))
    unique_percentage = (unique_count / non_null_count * 100) if non_null_count > 0 else 0.0
    
    # Sample values (non-null, up to 5)
    sample_values = series.dropna().head(5).tolist()
    
    profile = ColumnProfile(
        name=name,
        storage_type=storage_type,
        total_rows=total_rows,
        non_null_count=non_null_count,
        null_count=null_count,
        null_percentage=null_percentage,
        unique_count=unique_count,
        unique_percentage=unique_percentage,
        sample_values=sample_values,
    )

    # Type-specific statistics
    if is_numeric_type(storage_type):
        numeric_series = pd.to_numeric(series, errors='coerce')
        valid = numeric_series.dropna()
        if not valid.empty:
            profile.min_value = float(valid.min())
            profile.max_value = float(valid.max())
            profile.mean_value = float(valid.mean())
            profile.median_value = float(valid.median())
            std_val = valid.std()
            profile.std_value = float(std_val) if not pd.isna(std_val) else 0.0
    
    elif is_string_type(storage_type):
        str_series = series.dropna().astype(str)
        if not str_series.empty:
            lengths = str_series.str.len()
            profile.min_length = int(lengths.min())
            profile.max_length = int(lengths.max())
            profile.avg_length = float(lengths.mean())
    
    elif is_datetime_type(storage_type):
        dt_series = pd.to_datetime(series, errors='coerce')
        valid = dt_series.dropna()
        if not valid.empty:
            profile.min_date = valid.min()
            profile.max_date = valid.max()

    return profile


def profile_dataset(df: pd.DataFrame) -> list[ColumnProfile]:
    """
    Profile all columns in a dataset.

    Args:
        df: The pandas DataFrame to profile

    Returns:
        List of ColumnProfile objects
    """
    if df.columns.has_duplicates:
        raise ValueError(f"Duplicate column names detected: {df.columns[df.columns.duplicated()].tolist()}")

    logger.info(f"Profiling {len(df.columns)} columns...")
    profiles = []
    for col in df.columns:
        profiles.append(profile_column(df[col]))
    logger.info("Profiling complete")
    return profiles