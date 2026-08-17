"""
Phase 5: Business Rule Engine

Configurable, explainable business-rule validation, driven entirely by
external YAML configuration rather than hard-coded Python.

Design principles (see project master prompt, sections 14 / 27 / 38):
  - Rules are declared in config/rules.yaml (or an equivalent list of
    dicts) and actually control behavior -- nothing here is a dataset-
    specific hack. Swap the YAML and the same engine logic applies to a
    different dataset unchanged.
  - Business rules are kept structurally separate from Phase 4's generic
    data-quality checks: Phase 4 runs automatically from what ingestion/
    profiling/type-detection already determined; Phase 5 rules only run
    when a rule is explicitly configured for a column. A negative Profit
    value, for example, is never flagged unless a `range` rule for the
    Profit column explicitly forbids it.
  - Every violation is a single, explainable record (see RuleViolation)
    that Phase 6 (Issue Management) can consume directly, alongside
    Phase 4's QualityIssue records.
  - Invalid rule configuration fails loudly and specifically (RuleConfigError)
    rather than silently doing the wrong thing.

Null handling (documented per rule type -- see also each function's
docstring below):
  - required_column: not applicable at the cell level; this rule checks
    whether the column exists at all.
  - range: null cells are skipped. Missingness itself is Phase 4's concern.
  - allowed_values: null cells are skipped by default. Set
    `treat_null_as_invalid: true` on the rule to flag nulls too.
  - uniqueness: null values are excluded from duplicate comparison by
    default -- multiple nulls in the same column are not considered
    duplicates of each other.
  - comparison: rows where either side can't be parsed/compared are
    skipped -- a relationship can't be judged true or false without both
    values.
  - referential_integrity: null child values are skipped by default (a
    missing foreign key is "no reference," not automatically invalid).
    Set `treat_null_as_invalid: true` to flag nulls too.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union
import operator

import numpy as np
import pandas as pd
import yaml
from loguru import logger


# ─── Configuration Constants ─────────────────────────────────────────

SUPPORTED_RULE_TYPES = {
    "required_column",
    "range",
    "allowed_values",
    "uniqueness",
    "comparison",
    "referential_integrity",
}

VALID_SEVERITIES = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}

SUPPORTED_OPERATORS = {
    "<=": operator.le,
    "<": operator.lt,
    ">=": operator.ge,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}

_REQUIRED_FIELDS_BY_TYPE = {
    "required_column": ["column"],
    "range": ["column"],
    "allowed_values": ["column", "values"],
    "uniqueness": ["column"],
    "comparison": ["column_a", "column_b", "operator"],
    "referential_integrity": ["child_column", "parent_dataset", "parent_column"],
}


class RuleConfigError(ValueError):
    """Raised when a rule configuration is invalid or malformed."""


# ─── Result Dataclass ───────────────────────────────────────────────

@dataclass
class RuleViolation:
    """
    A single, explainable business-rule violation.

    Mirrors Phase 4's QualityIssue shape closely (row_index, column,
    actual_value, expected_condition) but additionally carries `severity`,
    since business rules declare their own severity in configuration --
    unlike Phase 4's generic checks, which leave severity to Phase 6.
    """
    rule_name: str
    rule_type: str
    row_index: Optional[Any] = None
    column: Optional[str] = None
    actual_value: Optional[Any] = None
    expected_condition: str = ""
    severity: str = "MEDIUM"
    message: str = ""


def _to_native(value: Any) -> Any:
    """Convert numpy/pandas scalar types to plain Python types for clean export.

    Duplicated intentionally from quality_engine.py's private helper of the
    same name, rather than importing it: that helper is module-private
    (leading underscore) in Phase 4, and this phase was scoped to avoid
    touching src/quality_engine.py. The function is a few lines; keeping
    Phase 4 and Phase 5 independently self-contained was judged the safer
    tradeoff over reaching into another module's private internals.
    """
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


# ─── Configuration Loading & Validation ──────────────────────────────

def load_rules(path: Union[str, Path]) -> list[dict]:
    """
    Load and validate business rules from a YAML file.

    The YAML file is expected to have a top-level `rules:` list, matching
    config/rules.yaml. Raises RuleConfigError with a clear message if the
    file is missing, malformed, or contains invalid rule definitions.
    """
    path = Path(path)
    if not path.exists():
        raise RuleConfigError(f"Rule configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise RuleConfigError(f"Failed to parse YAML rule configuration '{path}': {e}") from e

    data = data or {}
    if not isinstance(data, dict):
        raise RuleConfigError(
            f"Rule configuration '{path}' must be a mapping with a top-level 'rules:' list."
        )

    rules = data.get("rules", [])
    validate_rule_config(rules)
    return rules


def validate_rule_config(rules: list[dict]) -> None:
    """
    Validate a list of rule definitions, raising RuleConfigError with a
    clear, actionable message on the first problem found.

    Checks performed:
      - overall shape (must be a list of dicts)
      - each rule has a valid, unique 'name'
      - each rule has a 'type' that is one of SUPPORTED_RULE_TYPES
      - each rule has all fields required for its type
      - type-specific validation (range bounds, allowed operators,
        non-empty allowed-values list, valid severity)
    """
    if not isinstance(rules, list):
        raise RuleConfigError("Rule configuration must be a list of rule definitions.")

    seen_names: set[str] = set()

    for position, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise RuleConfigError(f"Rule at position {position} must be a mapping (dict), got {type(rule).__name__}.")

        name = rule.get("name")
        if not name or not isinstance(name, str):
            raise RuleConfigError(f"Rule at position {position} is missing a valid non-empty 'name'.")
        if name in seen_names:
            raise RuleConfigError(f"Duplicate rule name: '{name}'. Rule names must be unique.")
        seen_names.add(name)

        rule_type = rule.get("type")
        if not rule_type:
            raise RuleConfigError(f"Rule '{name}' is missing a 'type'.")
        if rule_type not in SUPPORTED_RULE_TYPES:
            raise RuleConfigError(
                f"Rule '{name}' has unsupported type '{rule_type}'. "
                f"Supported types: {sorted(SUPPORTED_RULE_TYPES)}"
            )

        for field in _REQUIRED_FIELDS_BY_TYPE[rule_type]:
            if field not in rule or rule[field] in (None, ""):
                raise RuleConfigError(f"Rule '{name}' ({rule_type}) is missing required field '{field}'.")

        if rule_type == "range":
            min_v = rule.get("min")
            max_v = rule.get("max")
            if min_v is None and max_v is None:
                raise RuleConfigError(f"Rule '{name}' (range) must specify at least one of 'min' or 'max'.")
            for label, v in (("min", min_v), ("max", max_v)):
                if v is not None and not isinstance(v, (int, float)):
                    raise RuleConfigError(
                        f"Rule '{name}' (range) field '{label}' must be numeric, got {type(v).__name__}."
                    )
            if min_v is not None and max_v is not None and min_v > max_v:
                raise RuleConfigError(f"Rule '{name}' (range) has min ({min_v}) greater than max ({max_v}).")

        if rule_type == "allowed_values":
            values = rule.get("values")
            if not isinstance(values, list) or len(values) == 0:
                raise RuleConfigError(f"Rule '{name}' (allowed_values) must specify a non-empty 'values' list.")

        if rule_type == "comparison":
            op_symbol = rule.get("operator")
            if op_symbol not in SUPPORTED_OPERATORS:
                raise RuleConfigError(
                    f"Rule '{name}' (comparison) has unsupported operator '{op_symbol}'. "
                    f"Supported operators: {sorted(SUPPORTED_OPERATORS)}"
                )
            value_type = rule.get("value_type")
            if value_type is not None and value_type not in ("date", "numeric"):
                raise RuleConfigError(
                    f"Rule '{name}' (comparison) has invalid 'value_type' "
                    f"'{value_type}'. Must be 'date' or 'numeric' if specified."
                )

        severity = rule.get("severity", "MEDIUM")
        if severity not in VALID_SEVERITIES:
            raise RuleConfigError(
                f"Rule '{name}' has invalid severity '{severity}'. "
                f"Valid severities: {sorted(VALID_SEVERITIES)}"
            )


# ─── Individual Rule Checks ──────────────────────────────────────────

def apply_required_column(df: pd.DataFrame, rule: dict) -> list[RuleViolation]:
    """
    Check that a column exists in the dataset.

    Null handling: not applicable -- this checks column existence, not
    cell values. Produces a single dataset-level violation (row_index=None)
    if the column is absent.
    """
    col = rule["column"]
    severity = rule.get("severity", "MEDIUM")
    if col in df.columns:
        return []
    return [RuleViolation(
        rule_name=rule["name"],
        rule_type="required_column",
        row_index=None,
        column=col,
        actual_value=None,
        expected_condition=f"Column '{col}' must be present in the dataset",
        severity=severity,
        message=f"Required column '{col}' is missing from the dataset.",
    )]


def apply_range(df: pd.DataFrame, rule: dict) -> list[RuleViolation]:
    """
    Check that numeric values in a column fall within [min, max] (inclusive
    on both bounds where configured).

    Null handling: null cells are skipped. Missing-value detection is
    Phase 4's job; this rule only judges values that are actually present.
    """
    col = rule["column"]
    if col not in df.columns:
        logger.warning(f"Rule '{rule['name']}' (range) references missing column '{col}'; skipping.")
        return []

    min_v = rule.get("min")
    max_v = rule.get("max")
    severity = rule.get("severity", "MEDIUM")

    raw = df[col]
    numeric = pd.to_numeric(raw, errors="coerce")
    comparable_mask = raw.notna() & numeric.notna()
    if not comparable_mask.any():
        return []

    below = pd.Series(False, index=df.index)
    above = pd.Series(False, index=df.index)
    if min_v is not None:
        below = numeric < min_v
    if max_v is not None:
        above = numeric > max_v
    violation_mask = comparable_mask & (below | above)
    if not violation_mask.any():
        return []

    condition_parts = []
    if min_v is not None:
        condition_parts.append(f">= {min_v}")
    if max_v is not None:
        condition_parts.append(f"<= {max_v}")
    expected = f"{col} " + " and ".join(condition_parts)

    violations = []
    for idx in df.index[violation_mask]:
        violations.append(RuleViolation(
            rule_name=rule["name"],
            rule_type="range",
            row_index=_to_native(idx),
            column=col,
            actual_value=_to_native(raw.loc[idx]),
            expected_condition=expected,
            severity=severity,
            message=f"Value in '{col}' is outside the allowed range ({expected}).",
        ))
    return violations


def apply_allowed_values(df: pd.DataFrame, rule: dict) -> list[RuleViolation]:
    """
    Check that values in a column are within an explicit allowed set.

    Null handling: null cells are skipped by default. Set
    `treat_null_as_invalid: true` on the rule to flag nulls too.
    """
    col = rule["column"]
    if col not in df.columns:
        logger.warning(f"Rule '{rule['name']}' (allowed_values) references missing column '{col}'; skipping.")
        return []

    allowed = set(rule["values"])
    treat_null_as_invalid = bool(rule.get("treat_null_as_invalid", False))
    severity = rule.get("severity", "MEDIUM")
    series = df[col]

    eligible_mask = pd.Series(True, index=df.index) if treat_null_as_invalid else series.notna()
    invalid_mask = eligible_mask & ~series.isin(allowed)
    if not invalid_mask.any():
        return []

    expected = f"Value should be one of: {sorted(str(v) for v in allowed)}"
    violations = []
    for idx in df.index[invalid_mask]:
        violations.append(RuleViolation(
            rule_name=rule["name"],
            rule_type="allowed_values",
            row_index=_to_native(idx),
            column=col,
            actual_value=_to_native(series.loc[idx]),
            expected_condition=expected,
            severity=severity,
            message=f"Value in '{col}' is not an allowed value.",
        ))
    return violations


def apply_uniqueness(df: pd.DataFrame, rule: dict) -> list[RuleViolation]:
    """
    Check that values in a column do not repeat.

    Null handling: null values are excluded from duplicate comparison --
    multiple nulls in the same column are not considered duplicates of
    each other. All rows sharing a duplicated non-null value are flagged
    (not just the later copies), since for a uniqueness constraint there
    is no way to tell which copy is "the correct one."
    """
    col = rule["column"]
    if col not in df.columns:
        logger.warning(f"Rule '{rule['name']}' (uniqueness) references missing column '{col}'; skipping.")
        return []

    severity = rule.get("severity", "MEDIUM")
    series = df[col]
    non_null_mask = series.notna()
    if not non_null_mask.any():
        return []

    dup_mask = non_null_mask & series.duplicated(keep=False)
    if not dup_mask.any():
        return []

    violations = []
    for idx in df.index[dup_mask]:
        violations.append(RuleViolation(
            rule_name=rule["name"],
            rule_type="uniqueness",
            row_index=_to_native(idx),
            column=col,
            actual_value=_to_native(series.loc[idx]),
            expected_condition=f"Values in '{col}' should be unique",
            severity=severity,
            message=f"The value in '{col}' is shared by more than one row.",
        ))
    return violations


def apply_comparison(df: pd.DataFrame, rule: dict) -> list[RuleViolation]:
    """
    Check that a relationship (<=, <, >=, >, ==, !=) holds between two
    columns, e.g. order_date <= delivery_date.

    Comparison mode (datetime vs numeric) is chosen via the optional
    `value_type: date|numeric` field. If not specified, the engine tries
    both interpretations and auto-selects whichever yields more comparable
    rows (a majority-vote heuristic, more robust than assuming datetime
    just because one row happens to parse as a date).

    Null handling: rows where either side can't be parsed under the
    selected interpretation are skipped -- a relationship can't be judged
    true or false without both values.
    """
    col_a = rule["column_a"]
    col_b = rule["column_b"]
    op_symbol = rule["operator"]
    severity = rule.get("severity", "MEDIUM")
    value_type = rule.get("value_type")

    if col_a not in df.columns:
        logger.warning(f"Rule '{rule['name']}' (comparison) references missing column '{col_a}'; skipping.")
        return []
    if col_b not in df.columns:
        logger.warning(f"Rule '{rule['name']}' (comparison) references missing column '{col_b}'; skipping.")
        return []

    op_func = SUPPORTED_OPERATORS[op_symbol]
    series_a = df[col_a]
    series_b = df[col_b]

    a_dt = pd.to_datetime(series_a, errors="coerce")
    b_dt = pd.to_datetime(series_b, errors="coerce")
    dt_comparable = a_dt.notna() & b_dt.notna()

    a_num = pd.to_numeric(series_a, errors="coerce")
    b_num = pd.to_numeric(series_b, errors="coerce")
    num_comparable = a_num.notna() & b_num.notna()

    if value_type == "date":
        cmp_a, cmp_b, comparable_mask = a_dt, b_dt, dt_comparable
    elif value_type == "numeric":
        cmp_a, cmp_b, comparable_mask = a_num, b_num, num_comparable
    elif dt_comparable.sum() >= num_comparable.sum():
        cmp_a, cmp_b, comparable_mask = a_dt, b_dt, dt_comparable
    else:
        cmp_a, cmp_b, comparable_mask = a_num, b_num, num_comparable

    if not comparable_mask.any():
        return []

    violation_mask = comparable_mask & ~op_func(cmp_a, cmp_b)
    if not violation_mask.any():
        return []

    expected = f"{col_a} {op_symbol} {col_b}"
    violations = []
    for idx in df.index[violation_mask]:
        violations.append(RuleViolation(
            rule_name=rule["name"],
            rule_type="comparison",
            row_index=_to_native(idx),
            column=f"{col_a} / {col_b}",
            actual_value=f"{col_a}={_to_native(series_a.loc[idx])!r}, {col_b}={_to_native(series_b.loc[idx])!r}",
            expected_condition=expected,
            severity=severity,
            message=f"Row violates comparison rule: {expected}.",
        ))
    return violations


def apply_referential_integrity(
    df: pd.DataFrame,
    rule: dict,
    parent_datasets: dict[str, pd.DataFrame],
) -> list[RuleViolation]:
    """
    Check that every (non-null) value in a child column exists somewhere
    in a parent dataset's column.

    The parent dataset is not loaded by this module -- it must be supplied
    by the caller via `parent_datasets` (a name -> DataFrame mapping) when
    running the engine. This avoids building any database dependency into
    Phase 5.

    Null handling: null child values are skipped by default (a missing
    foreign key is treated as "no reference," not automatically invalid).
    Set `treat_null_as_invalid: true` on the rule to flag nulls too.

    Missing columns/datasets: if the child column, the named parent
    dataset, or the parent column is not available, the rule is skipped
    gracefully (logged as a warning), not treated as a violation or a crash.
    """
    child_col = rule["child_column"]
    parent_name = rule["parent_dataset"]
    parent_col = rule["parent_column"]
    severity = rule.get("severity", "MEDIUM")
    treat_null_as_invalid = bool(rule.get("treat_null_as_invalid", False))

    if child_col not in df.columns:
        logger.warning(
            f"Rule '{rule['name']}' (referential_integrity) references missing "
            f"child column '{child_col}'; skipping."
        )
        return []

    parent_df = parent_datasets.get(parent_name)
    if parent_df is None:
        logger.warning(
            f"Rule '{rule['name']}' (referential_integrity) references parent dataset "
            f"'{parent_name}', which was not supplied to RuleEngine.run(); skipping."
        )
        return []

    if parent_col not in parent_df.columns:
        logger.warning(
            f"Rule '{rule['name']}' (referential_integrity) references missing parent "
            f"column '{parent_col}' in dataset '{parent_name}'; skipping."
        )
        return []

    child_series = df[child_col]
    parent_values = set(parent_df[parent_col].dropna())

    eligible_mask = pd.Series(True, index=df.index) if treat_null_as_invalid else child_series.notna()
    invalid_mask = eligible_mask & ~child_series.isin(parent_values)
    if not invalid_mask.any():
        return []

    expected = f"'{child_col}' must exist in {parent_name}.{parent_col}"
    violations = []
    for idx in df.index[invalid_mask]:
        violations.append(RuleViolation(
            rule_name=rule["name"],
            rule_type="referential_integrity",
            row_index=_to_native(idx),
            column=child_col,
            actual_value=_to_native(child_series.loc[idx]),
            expected_condition=expected,
            severity=severity,
            message=f"Value in '{child_col}' has no matching record in {parent_name}.{parent_col}.",
        ))
    return violations


# ─── Rule Engine ──────────────────────────────────────────────────────

class RuleEngine:
    """
    Loads a list of validated business-rule definitions and applies them
    to a DataFrame, producing a flat list of RuleViolation records.

    Rules are strictly opt-in and dataset-configured (via YAML or an
    equivalent list of dicts) -- nothing in this engine is hard-coded per
    dataset, and nothing is flagged unless a rule explicitly says so.

    Configuration is validated once, at construction time, so a malformed
    rule set fails fast with a clear RuleConfigError before any data is
    touched.
    """

    def __init__(self, rules: list[dict]):
        validate_rule_config(rules)
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "RuleEngine":
        """Convenience constructor: load and validate rules directly from a YAML file."""
        return cls(load_rules(path))

    def run(
        self,
        df: pd.DataFrame,
        parent_datasets: Optional[dict[str, pd.DataFrame]] = None,
    ) -> list[RuleViolation]:
        """
        Apply every configured rule to `df` and return a combined, flat
        list of RuleViolation records.

        `parent_datasets` is an optional name -> DataFrame mapping used
        only by `referential_integrity` rules; other rule types ignore it.
        """
        parent_datasets = parent_datasets or {}
        violations: list[RuleViolation] = []

        for rule in self.rules:
            rule_type = rule["type"]
            if rule_type == "required_column":
                violations.extend(apply_required_column(df, rule))
            elif rule_type == "range":
                violations.extend(apply_range(df, rule))
            elif rule_type == "allowed_values":
                violations.extend(apply_allowed_values(df, rule))
            elif rule_type == "uniqueness":
                violations.extend(apply_uniqueness(df, rule))
            elif rule_type == "comparison":
                violations.extend(apply_comparison(df, rule))
            elif rule_type == "referential_integrity":
                violations.extend(apply_referential_integrity(df, rule, parent_datasets))
            else:
                # Unreachable in practice -- validate_rule_config already
                # enforces SUPPORTED_RULE_TYPES at construction time -- but
                # guarded defensively rather than letting a single bad rule
                # crash the entire run.
                logger.warning(f"Unknown rule type '{rule_type}' for rule '{rule['name']}'; skipping.")

        return violations


def run_business_rules(
    df: pd.DataFrame,
    rules: list[dict],
    parent_datasets: Optional[dict[str, pd.DataFrame]] = None,
) -> list[RuleViolation]:
    """
    Convenience function: validate and run a list of rule dicts against a
    DataFrame in one call, without needing to construct a RuleEngine
    explicitly. Equivalent to `RuleEngine(rules).run(df, parent_datasets)`.
    """
    engine = RuleEngine(rules)
    return engine.run(df, parent_datasets=parent_datasets)