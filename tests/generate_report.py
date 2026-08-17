import json
import os
from tests.ground_truth_engine import load_expected_issues, run_ground_truth_pipeline, calculate_metrics

DATASET_PATH = "tests/ground_truth/synthetic_dataset.csv"
EXPECTED_PATH = "tests/ground_truth/synthetic_expected.yaml"
RULES_PATH = "tests/ground_truth/synthetic_rules.yaml"
REPORT_PATH = "docs/ground_truth_report.md"

def generate_report():
    expected = load_expected_issues(EXPECTED_PATH)
    detected = run_ground_truth_pipeline(DATASET_PATH, RULES_PATH)
    metrics = calculate_metrics(expected, detected)
    
    os.makedirs("docs", exist_ok=True)
    
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 8: Ground-Truth Testing System Report\n\n")
        f.write("This report evaluates the accuracy of the Analytics Readiness & Data Quality Analyzer pipeline against a known synthetic dataset with injected issues.\n\n")
        
        overall = metrics.pop('OVERALL')
        
        f.write("## Overall Metrics\n\n")
        f.write(f"- **True Positives (TP)**: {overall['TP']}\n")
        f.write(f"- **False Positives (FP)**: {overall['FP']}\n")
        f.write(f"- **False Negatives (FN)**: {overall['FN']}\n")
        f.write(f"- **Precision**: {overall['Precision']:.2%}\n")
        f.write(f"- **Recall**: {overall['Recall']:.2%}\n")
        f.write(f"- **F1 Score**: {overall['F1']:.2%}\n\n")
        
        f.write("## Issue-Specific Metrics\n\n")
        f.write("| Issue Type | TP | FP | FN | Precision | Recall | F1 Score |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        
        for itype, m in sorted(metrics.items()):
            f.write(f"| {itype} | {m['TP']} | {m['FP']} | {m['FN']} | {m['Precision']:.2%} | {m['Recall']:.2%} | {m['F1']:.2%} |\n")
            
        f.write("\n## Detailed Breakdown\n\n")
        f.write("### False Positives (Expected to be valid, but flagged as issues)\n")
        if overall['FP'] == 0:
            f.write("*None*\n")
        else:
            for issue in overall['detected_set'] - overall['expected_set']:
                f.write(f"- Row {issue[0]}, Col '{issue[1]}', Type '{issue[2]}'\n")
                
        f.write("\n### False Negatives (Expected to be issues, but not flagged)\n")
        if overall['FN'] == 0:
            f.write("*None*\n")
        else:
            for issue in overall['expected_set'] - overall['detected_set']:
                f.write(f"- Row {issue[0]}, Col '{issue[1]}', Type '{issue[2]}'\n")

if __name__ == "__main__":
    generate_report()
    print("Report generated successfully.")
