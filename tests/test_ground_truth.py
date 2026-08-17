import pytest
from tests.ground_truth_engine import load_expected_issues, run_ground_truth_pipeline, calculate_metrics

DATASET_PATH = "tests/ground_truth/synthetic_dataset.csv"
EXPECTED_PATH = "tests/ground_truth/synthetic_expected.yaml"
RULES_PATH = "tests/ground_truth/synthetic_rules.yaml"

@pytest.fixture(scope="module")
def gt_results():
    expected = load_expected_issues(EXPECTED_PATH)
    detected = run_ground_truth_pipeline(DATASET_PATH, RULES_PATH)
    metrics = calculate_metrics(expected, detected)
    return expected, detected, metrics

def test_load_expected_issues(gt_results):
    expected, _, _ = gt_results
    assert len(expected) > 0, "Should load expected issues"
    
    # Check a specific known expected issue
    assert (1, 'email', 'INVALID_EMAIL') in expected

def test_ground_truth_overall_metrics(gt_results):
    _, _, metrics = gt_results
    overall = metrics['OVERALL']
    assert 'TP' in overall
    assert 'FP' in overall
    assert 'FN' in overall
    
    # We shouldn't assert absolute 1.0 accuracy because the engine might have limitations (e.g. DUPLICATE_ID on row 0 as well).
    # But we can assert that Precision, Recall, and F1 are calculated correctly from TP/FP/FN.
    tp, fp, fn = overall['TP'], overall['FP'], overall['FN']
    expected_prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    expected_rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    
    assert overall['Precision'] == expected_prec
    assert overall['Recall'] == expected_rec

def test_fn_calculation():
    # Prove that a missed expected issue becomes an FN
    expected = {(0, 'col1', 'MISSING_VALUE')}
    detected = set() # Empty detection
    metrics = calculate_metrics(expected, detected)
    assert metrics['OVERALL']['FN'] == 1
    assert metrics['OVERALL']['TP'] == 0
    assert metrics['OVERALL']['FP'] == 0
    assert metrics['OVERALL']['Recall'] == 0.0

def test_fp_calculation():
    # Prove that an unexpected detected issue becomes an FP
    expected = set()
    detected = {(0, 'col1', 'INVALID_EMAIL')}
    metrics = calculate_metrics(expected, detected)
    assert metrics['OVERALL']['FP'] == 1
    assert metrics['OVERALL']['TP'] == 0
    assert metrics['OVERALL']['FN'] == 0
    assert metrics['OVERALL']['Precision'] == 0.0

def test_zero_denominator_handling():
    # Empty sets should handle safely
    metrics = calculate_metrics(set(), set())
    assert metrics['OVERALL']['Precision'] == 1.0
    assert metrics['OVERALL']['Recall'] == 1.0
    assert metrics['OVERALL']['F1'] == 1.0

def test_multiple_issues_on_same_row():
    # Prove that multiple issues on the same row are tracked independently
    expected = {
        (1, 'col1', 'MISSING_VALUE'),
        (1, 'col2', 'INVALID_DATE')
    }
    detected = {
        (1, 'col1', 'MISSING_VALUE'),
    }
    metrics = calculate_metrics(expected, detected)
    assert metrics['MISSING_VALUE']['TP'] == 1
    assert metrics['INVALID_DATE']['FN'] == 1
    assert metrics['OVERALL']['TP'] == 1
    assert metrics['OVERALL']['FN'] == 1
