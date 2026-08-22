import pytest
import pandas as pd
from src.type_detector import detect_semantic_type
from src.issue_manager import IssueClassification, StandardizedIssue
from src.proposal_generator import ProposalGenerator

def test_type_detection_strong_signals():
    # 1. Quantity with dirty values
    s1 = pd.Series([1, 2, "three", 4, 5, None, "2024-01-01"])
    t1, _, _ = detect_semantic_type(s1, "Quantity", "object")
    assert t1 in ("Integer", "Decimal")

    # 2. Discount_Pct
    s2 = pd.Series([0.1, 0.2, "dirty", "10-2"])
    t2, _, _ = detect_semantic_type(s2, "Discount_Pct", "object")
    assert t2 == "Percentage"

    # 3. Phone
    s3 = pd.Series(["1234567890", "unknown", "555-5555"])
    t3, _, _ = detect_semantic_type(s3, "Customer_Phone", "object")
    assert t3 == "Phone"

    # 4. Order_Date
    s4 = pd.Series(["2024-01-01", "2024-01-02", "bad date"])
    t4, _, _ = detect_semantic_type(s4, "Order_Date", "object")
    assert t4 == "Date"

    # 5. Customer_Email
    s5 = pd.Series(["a@b.com", "c@d.com", "not an email"])
    t5, _, _ = detect_semantic_type(s5, "Customer_Email", "object")
    assert t5 == "Email"

    # 6. Customer_ID
    s6 = pd.Series(["ID1", "ID2", "ID3", "dirty"])
    t6, _, _ = detect_semantic_type(s6, "Customer_ID", "object")
    assert t6 == "ID"

def test_proposal_generation():
    generator = ProposalGenerator()
    df = pd.DataFrame({"col1": ["1", "2"], "id": ["a", "b"]})

    # Safe deterministic -> proposal
    i1 = StandardizedIssue("1", "src", "BLANK_VALUE", "rule", 0, "col1", "  ", "", "LOW", "msg", "rec", IssueClassification.AUTO_FIXABLE)
    p1 = generator._generate_single_proposal(df, i1)
    assert p1 is not None
    assert p1.classification == IssueClassification.AUTO_FIXABLE

    # Reviewable -> proposal (INVALID_NUMERIC is now REVIEW_REQUIRED)
    i2 = StandardizedIssue("2", "src", "INVALID_NUMERIC", "rule", 0, "col1", " 123 ", "", "HIGH", "msg", "rec", IssueClassification.REVIEW_REQUIRED)
    p2 = generator._generate_single_proposal(df, i2)
    assert p2 is not None
    assert p2.classification == IssueClassification.REVIEW_REQUIRED

    # Unsafe -> blocked from proposal by generator.generate_proposals
    i3 = StandardizedIssue("3", "src", "DUPLICATE_ID", "rule", 0, "id", "a", "", "CRITICAL", "msg", "rec", IssueClassification.UNSAFE_TO_FIX)
    props = generator.generate_proposals(df, [i3])
    # DUPLICATE_ID is UNSAFE_TO_FIX so no proposal generated (there might be one for whitespace column, so we filter)
    assert len([p for p in props if p.issue_id == "3"]) == 0
