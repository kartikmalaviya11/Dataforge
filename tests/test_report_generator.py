import os
import shutil
import pytest
import pandas as pd
import numpy as np

from src.report_generator import ReportGenerator
from src.profiler import ColumnProfile
from src.type_detector import TypeDetectionResult
from src.issue_manager import StandardizedIssue
from src.scoring import ReadinessScore
from src.kpi_engine import KPIRecommendation
from src.dax_generator import DAXMeasure

@pytest.fixture
def temp_out(tmp_path):
    out_dir = tmp_path / "output"
    return str(out_dir)

@pytest.fixture
def generator(temp_out):
    return ReportGenerator(output_dir=temp_out)

def test_directory_creation(temp_out):
    assert not os.path.exists(temp_out)
    ReportGenerator(output_dir=temp_out)
    assert os.path.exists(temp_out)

def test_null_and_list_serialization(generator):
    assert generator._serialize_value(None) == ""
    assert generator._serialize_value(np.nan) == ""
    assert generator._serialize_value(pd.NaT) == ""
    assert generator._serialize_value("String") == "String"
    assert generator._serialize_value([1, "B", None]) == "1, B, "
    assert generator._serialize_value({"Key": "Value", "Num": 5}) == "Key: Value | Num: 5"

def test_empty_results(generator, temp_out):
    generator.generate_quality_issues([])
    df = pd.read_csv(os.path.join(temp_out, "quality_issues.csv"))
    assert df.empty

def test_determinism_and_round_trip(generator, temp_out):
    # Create some chaotic input
    issues = [
        StandardizedIssue("ISS-2", "Phase4", "MISSING_VALUE", "check", 5, "Sales", None, "NonNull", "HIGH", "Msg", "Rec"),
        StandardizedIssue("ISS-1", "Phase4", "MISSING_VALUE", "check", 2, "Sales", None, "NonNull", "HIGH", "Msg", "Rec")
    ]
    
    # Generate once
    generator.generate_quality_issues(issues)
    path = os.path.join(temp_out, "quality_issues.csv")
    with open(path, "r", encoding="utf-8") as f:
        content_run1 = f.read()
        
    # Generate twice
    generator.generate_quality_issues(issues)
    with open(path, "r", encoding="utf-8") as f:
        content_run2 = f.read()
        
    # Verify deterministic (byte-for-byte exact)
    assert content_run1 == content_run2
    
    # Verify Sorting (ISS-1 should come before ISS-2)
    df = pd.read_csv(path)
    assert df.iloc[0]["issue_id"] == "ISS-1"
    assert df.iloc[1]["issue_id"] == "ISS-2"
    
    # Round-trip verification: Ensure we can read exactly the serialized None as NaN in pandas
    assert pd.isna(df.iloc[0]["actual_value"])

def test_dax_and_kpi_export(generator, temp_out):
    kpis = [
        KPIRecommendation("Total Sales", "Aggr", "HIGH", "AVAILABLE", ["Sales"], ["Sales"], "SUM(Sales)", "Desc", "")
    ]
    dax = [
        DAXMeasure("Total Sales", "Total Sales", "SUM(Dataset[Sales])", "PRODUCTION", ["Sales"], ["Sales"], "Desc", "")
    ]
    generator.generate_kpi_recommendations(kpis)
    generator.generate_dax_measures(dax)
    
    kpi_df = pd.read_csv(os.path.join(temp_out, "kpi_recommendations.csv"))
    dax_df = pd.read_csv(os.path.join(temp_out, "dax_measures.csv"))
    
    assert len(kpi_df) == 1
    assert kpi_df.iloc[0]["kpi_name"] == "Total Sales"
    # Verify list serialization
    assert kpi_df.iloc[0]["required_columns"] == "Sales"
    
    assert len(dax_df) == 1
    assert dax_df.iloc[0]["dax_expression"] == "SUM(Dataset[Sales])"


def test_full_integration(tmp_path):
    # Run the real pipeline
    from src.profiler import profile_dataset
    from src.type_detector import detect_semantic_types
    from src.quality_engine import run_quality_checks
    from src.issue_manager import IssueManager
    from src.scoring import calculate_readiness_score
    from src.kpi_engine import KPIEngine
    from src.dax_generator import DAXGenerator
    
    df = pd.DataFrame({
        "CustomerID": [1, 2, 2, 4],
        "Revenue": [100.5, 200.0, None, 50.0]
    })
    
    # 1. Profile
    col_profs = profile_dataset(df)
    # 2. Type Detection
    types = detect_semantic_types(df, col_profs)
    # 3. Quality (1 duplicate ID, 1 missing value)
    raw_issues = run_quality_checks(df, col_profs, types, id_columns=["CustomerID"])
    # 4. Issue Management
    mgr = IssueManager()
    std_issues = mgr.consolidate(raw_issues)
    # 5. Scoring
    score = calculate_readiness_score(df, col_profs, std_issues)
    # 6. KPI Engine
    kpi_engine = KPIEngine()
    kpis = kpi_engine.recommend_kpis(len(df), types, std_issues)
    # 7. DAX Engine
    dax_gen = DAXGenerator()
    dax = dax_gen.generate_measures(kpis)
    
    # 8. Report Generator
    out_dir = tmp_path / "integration_output"
    gen = ReportGenerator(output_dir=str(out_dir))
    
    gen.export_all("SalesData", len(df), len(df.columns), col_profs, types, std_issues, score, kpis, dax)
    
    # Verify all 7 files exist
    expected_files = [
        "dataset_profile.csv",
        "column_metadata.csv",
        "quality_issues.csv",
        "quality_summary.csv",
        "readiness_score.csv",
        "kpi_recommendations.csv",
        "dax_measures.csv"
    ]
    for f in expected_files:
        assert os.path.exists(os.path.join(out_dir, f))
        
    # Read back and verify correctness
    df_prof = pd.read_csv(os.path.join(out_dir, "dataset_profile.csv"))
    assert df_prof.iloc[0]["dataset_name"] == "SalesData"
    assert df_prof.iloc[0]["row_count"] == 4
    
    df_issues = pd.read_csv(os.path.join(out_dir, "quality_issues.csv"))
    assert len(df_issues) == 3 # 2 for duplicated ID rows, 1 for missing revenue
    assert "MISSING_VALUE" in df_issues["issue_type"].values
    
    df_score = pd.read_csv(os.path.join(out_dir, "readiness_score.csv"))
    assert "overall_score" in df_score.columns
    assert df_score.iloc[0]["grade"] in ["Excellent", "Good", "Fair", "Poor", "Critical"]
    
    df_kpi = pd.read_csv(os.path.join(out_dir, "kpi_recommendations.csv"))
    assert "Total Sales" in df_kpi["kpi_name"].values
    
    df_dax = pd.read_csv(os.path.join(out_dir, "dax_measures.csv"))
    assert len(df_dax) == len(df_kpi)

def test_dashboard_spec_exists():
    assert os.path.exists("docs/powerbi_dashboard_spec.md"), "Dashboard spec missing"
