"""Tests for Phase 5: Business Rule Engine"""

import pytest
import pandas as pd

from src.rules import (
    RuleEngine,
    RuleViolation,
    RuleConfigError,
    load_rules,
    validate_rule_config,
    run_business_rules,
    apply_required_column,
    apply_range,
    apply_allowed_values,
    apply_uniqueness,
    apply_comparison,
    apply_referential_integrity,
)


# ─── Required Column ─────────────────────────────────────────────────

class TestRequiredColumn:
    def test_present_column_no_violation(self):
        df = pd.DataFrame({"customer_id": [1, 2, 3]})
        rule = {"name": "cid_required", "type": "required_column", "column": "customer_id", "severity": "HIGH"}
        violations = apply_required_column(df, rule)
        assert violations == []

    def test_missing_column_produces_dataset_level_violation(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        rule = {"name": "cid_required", "type": "required_column", "column": "customer_id", "severity": "HIGH"}
        violations = apply_required_column(df, rule)
        assert len(violations) == 1
        v = violations[0]
        assert v.rule_name == "cid_required"
        assert v.rule_type == "required_column"
        assert v.row_index is None
        assert v.column == "customer_id"
        assert v.severity == "HIGH"


# ─── Range ────────────────────────────────────────────────────────────

class TestRange:
    def test_valid_value_no_violation(self):
        df = pd.DataFrame({"age": [25, 40, 60]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        assert apply_range(df, rule) == []

    def test_below_minimum(self):
        df = pd.DataFrame({"age": [10, 40]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        violations = apply_range(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 0
        assert violations[0].actual_value == 10

    def test_above_maximum(self):
        df = pd.DataFrame({"age": [40, 150]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        violations = apply_range(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 1
        assert violations[0].actual_value == 150

    def test_exact_minimum_is_valid(self):
        df = pd.DataFrame({"age": [18]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        assert apply_range(df, rule) == []

    def test_exact_maximum_is_valid(self):
        df = pd.DataFrame({"age": [100]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        assert apply_range(df, rule) == []

    def test_null_value_is_skipped(self):
        df = pd.DataFrame({"age": [25, None, 150]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        violations = apply_range(df, rule)
        # Only row 2 (150) should be flagged; the null at row 1 is skipped.
        assert len(violations) == 1
        assert violations[0].row_index == 2

    def test_missing_column_skipped_gracefully(self):
        df = pd.DataFrame({"other": [1, 2]})
        rule = {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}
        assert apply_range(df, rule) == []

    def test_open_ended_min_only(self):
        df = pd.DataFrame({"quantity": [5, -1, 0]})
        rule = {"name": "valid_qty", "type": "range", "column": "quantity", "min": 0, "severity": "MEDIUM"}
        violations = apply_range(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 1

    def test_invalid_range_configuration_min_greater_than_max(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([
                {"name": "bad_range", "type": "range", "column": "age", "min": 100, "max": 18, "severity": "HIGH"}
            ])

    def test_invalid_range_configuration_no_bounds(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([
                {"name": "bad_range", "type": "range", "column": "age", "severity": "HIGH"}
            ])

    def test_invalid_range_configuration_non_numeric_bound(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([
                {"name": "bad_range", "type": "range", "column": "age", "min": "eighteen", "severity": "HIGH"}
            ])


# ─── Allowed Values ───────────────────────────────────────────────────

class TestAllowedValues:
    def test_valid_value_no_violation(self):
        df = pd.DataFrame({"status": ["active", "inactive"]})
        rule = {"name": "valid_status", "type": "allowed_values", "column": "status",
                "values": ["active", "inactive", "pending"], "severity": "MEDIUM"}
        assert apply_allowed_values(df, rule) == []

    def test_invalid_value(self):
        df = pd.DataFrame({"status": ["active", "bogus"]})
        rule = {"name": "valid_status", "type": "allowed_values", "column": "status",
                "values": ["active", "inactive", "pending"], "severity": "MEDIUM"}
        violations = apply_allowed_values(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 1
        assert violations[0].actual_value == "bogus"

    def test_null_skipped_by_default(self):
        df = pd.DataFrame({"status": ["active", None]})
        rule = {"name": "valid_status", "type": "allowed_values", "column": "status",
                "values": ["active", "inactive"], "severity": "MEDIUM"}
        assert apply_allowed_values(df, rule) == []

    def test_null_flagged_when_configured(self):
        df = pd.DataFrame({"status": ["active", None]})
        rule = {"name": "valid_status", "type": "allowed_values", "column": "status",
                "values": ["active", "inactive"], "severity": "MEDIUM", "treat_null_as_invalid": True}
        violations = apply_allowed_values(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 1
        assert violations[0].actual_value is None

    def test_empty_allowed_set_is_a_config_error(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([
                {"name": "valid_status", "type": "allowed_values", "column": "status", "values": [], "severity": "MEDIUM"}
            ])


# ─── Uniqueness ─────────────────────────────────────────────────────

class TestUniqueness:
    def test_all_unique_no_violation(self):
        df = pd.DataFrame({"customer_id": [1, 2, 3]})
        rule = {"name": "cid_unique", "type": "uniqueness", "column": "customer_id", "severity": "HIGH"}
        assert apply_uniqueness(df, rule) == []

    def test_duplicates_flagged(self):
        df = pd.DataFrame({"customer_id": [1, 2, 2, 3]})
        rule = {"name": "cid_unique", "type": "uniqueness", "column": "customer_id", "severity": "HIGH"}
        violations = apply_uniqueness(df, rule)
        # Both rows sharing value 2 are flagged.
        assert len(violations) == 2
        assert {v.row_index for v in violations} == {1, 2}

    def test_nulls_not_considered_duplicates_of_each_other(self):
        df = pd.DataFrame({"customer_id": [1, None, None, 3]})
        rule = {"name": "cid_unique", "type": "uniqueness", "column": "customer_id", "severity": "HIGH"}
        assert apply_uniqueness(df, rule) == []


# ─── Comparison ───────────────────────────────────────────────────────

class TestComparison:
    def test_valid_relationship_no_violation(self):
        df = pd.DataFrame({
            "order_date": ["2024-01-01", "2024-02-01"],
            "delivery_date": ["2024-01-05", "2024-02-10"],
        })
        rule = {"name": "order_before_delivery", "type": "comparison", "column_a": "order_date",
                "column_b": "delivery_date", "operator": "<=", "value_type": "date", "severity": "HIGH"}
        assert apply_comparison(df, rule) == []

    def test_invalid_relationship_flagged(self):
        df = pd.DataFrame({
            "order_date": ["2024-03-05"],
            "delivery_date": ["2024-03-01"],
        })
        rule = {"name": "order_before_delivery", "type": "comparison", "column_a": "order_date",
                "column_b": "delivery_date", "operator": "<=", "value_type": "date", "severity": "HIGH"}
        violations = apply_comparison(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 0

    def test_boundary_equality_satisfies_le(self):
        df = pd.DataFrame({"order_date": ["2024-01-01"], "delivery_date": ["2024-01-01"]})
        rule = {"name": "order_before_delivery", "type": "comparison", "column_a": "order_date",
                "column_b": "delivery_date", "operator": "<=", "value_type": "date", "severity": "HIGH"}
        assert apply_comparison(df, rule) == []

    def test_boundary_equality_violates_strict_lt(self):
        df = pd.DataFrame({"order_date": ["2024-01-01"], "delivery_date": ["2024-01-01"]})
        rule = {"name": "order_strictly_before_delivery", "type": "comparison", "column_a": "order_date",
                "column_b": "delivery_date", "operator": "<", "value_type": "date", "severity": "HIGH"}
        violations = apply_comparison(df, rule)
        assert len(violations) == 1

    def test_missing_values_skipped(self):
        df = pd.DataFrame({
            "order_date": ["2024-01-01", None],
            "delivery_date": ["2024-01-05", "2024-02-10"],
        })
        rule = {"name": "order_before_delivery", "type": "comparison", "column_a": "order_date",
                "column_b": "delivery_date", "operator": "<=", "value_type": "date", "severity": "HIGH"}
        # Row 1 has a null order_date -- can't be judged, must be skipped, not flagged.
        assert apply_comparison(df, rule) == []

    def test_numeric_comparison(self):
        df = pd.DataFrame({"min_price": [10, 50], "max_price": [20, 40]})
        rule = {"name": "min_le_max", "type": "comparison", "column_a": "min_price",
                "column_b": "max_price", "operator": "<=", "value_type": "numeric", "severity": "MEDIUM"}
        violations = apply_comparison(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 1

    def test_auto_detected_value_type_prefers_majority(self):
        # No value_type specified -- both columns are clearly numeric, so
        # the engine should auto-select numeric comparison.
        df = pd.DataFrame({"a": [1, 2, 3], "b": [5, 1, 10]})
        rule = {"name": "a_le_b", "type": "comparison", "column_a": "a", "column_b": "b", "operator": "<=", "severity": "MEDIUM"}
        violations = apply_comparison(df, rule)
        assert len(violations) == 1
        assert violations[0].row_index == 1

    def test_invalid_operator_is_a_config_error(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([
                {"name": "bad_op", "type": "comparison", "column_a": "a", "column_b": "b", "operator": "<>", "severity": "HIGH"}
            ])

    def test_missing_column_skipped_gracefully(self):
        df = pd.DataFrame({"a": [1, 2]})
        rule = {"name": "a_le_b", "type": "comparison", "column_a": "a", "column_b": "does_not_exist", "operator": "<=", "severity": "MEDIUM"}
        assert apply_comparison(df, rule) == []


# ─── Referential Integrity ─────────────────────────────────────────────

class TestReferentialIntegrity:
    def test_all_references_valid(self):
        df = pd.DataFrame({"customer_id": [1, 2, 3]})
        parent = pd.DataFrame({"customer_id": [1, 2, 3, 4]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH"}
        violations = apply_referential_integrity(df, rule, {"customers": parent})
        assert violations == []

    def test_invalid_reference_flagged(self):
        df = pd.DataFrame({"customer_id": [1, 2, 99]})
        parent = pd.DataFrame({"customer_id": [1, 2, 3]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH"}
        violations = apply_referential_integrity(df, rule, {"customers": parent})
        assert len(violations) == 1
        assert violations[0].row_index == 2
        assert violations[0].actual_value == 99

    def test_null_child_value_skipped_by_default(self):
        df = pd.DataFrame({"customer_id": [1, None]})
        parent = pd.DataFrame({"customer_id": [1, 2]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH"}
        violations = apply_referential_integrity(df, rule, {"customers": parent})
        assert violations == []

    def test_null_child_value_flagged_when_configured(self):
        df = pd.DataFrame({"customer_id": [1, None]})
        parent = pd.DataFrame({"customer_id": [1, 2]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH",
                "treat_null_as_invalid": True}
        violations = apply_referential_integrity(df, rule, {"customers": parent})
        assert len(violations) == 1
        assert violations[0].row_index == 1

    def test_missing_parent_column_skipped_gracefully(self):
        df = pd.DataFrame({"customer_id": [1, 2]})
        parent = pd.DataFrame({"other_column": [1, 2]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH"}
        violations = apply_referential_integrity(df, rule, {"customers": parent})
        assert violations == []

    def test_missing_child_column_skipped_gracefully(self):
        df = pd.DataFrame({"other": [1, 2]})
        parent = pd.DataFrame({"customer_id": [1, 2]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH"}
        violations = apply_referential_integrity(df, rule, {"customers": parent})
        assert violations == []

    def test_parent_dataset_not_supplied_skipped_gracefully(self):
        df = pd.DataFrame({"customer_id": [1, 2]})
        rule = {"name": "valid_ref", "type": "referential_integrity", "child_column": "customer_id",
                "parent_dataset": "customers", "parent_column": "customer_id", "severity": "HIGH"}
        violations = apply_referential_integrity(df, rule, {})
        assert violations == []


# ─── Configuration Validation ────────────────────────────────────────

class TestConfigValidation:
    def test_valid_config_passes(self):
        validate_rule_config([
            {"name": "r1", "type": "required_column", "column": "a", "severity": "HIGH"},
            {"name": "r2", "type": "range", "column": "b", "min": 0, "max": 10, "severity": "MEDIUM"},
        ])  # should not raise

    def test_empty_list_is_valid(self):
        validate_rule_config([])  # should not raise

    def test_not_a_list_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config({"name": "r1"})

    def test_rule_not_a_dict_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config(["not_a_dict"])

    def test_missing_name_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([{"type": "required_column", "column": "a"}])

    def test_missing_type_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([{"name": "r1", "column": "a"}])

    def test_unsupported_type_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([{"name": "r1", "type": "made_up_type", "column": "a"}])

    def test_missing_required_field_raises(self):
        with pytest.raises(RuleConfigError):
            # 'range' requires 'column'
            validate_rule_config([{"name": "r1", "type": "range", "min": 0, "max": 10}])

    def test_duplicate_rule_name_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([
                {"name": "dup", "type": "required_column", "column": "a", "severity": "HIGH"},
                {"name": "dup", "type": "required_column", "column": "b", "severity": "HIGH"},
            ])

    def test_invalid_severity_raises(self):
        with pytest.raises(RuleConfigError):
            validate_rule_config([{"name": "r1", "type": "required_column", "column": "a", "severity": "SUPER_BAD"}])

    def test_severity_defaults_to_medium_when_omitted(self):
        # Omitting severity is allowed -- it defaults, it doesn't error.
        validate_rule_config([{"name": "r1", "type": "required_column", "column": "a"}])


# ─── YAML Loading ──────────────────────────────────────────────────────

class TestLoadRules:
    def test_load_real_config_file(self):
        rules = load_rules("config/rules.yaml")
        assert isinstance(rules, list)
        assert len(rules) > 0
        names = {r["name"] for r in rules}
        assert "customer_id_required" in names
        assert "valid_age" in names

    def test_missing_file_raises_clear_error(self):
        with pytest.raises(RuleConfigError):
            load_rules("config/does_not_exist.yaml")

    def test_malformed_yaml_raises_clear_error(self, tmp_path):
        bad_file = tmp_path / "bad_rules.yaml"
        bad_file.write_text("rules: [this is: not: valid: yaml")
        with pytest.raises(RuleConfigError):
            load_rules(bad_file)

    def test_empty_file_yields_no_rules(self, tmp_path):
        empty_file = tmp_path / "empty_rules.yaml"
        empty_file.write_text("")
        rules = load_rules(empty_file)
        assert rules == []


# ─── RuleEngine / Full Orchestrator ────────────────────────────────────

class TestRuleEngine:
    def test_construction_validates_rules(self):
        with pytest.raises(RuleConfigError):
            RuleEngine([{"name": "bad", "type": "not_a_real_type"}])

    def test_run_combines_multiple_rule_types(self):
        df = pd.DataFrame({
            "age": [25, 150],
            "status": ["active", "bogus"],
        })
        rules = [
            {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"},
            {"name": "valid_status", "type": "allowed_values", "column": "status", "values": ["active", "inactive"], "severity": "MEDIUM"},
        ]
        violations = RuleEngine(rules).run(df)
        rule_names = {v.rule_name for v in violations}
        assert "valid_age" in rule_names
        assert "valid_status" in rule_names

    def test_from_yaml_convenience_constructor(self):
        engine = RuleEngine.from_yaml("config/rules.yaml")
        assert len(engine.rules) > 0

    def test_run_business_rules_convenience_function(self):
        df = pd.DataFrame({"age": [200]})
        rules = [{"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}]
        violations = run_business_rules(df, rules)
        assert len(violations) == 1

    def test_negative_profit_not_flagged_without_explicit_rule(self):
        # Business rules must never invent constraints that weren't configured.
        df = pd.DataFrame({"profit": [-500, 1000, -20]})
        violations = RuleEngine([]).run(df)
        assert violations == []


# ─── Edge Cases ─────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_dataframe(self):
        df = pd.DataFrame({"age": pd.Series(dtype="float64"), "status": pd.Series(dtype="object")})
        rules = [
            {"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"},
            {"name": "valid_status", "type": "allowed_values", "column": "status", "values": ["active"], "severity": "MEDIUM"},
        ]
        violations = RuleEngine(rules).run(df)
        assert violations == []

    def test_one_row_dataframe(self):
        df = pd.DataFrame({"age": [200]})
        rules = [{"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}]
        violations = RuleEngine(rules).run(df)
        assert len(violations) == 1

    def test_custom_pandas_index_preserved(self):
        df = pd.DataFrame({"age": [25, 200]}, index=["row_a", "row_b"])
        rules = [{"name": "valid_age", "type": "range", "column": "age", "min": 18, "max": 100, "severity": "HIGH"}]
        violations = RuleEngine(rules).run(df)
        assert len(violations) == 1
        assert violations[0].row_index == "row_b"

    def test_mixed_types_in_allowed_values_column(self):
        df = pd.DataFrame({"code": [1, "1", 2]})
        rule = {"name": "valid_code", "type": "allowed_values", "column": "code", "values": [1, 2], "severity": "LOW"}
        violations = apply_allowed_values(df, rule)
        # The string "1" is not the same value as the int 1 under isin(), so it's flagged.
        assert len(violations) == 1
        assert violations[0].actual_value == "1"

    def test_missing_columns_across_all_rule_types_handled_gracefully(self):
        df = pd.DataFrame({"unrelated": [1, 2, 3]})
        rules = [
            {"name": "r_range", "type": "range", "column": "age", "min": 0, "max": 10, "severity": "LOW"},
            {"name": "r_allowed", "type": "allowed_values", "column": "status", "values": ["a"], "severity": "LOW"},
            {"name": "r_unique", "type": "uniqueness", "column": "id", "severity": "LOW"},
            {"name": "r_cmp", "type": "comparison", "column_a": "x", "column_b": "y", "operator": "<=", "severity": "LOW"},
            {"name": "r_ref", "type": "referential_integrity", "child_column": "cid",
             "parent_dataset": "parent", "parent_column": "id", "severity": "LOW"},
        ]
        # None of these should crash the engine even though every referenced
        # column is absent from df.
        violations = RuleEngine(rules).run(df)
        assert violations == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])