
import pytest
from src.readiness_checklist import ReadinessChecklist

def test_all_pass():
    rc = ReadinessChecklist()
    for item in rc.items:
        rc.update_item(item, "PASS")
    assert rc.evaluate_overall() == "READY"

def test_missing_artifact_not_run():
    rc = ReadinessChecklist()
    for item in rc.items:
        rc.update_item(item, "PASS")
    rc.update_item("Dashboard", "NOT_RUN")
    assert rc.evaluate_overall() == "BLOCKED"

def test_fail_blocked():
    rc = ReadinessChecklist()
    for item in rc.items:
        rc.update_item(item, "PASS")
    rc.update_item("Cleaning", "FAIL")
    assert rc.evaluate_overall() == "BLOCKED"

def test_warning():
    rc = ReadinessChecklist()
    for item in rc.items:
        rc.update_item(item, "PASS")
    rc.update_item("Cleaning", "WARNING")
    assert rc.evaluate_overall() == "READY_WITH_WARNINGS"

def test_deterministic_status():
    rc = ReadinessChecklist()
    keys = list(rc.get_status().keys())
    assert keys == sorted(keys)
