import pandas as pd
import numpy as np
import os
import yaml

from src.profiler import profile_dataset
from src.type_detector import detect_semantic_types
from src.quality_engine import run_quality_checks, ISSUE_POTENTIAL_DUPLICATE, ISSUE_WHITESPACE, ISSUE_INCONSISTENT_CASE, ISSUE_MISSING_VALUE
from src.issue_manager import IssueManager
from src.proposal_generator import ProposalGenerator
from src.rules import RuleEngine, RuleViolation

def create_test_data():
    data = [
        {"Customer_ID": "C001", "Name": "Priya Patel", "City": "Surat", "Status": "Active", "Revenue": 1000.0, "Email": "priya@example.com", "Phone": "1234567890", "Signup_Date": "2023-01-01"},
        {"Customer_ID": "C031", "Name": "Priya Patel", "City": "Surat", "Status": "Active", "Revenue": 1000.0, "Email": "priya@example.com", "Phone": "1234567890", "Signup_Date": "2023-01-01"},
        {"Customer_ID": "C002", "Name": " Rahul Sharma ", "City": " Surat ", "Status": "Active", "Revenue": 500.0, "Email": "rahul@example.com", "Phone": "9876543210", "Signup_Date": "2023-02-01"},
        {"Customer_ID": "C003", "Name": "Amit Singh", "City": "surat", "Status": "active", "Revenue": 750.0, "Email": "amit@example.com", "Phone": "1122334455", "Signup_Date": "2023-03-01"},
        {"Customer_ID": "C004", "Name": "Neha Gupta", "City": "SURAT", "Status": "ACTIVE", "Revenue": 1200.0, "Email": "neha@example.com", "Phone": "5544332211", "Signup_Date": "2023-04-01"},
        {"Customer_ID": "C039", "Name": "Vikas Verma", "City": "Delhi", "Status": "Active", "Revenue": -9900.0, "Email": "vikas@example.com", "Phone": "9998887776", "Signup_Date": "2023-05-01"},
        {"Customer_ID": "C034", "Name": "Sanjay Dutt", "City": "Mumbai", "Status": "Active", "Revenue": 1500.0, "Email": "", "Phone": " ", "Signup_Date": "NA"},
        {"Customer_ID": "C035", "Name": "Riya Jain", "City": "Pune", "Status": "-", "Revenue": 200.0, "Email": "riya@example.com", "Phone": "7776665554", "Signup_Date": "2023-06-01"},
        {"Customer_ID": "C036", "Name": "Rahul Sharma", "City": "Surat", "Status": "Inactive", "Revenue": 100.0, "Email": "rahul.other@example.com", "Phone": "0000000000", "Signup_Date": "2023-07-01"}
    ]
    return pd.DataFrame(data)

def test_new_requirements_edge_cases():
    df = create_test_data()
    col_profiles = profile_dataset(df)
    type_results = detect_semantic_types(df, col_profiles)
    
    custom_markers = {"NA", "N/A", "NULL", "NONE", "MISSING", "?"}
    
    quality_issues = run_quality_checks(df, col_profiles, type_results, id_columns=["Customer_ID"], custom_missing_markers=custom_markers)
    
    issues_by_type = {}
    for i in quality_issues:
        issues_by_type.setdefault(i.issue_type, []).append(i)
        
    pot_dups = issues_by_type.get(ISSUE_POTENTIAL_DUPLICATE, [])
    assert len(pot_dups) == 2
    assert {i.row_index for i in pot_dups} == {0, 1}
    
    ws = issues_by_type.get(ISSUE_WHITESPACE, [])
    assert len(ws) == 2
    assert {i.row_index for i in ws} == {2}
    
    inc = issues_by_type.get(ISSUE_INCONSISTENT_CASE, [])
    assert len(inc) > 0
    
    miss = issues_by_type.get(ISSUE_MISSING_VALUE, [])
    assert len(miss) == 3
    assert {i.row_index for i in miss} == {6}
    
    rules_yaml = """
- type: range
  column: Revenue
  min: 0
  name: non_negative_revenue
  message: "Revenue cannot be negative"
  severity: HIGH
"""
    rules_dict = yaml.safe_load(rules_yaml)
    engine = RuleEngine(rules_dict)
    rule_issues = engine.run(df)
    assert len(rule_issues) == 1
    assert rule_issues[0].row_index == 5
        
    im = IssueManager()
    all_issues = im.consolidate(quality_issues + rule_issues)
    
    for i in all_issues:
        if i.issue_type in (ISSUE_POTENTIAL_DUPLICATE, ISSUE_INCONSISTENT_CASE):
            assert i.classification.name == "REVIEW_REQUIRED"
        if i.issue_type == ISSUE_WHITESPACE:
            assert i.classification.name == "AUTO_FIXABLE"
