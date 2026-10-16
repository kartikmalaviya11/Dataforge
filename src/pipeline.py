import os

def clean_temp_file(path):
    try:
        if os.path.exists(path):
            os.unlink(path)
    except:
        pass

import tempfile
import time
from pathlib import Path
import streamlit as st
from src.ingestion import load_dataset
from src.profiler import profile_dataset
from src.type_detector import detect_semantic_types
from src.quality_engine import run_quality_checks
from src.rules import load_rules, RuleEngine
from src.issue_manager import IssueManager, IssueClassification
from src.proposal_generator import ProposalGenerator
from src.scoring import calculate_readiness_score
from src.kpi_engine import KPIEngine
from src.dax_generator import DAXGenerator
from src.sql_analyzer import SQLAnalyzer
from src.report_generator import ReportGenerator
from src.revalidation import ValidationSnapshot

def run_pipeline(uploaded_file, rules_yaml_path):

    suffix = Path(uploaded_file.name).suffix

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

        tmp.write(uploaded_file.getvalue())

        tmp_path = Path(tmp.name)

    

    start_time = time.time()

    try:

        df, profile = load_dataset(tmp_path)

        col_profiles = profile_dataset(df)

        type_results = detect_semantic_types(df, col_profiles)

        quality_issues = run_quality_checks(df, col_profiles, type_results)

        

        rule_issues = []

        rules_configured = False

        if rules_yaml_path and Path(rules_yaml_path).exists():

            rules = load_rules(Path(rules_yaml_path))

            engine = RuleEngine(rules)

            rule_issues = engine.run(df)

            rules_configured = True

            

        excel_issues = []

        if Path(uploaded_file.name).suffix.lower() in [".xlsx", ".xls"]:

            from src.excel_quality import ExcelQualityEngine

            excel_eng = ExcelQualityEngine(uploaded_file.getvalue())

            excel_issues = excel_eng.analyze(df)

            

        im = IssueManager()

        all_issues = im.consolidate(quality_issues + rule_issues + excel_issues)

        

        if Path(uploaded_file.name).suffix.lower() in [".xlsx", ".xls"] and excel_eng is not None:

            if excel_eng.has_formulas_or_merges:

                for issue in all_issues:

                    if issue.issue_type == "DUPLICATE_ROW":

                        issue.classification = IssueClassification.UNSAFE_TO_FIX

                        issue.message += " (Unsafe to fix: Excel workbook contains formulas or merged cells that would break if rows are deleted)."

        

        prop_gen = ProposalGenerator()

        proposals = prop_gen.generate_proposals(df, all_issues)

        

        readiness = calculate_readiness_score(df, col_profiles, all_issues, rules_configured=rules_configured)

        kpi_engine = KPIEngine()

        kpis = kpi_engine.recommend_kpis(len(df), type_results, all_issues)

        dax_gen = DAXGenerator("Dataset")

        dax = dax_gen.generate_measures(kpis)

        

        sql_analyzer = SQLAnalyzer(df)

        sql_results = []

        for cp in col_profiles:

            if cp.null_count > 0: sql_results.append(sql_analyzer.check_missing_values(cp.name, cp.null_count))

        dup_rows_count = sum(1 for i in quality_issues if i.issue_type == "DUPLICATE_ROW")

        if dup_rows_count > 0: sql_results.append(sql_analyzer.check_duplicate_rows(dup_rows_count))

        for kpi in kpis:

            if kpi.status != "UNAVAILABLE": sql_results.append(sql_analyzer.aggregate_kpi(kpi, None))

        

        out_dir = Path(tempfile.mkdtemp(prefix="ara_reports_"))

        report_gen = ReportGenerator(output_dir=str(out_dir))

        report_gen.export_all(Path(uploaded_file.name).stem, profile.row_count, profile.column_count, col_profiles, type_results, all_issues, readiness, kpis, dax)

        

        before_snapshot = ValidationSnapshot(

            issues=all_issues,

            readiness=readiness,

            col_profiles=col_profiles,

            type_results=type_results

        )

        

        st.session_state.analysis_results = {

            "df": df, 

            "proposals": proposals,

            "profile": profile, "col_profiles": col_profiles, "type_results": type_results,

            "all_issues": all_issues, "readiness": readiness, "kpis": kpis, "dax": dax,

            "sql_results": sql_results, "out_dir": out_dir, "filename": uploaded_file.name,

            "raw_bytes": uploaded_file.getvalue(),

            "filesize": uploaded_file.size, "elapsed": time.time() - start_time,

            "repaired_df": None,

            "repair_results": None,

            "before_snapshot": before_snapshot,

            "after_snapshot": None,

            "comparison_result": None

        }

        return True, ""

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

    finally: clean_temp_file(tmp_path)



def validate_default_cols(df_columns, default_cols):

    valid_defaults = [c for c in default_cols if c in df_columns]

    if not valid_defaults and len(df_columns) > 0:

        valid_defaults = list(df_columns[:min(5, len(df_columns))])

    return valid_defaults



