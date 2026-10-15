from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict
import pandas as pd
import numpy as np

from .issue_manager import IssueClassification

class RepairError(ValueError):
    """Raised when a repair instruction is invalid or cannot be applied safely."""
    pass

@dataclass
class RepairInstruction:
    action: str
    classification: IssueClassification
    column: Optional[str] = None
    row_index: Optional[Any] = None
    expected_state: Optional[Any] = None
    proposed_value: Optional[Any] = None
    reason: str = ""
    approved: bool = False

@dataclass
class ChangeRecord:
    row_index: Optional[Any]
    column: Optional[str]
    old_value: Any
    new_value: Any
    action: str
    reason: str
    classification: str

@dataclass
class RepairResult:
    success: bool
    affected_rows: int
    change_records: List[ChangeRecord]
    errors: List[str]

class RepairEngine:
    """
    Deterministic Repair Engine (Phase 2).
    Executes approved repair operations against a working copy of a dataset.
    """

    def __init__(self):
        self._operations = {
            "trim_whitespace": self._trim_whitespace,
            "normalize_case": self._normalize_case,
            "remove_exact_duplicates": self._remove_exact_duplicates,
            "impute_nulls": self._impute_nulls,
            "drop_column": self._drop_column,
            "convert_obvious_numeric": self._convert_obvious_numeric,
            "normalize_obvious_date": self._normalize_obvious_date,
            "normalize_column_name_whitespace": self._normalize_column_name_whitespace,
            "normalize_number_format": self._excel_format_repair,
            "normalize_date_display_format": self._excel_format_repair,
            "normalize_fill": self._excel_format_repair,
            "normalize_font": self._excel_format_repair,
            "normalize_alignment": self._excel_format_repair
        }

    def apply(self, df: pd.DataFrame, instructions: List[RepairInstruction]) -> Tuple[pd.DataFrame, Dict[str, RepairResult]]:
        """
        Apply a list of repair instructions to a working copy of the dataframe.
        Original dataframe is not mutated.
        Returns a tuple of (repaired_df, results_dict).
        """
        repaired_df = df.copy(deep=True)
        results = {}

        for i, instruction in enumerate(instructions):
            result_key = f"instruction_{i}"
            try:
                # 1. Reject UNSAFE_TO_FIX
                if instruction.classification == IssueClassification.UNSAFE_TO_FIX:
                    raise RepairError("Refusing to apply UNSAFE_TO_FIX repair.")

                # 2. Reject REVIEW_REQUIRED if not approved
                if instruction.classification == IssueClassification.REVIEW_REQUIRED and not instruction.approved:
                    raise RepairError("Refusing to apply REVIEW_REQUIRED repair without explicit approval.")

                # 3. Reject unknown operations
                if instruction.action not in self._operations:
                    raise RepairError(f"Unsupported repair action: '{instruction.action}'")

                # Apply operation deterministically
                op_func = self._operations[instruction.action]
                repaired_df, result = op_func(repaired_df, instruction)
                results[result_key] = result

            except RepairError as e:
                results[result_key] = RepairResult(
                    success=False,
                    affected_rows=0,
                    change_records=[],
                    errors=[str(e)]
                )
            except Exception as e:
                # Catch unexpected pandas/system errors
                results[result_key] = RepairResult(
                    success=False,
                    affected_rows=0,
                    change_records=[],
                    errors=[f"Unexpected execution error: {str(e)}"]
                )

        return repaired_df, results

    def _trim_whitespace(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        if not instruction.column:
            raise RepairError("Target column missing from instruction.")
        if instruction.column not in df.columns:
            raise RepairError(f"Target column '{instruction.column}' not found.")

        col = instruction.column
        changes = []
        affected_rows = 0

        # Determine rows needing trim (string type & containing leading/trailing whitespace)
        mask = df[col].apply(lambda x: isinstance(x, str))
        needs_trim = mask & df[col].str.contains(r'^\s+|\s+$', regex=True, na=False)

        target_indices = [instruction.row_index] if instruction.row_index is not None else df[needs_trim].index
        for idx in target_indices:
            if idx not in df.index:
                continue
            old_val = df.at[idx, col]
            if isinstance(old_val, str):
                new_val = old_val.strip()
                if new_val != old_val:
                    changes.append(ChangeRecord(
                        row_index=idx,
                        column=col,
                        old_value=old_val,
                        new_value=new_val,
                        action=instruction.action,
                        reason=instruction.reason,
                        classification=instruction.classification.value
                    ))
                    df.at[idx, col] = new_val
                    affected_rows += 1

        return df, RepairResult(True, affected_rows, changes, [])


    def _normalize_case(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        if not instruction.column:
            raise RepairError("Target column missing from instruction.")
        if instruction.column not in df.columns:
            raise RepairError(f"Target column '{instruction.column}' not found.")

        col = instruction.column
        changes = []
        affected_rows = 0

        target_indices = [instruction.row_index] if instruction.row_index is not None else []
        for idx in target_indices:
            if idx in df.index:
                old_val = df.at[idx, col]
                new_val = instruction.proposed_value
                if old_val != new_val:
                    df.at[idx, col] = new_val
                    changes.append(ChangeRecord(
                        row_index=idx,
                        column=col,
                        old_value=old_val,
                        new_value=new_val,
                        action=instruction.action,
                        reason=instruction.reason,
                        classification=instruction.classification.value
                    ))
                    affected_rows += 1

        return df, RepairResult(
            success=True,
            affected_rows=affected_rows,
            change_records=changes,
            errors=[]
        )

    def _remove_exact_duplicates(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        duplicates = df.duplicated(keep='first')
        dup_indices = df[duplicates].index.tolist()

        if instruction.row_index is not None:
            if instruction.row_index in dup_indices:
                dup_indices = [instruction.row_index]
            else:
                dup_indices = []

        changes = []
        for idx in dup_indices:
            row_dict = df.loc[idx].to_dict()
            changes.append(ChangeRecord(
                row_index=idx,
                column=None,
                old_value=str(row_dict),
                new_value="Removed",
                action=instruction.action,
                reason=instruction.reason,
                classification=instruction.classification.value
            ))

        df = df.drop(index=dup_indices)

        return df, RepairResult(True, len(dup_indices), changes, [])

    def _convert_obvious_numeric(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        if not instruction.column:
            raise RepairError("Target column missing from instruction.")
        if instruction.column not in df.columns:
            raise RepairError(f"Target column '{instruction.column}' not found.")

        col = instruction.column
        col_lower = col.lower()

        # Protect identifiers: do not convert columns representing IDs, codes, or references
        identifier_keywords = ["id", "code", "reference", "ref", "guid", "uuid"]
        if any(kw in col_lower for kw in identifier_keywords):
            # Skip conversion entirely for identifier columns
            return df, RepairResult(True, 0, [], [])

        # Cast to object to allow mixed types during update
        df[col] = df[col].astype(object)

        changes = []
        affected_rows = 0

        forbidden_specials = {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}

        target_indices = [instruction.row_index] if instruction.row_index is not None else df.index
        for idx in target_indices:
            if idx not in df.index:
                continue
            old_val = df.at[idx, col]
            if isinstance(old_val, str):
                val_strip = old_val.strip()
                val_lower = val_strip.lower()

                # Reject special numeric values like nan, inf
                if val_lower in forbidden_specials:
                    continue

                # Extra safety: do not strip leading zeros (e.g. "00123") even if column isn't obviously an ID
                # If it has leading zeros and isn't a decimal like "0.5" or just "0"
                if val_strip.startswith("0") and len(val_strip) > 1 and not val_strip.startswith("0."):
                    continue
                if val_strip.startswith("-0") and len(val_strip) > 2 and not val_strip.startswith("-0."):
                    continue

                try:
                    new_val = float(val_strip)
                    if new_val.is_integer() and '.' not in val_strip:
                        new_val = int(new_val)

                    df.at[idx, col] = new_val
                    changes.append(ChangeRecord(
                        row_index=idx,
                        column=col,
                        old_value=old_val,
                        new_value=new_val,
                        action=instruction.action,
                        reason=instruction.reason,
                        classification=instruction.classification.value
                    ))
                    affected_rows += 1
                except (ValueError, TypeError):
                    pass # Not an obvious numeric, leave it untouched

        return df, RepairResult(True, affected_rows, changes, [])

    def _normalize_obvious_date(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        if not instruction.column:
            raise RepairError("Target column missing from instruction.")
        if instruction.column not in df.columns:
            raise RepairError(f"Target column '{instruction.column}' not found.")

        col = instruction.column
        # Cast to object to allow datetime injection
        df[col] = df[col].astype(object)

        changes = []
        affected_rows = 0

        unambiguous_formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d"
        ]

        target_indices = [instruction.row_index] if instruction.row_index is not None else df.index
        for idx in target_indices:
            if idx not in df.index:
                continue
            old_val = df.at[idx, col]
            if isinstance(old_val, str):
                new_val = None
                for fmt in unambiguous_formats:
                    try:
                        parsed = pd.to_datetime(old_val, format=fmt, exact=True)
                        if not pd.isna(parsed):
                            new_val = parsed
                            break
                    except (ValueError, TypeError):
                        continue

                if new_val is not None:
                    df.at[idx, col] = new_val
                    changes.append(ChangeRecord(
                        row_index=idx,
                        column=col,
                        old_value=old_val,
                        new_value=new_val,
                        action=instruction.action,
                        reason=instruction.reason,
                        classification=instruction.classification.value
                    ))
                    affected_rows += 1

        return df, RepairResult(True, affected_rows, changes, [])

    def _normalize_column_name_whitespace(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        changes = []
        affected_rows = 0
        new_cols = []

        for col in df.columns:
            if isinstance(col, str):
                new_col = col.strip()
                if new_col != col:
                    changes.append(ChangeRecord(
                        row_index=None,
                        column=col,
                        old_value=col,
                        new_value=new_col,
                        action=instruction.action,
                        reason=instruction.reason,
                        classification=instruction.classification.value
                    ))
                    affected_rows += 1
                    new_cols.append(new_col)
                else:
                    new_cols.append(col)
            else:
                new_cols.append(col)

        df.columns = new_cols
        return df, RepairResult(True, affected_rows, changes, [])

    def _excel_format_repair(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        # Excel formatting doesn't alter the DataFrame values,
        # but we record it so ExportService can apply it to the workbook
        changes = []
        # If the instruction contains a row_index, it's a specific cell
        if instruction.row_index is not None and instruction.column:
            changes.append(ChangeRecord(
                row_index=instruction.row_index,
                column=instruction.column,
                old_value="FORMATTING",
                new_value=instruction.proposed_value,
                action=instruction.action,
                reason=instruction.reason,
                classification=instruction.classification.value
            ))
            return df, RepairResult(True, 1, changes, [])

        return df, RepairResult(False, 0, [], ["Invalid instruction for excel_format_repair"])

    def _impute_nulls(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        if not instruction.column or instruction.column not in df.columns:
            raise RepairError(f"Target column '{instruction.column}' not found.")

        col = instruction.column
        strategy = instruction.proposed_value  # Dict like {"strategy": "mean"}
        if not isinstance(strategy, dict) or "strategy" not in strategy:
            raise RepairError("Invalid imputation strategy provided.")

        strat_type = strategy["strategy"]

        # Check if column is all nulls
        if df[col].isna().all():
            return df, RepairResult(False, 0, [], [f"Cannot impute column '{col}' because it is entirely null."])

        val_to_impute = None

        if strat_type == "mean":
            if not pd.api.types.is_numeric_dtype(df[col]):
                return df, RepairResult(False, 0, [], [f"Cannot apply 'mean' strategy to non-numeric column '{col}'."])
            val_to_impute = df[col].mean()
        elif strat_type == "median":
            if not pd.api.types.is_numeric_dtype(df[col]):
                return df, RepairResult(False, 0, [], [f"Cannot apply 'median' strategy to non-numeric column '{col}'."])
            val_to_impute = df[col].median()
        elif strat_type == "mode":
            modes = df[col].mode()
            if modes.empty:
                return df, RepairResult(False, 0, [], [f"No valid mode found for column '{col}'."])
            val_to_impute = modes.iloc[0]
        elif strat_type == "constant":
            if "value" not in strategy:
                return df, RepairResult(False, 0, [], ["No constant value provided for imputation."])
            val_to_impute = strategy["value"]
            # Validate constant matches datatype (rough check)
            if pd.api.types.is_numeric_dtype(df[col]):
                try:
                    val_to_impute = float(val_to_impute)
                except ValueError:
                    return df, RepairResult(False, 0, [], [f"Constant '{val_to_impute}' is not valid for numeric column '{col}'."])
        else:
            return df, RepairResult(False, 0, [], [f"Unknown imputation strategy: {strat_type}"])

        # Apply imputation
        null_mask = df[col].isna()
        null_indices = df[null_mask].index.tolist()

        if not null_indices:
            return df, RepairResult(True, 0, [], [])

        # Important: convert column to object if we are imputing string constant into non-string
        # Let's let pandas handle upcasting, or we can force it.
        try:
            df.loc[null_mask, col] = val_to_impute
        except ValueError:
            # Type error during insertion, cast to object
            df[col] = df[col].astype(object)
            df.loc[null_mask, col] = val_to_impute

        changes = []
        for idx in null_indices:
            changes.append(ChangeRecord(
                row_index=idx,
                column=col,
                old_value=None,
                new_value=val_to_impute,
                action=instruction.action,
                reason=instruction.reason,
                classification=instruction.classification.value
            ))

        return df, RepairResult(True, len(null_indices), changes, [])

    def _drop_column(self, df: pd.DataFrame, instruction: RepairInstruction) -> Tuple[pd.DataFrame, RepairResult]:
        if not instruction.column or instruction.column not in df.columns:
            raise RepairError(f"Target column '{instruction.column}' not found.")

        if len(df.columns) <= 1:
            return df, RepairResult(False, 0, [], ["Cannot drop the last remaining column in the dataset."])

        col = instruction.column
        df = df.drop(columns=[col])

        changes = [ChangeRecord(
            row_index=None,
            column=col,
            old_value="Exists",
            new_value="Dropped",
            action=instruction.action,
            reason=instruction.reason,
            classification=instruction.classification.value
        )]

        return df, RepairResult(True, len(df), changes, [])

import re
from src.issue_manager import StandardizedIssue, IssueClassification
import uuid
import pandas as pd

def validate_custom_pattern(df: pd.DataFrame, col_name: str, pattern: str) -> tuple[bool, dict]:
    """Validates a column against a regex pattern."""
    if col_name not in df.columns:
        return False, {"error": f"Column '{col_name}' not found in dataset."}

    try:
        prog = re.compile(pattern)
    except re.error as e:
        return False, {"error": f"Invalid Regex Pattern: {e}"}

    if df.empty:
        return True, {"matches": 0, "non_matches": 0, "nulls": 0, "offenders": [], "issue": None, "offending_indices": []}

    series = df[col_name]
    null_mask = pd.isna(series)
    null_count = int(null_mask.sum())

    valid_mask = series.dropna().astype(str).apply(lambda x: bool(prog.match(x)))
    match_count = int(valid_mask.sum()) if not valid_mask.empty else 0
    non_match_count = int(len(series.dropna()) - match_count)

    offenders = []
    offending_indices = []
    issue = None

    if non_match_count > 0:
        offending_series = series.dropna()[~valid_mask]
        offenders = offending_series.tolist()
        offending_indices = offending_series.index.tolist()

        issue = StandardizedIssue(
            issue_id=f"PAT-{uuid.uuid4().hex[:6]}",
            source="PATTERN_VALIDATION",
            issue_type="CUSTOM_PATTERN",
            rule_or_check_name=pattern,
            row_index=None,
            column=col_name,
            actual_value=None,
            expected_condition=pattern,
            severity="warning",
            message=f"{non_match_count} rows did not match pattern {pattern}",
            recommendation="Review offending values and correct or drop them.",
            classification=IssueClassification.REVIEW_REQUIRED
        )
        # Manually attach affected_count if UI expects it (since it's not in the signature of some versions)
        issue.affected_count = non_match_count

    return True, {
        "matches": match_count,
        "non_matches": non_match_count,
        "nulls": null_count,
        "offenders": offenders,
        "offending_indices": offending_indices,
        "issue": issue
    }
