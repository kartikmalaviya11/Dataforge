# Phase 8: Ground-Truth Testing System Report

This report evaluates the accuracy of the Analytics Readiness & Data Quality Analyzer pipeline against a known synthetic dataset with injected issues.

## Overall Metrics

- **True Positives (TP)**: 16
- **False Positives (FP)**: 0
- **False Negatives (FN)**: 0
- **Precision**: 100.00%
- **Recall**: 100.00%
- **F1 Score**: 100.00%

## Issue-Specific Metrics

| Issue Type | TP | FP | FN | Precision | Recall | F1 Score |
|---|---|---|---|---|---|---|
| DUPLICATE_ROW | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| INVALID_DATE | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| INVALID_EMAIL | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| MISSING_VALUE | 3 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| allowed_values | 2 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| comparison | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| range | 5 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| uniqueness | 2 | 0 | 0 | 100.00% | 100.00% | 100.00% |

## Detailed Breakdown

### False Positives (Expected to be valid, but flagged as issues)
*None*

### False Negatives (Expected to be issues, but not flagged)
*None*
