"""
Phase 1: Dataset Ingestion

Supports CSV and Excel (.xlsx) loading with error handling.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger


@dataclass
class DatasetProfile:
    """Basic dataset profile information."""
    file_path: Path
    file_format: str          # "csv" or "xlsx"
    row_count: int
    column_count: int
    column_names: list[str]
    storage_types: dict[str, str]  # column -> pandas dtype
    memory_usage_mb: float
    sample_size: Optional[int] = None


class IngestionError(Exception):
    """Raised when dataset ingestion fails."""
    pass


SUPPORTED_FORMATS = {
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
}


def detect_format(file_path: Path) -> str:
    """Detect file format from extension."""
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise IngestionError(
            f"Unsupported file format: {suffix}. Supported: {list(SUPPORTED_FORMATS.keys())}"
        )
    return SUPPORTED_FORMATS[suffix]


def load_dataset(
    file_path: Path | str,
    sample_size: Optional[int] = None,
    **pandas_kwargs
) -> tuple[pd.DataFrame, DatasetProfile]:
    """
    Load a CSV or Excel file into a pandas DataFrame.

    Args:
        file_path: Path to the data file
        sample_size: If set, read only this many rows (for large files)
        **pandas_kwargs: Additional arguments passed to pd.read_csv / pd.read_excel

    Returns:
        Tuple of (DataFrame, DatasetProfile)

    Raises:
        IngestionError: If file not found, empty, corrupted, or unsupported format
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise IngestionError(f"File not found: {file_path}")

    if file_path.stat().st_size == 0:
        raise IngestionError(f"File is empty: {file_path}")

    file_format = detect_format(file_path)
    logger.info(f"Loading {file_format.upper()} file: {file_path}")

    try:
        if file_format == "csv":
            # Try common encodings
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(
                        file_path,
                        nrows=sample_size,
                        encoding=encoding,
                        **pandas_kwargs
                    )
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise IngestionError("Could not decode CSV with common encodings")
        else:  # xlsx
            df = pd.read_excel(file_path, nrows=sample_size, **pandas_kwargs)
    except pd.errors.EmptyDataError:
        raise IngestionError("File contains no data")
    except pd.errors.ParserError as e:
        raise IngestionError(f"Failed to parse file: {e}")
    except Exception as e:
        raise IngestionError(f"Unexpected error loading file: {e}")

    if df.empty:
        raise IngestionError("Dataset has no rows after loading")

    # Build profile
    profile = DatasetProfile(
        file_path=file_path,
        file_format=file_format,
        row_count=len(df),
        column_count=len(df.columns),
        column_names=list(df.columns),
        storage_types={col: str(dtype) for col, dtype in df.dtypes.items()},
        memory_usage_mb=df.memory_usage(deep=True).sum() / 1024**2,
        sample_size=sample_size,
    )

    logger.info(f"Loaded {profile.row_count:,} rows × {profile.column_count} columns")
    return df, profile