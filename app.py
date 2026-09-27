import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
import zipfile
import io
import time
from collections import Counter

# --- Analytics Engine Imports ---
from src.ingestion import load_dataset
from src.profiler import profile_dataset
from src.type_detector import detect_semantic_types
from src.quality_engine import run_quality_checks
from src.rules import load_rules, RuleEngine
from src.issue_manager import IssueManager, IssueClassification
from src.proposal_generator import ProposalGenerator, ApprovalState
from src.repair_engine import RepairEngine
from src.revalidation import RevalidationEngine, ValidationSnapshot
from src.scoring import calculate_readiness_score
from src.kpi_engine import KPIEngine
from src.dax_generator import DAXGenerator
from src.report_generator import ReportGenerator
from src.sql_analyzer import SQLAnalyzer
from src.export_service import ExportService

from src.workspace import ProjectWorkspace, TableStatus
from src.relationship_engine import RelationshipDetector
from src.er_generator import ERGenerator
from src.data_model import DataModel, RelationshipStatus

class LocalFileMock:
    def __init__(self, file_path):
        self.path = Path(file_path)
        self.name = self.path.name
        self.size = self.path.stat().st_size
    def getvalue(self):
        return self.path.read_bytes()


# --- Page Config & Styling ---
st.set_page_config(page_title="DATAFORGE — Analytics Readiness", page_icon="♦", layout="wide", initial_sidebar_state="expanded")

# Dark Theme CSS Injection
st.markdown('''
<style>
    :root {
        --bg-color: #070B14; --sidebar-bg: #0B1020; --card-bg: #111827; --border-color: #1E293B;
        --primary-cyan: #00B8FF; --secondary-purple: #7C3AED; --success-green: #22C55E;
        --warning-amber: #F59E0B; --danger-red: #EF4444; --text-main: #F8FAFC; --text-muted: #94A3B8;
    }
    
    .stApp { background-color: var(--bg-color); color: var(--text-main); }
    [data-testid="stSidebar"] { background-color: var(--sidebar-bg); border-right: 1px solid var(--border-color); }
    h1, h2, h3, h4, h5, h6, p, label, span { color: var(--text-main) !important; }
    .st-emotion-cache-16idsys p { color: var(--text-muted) !important; }
    
    .stFileUploader > div > div { background-color: rgba(0, 184, 255, 0.05); border: 1px dashed rgba(0, 184, 255, 0.3); border-radius: 8px; }
    
    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, var(--primary-cyan) 0%, var(--secondary-purple) 100%);
        color: white !important; border-radius: 8px; border: none; padding: 0.6rem 1.2rem;
        font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
        box-shadow: 0 4px 15px -3px rgba(0, 184, 255, 0.3); transition: all 0.3s ease;
    }
    div.stButton > button[kind="primary"]:hover { box-shadow: 0 6px 20px -3px rgba(124, 58, 237, 0.4); transform: translateY(-1px); }
    
    div[data-testid="metric-container"] {
        background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.2rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    }
    div[data-testid="metric-container"] label { color: var(--text-muted) !important; font-weight: 500 !important; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.05em; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: var(--text-main) !important; font-weight: 700; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 32px; background-color: transparent; padding: 0; border-bottom: 1px solid var(--border-color); }
    .stTabs [data-baseweb="tab"] { padding: 1rem 0; color: var(--text-muted); font-weight: 600; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { color: var(--primary-cyan); border-bottom: 2px solid var(--primary-cyan); }
    
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid var(--border-color); background-color: var(--card-bg); margin-top: 0.5rem; }
    
    .app-title { background: -webkit-linear-gradient(0deg, var(--primary-cyan), var(--secondary-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.5rem; font-weight: 800; margin-bottom: 0; padding-bottom: 0; }
    .app-subtitle { color: var(--text-muted); font-size: 1.1rem; font-weight: 400; margin-top: 0.5rem; }
    
    /* Toolbar custom styling */
    .toolbar-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 0.5rem; }
    .toolbar-title { font-size: 1.2rem; font-weight: 700; color: white; }
    .toolbar-count { font-size: 0.85rem; color: var(--text-muted); }
    hr { border-color: var(--border-color); margin: 0.5rem 0 1rem 0; }
</style>
''', unsafe_allow_html=True)

if "analysis_results" not in st.session_state: st.session_state.analysis_results = None

def clean_temp_file(path_str):
    if path_str and os.path.exists(path_str):
        try: os.remove(path_str)
        except: pass

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
        
        if excel_issues and Path(uploaded_file.name).suffix.lower() in [".xlsx", ".xls"]:
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
    except Exception as e: return False, str(e)
    finally: clean_temp_file(tmp_path)

def create_zip_archive(out_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in out_dir.iterdir():
            if file.is_file(): zf.write(file, arcname=file.name)
    return buf.getvalue()

def color_status(val):
    if pd.isna(val): return ''
    val_str = str(val).upper()
    if 'MATCH' in val_str and 'MISMATCH' not in val_str: return 'color: #22C55E; font-weight: bold'
    elif 'MISMATCH' in val_str or 'CRITICAL' in val_str: return 'color: #EF4444; font-weight: bold'
    elif 'NOT_AVAILABLE' in val_str: return 'color: #94A3B8'
    elif 'HIGH' in val_str: return 'color: #F97316; font-weight: bold'
    elif 'MEDIUM' in val_str: return 'color: #F59E0B; font-weight: bold'
    elif 'LOW' in val_str or 'INFO' in val_str: return 'color: #00B8FF; font-weight: bold'
    elif 'AVAILABLE' in val_str and 'NOT_' not in val_str and 'UNAVAILABLE' not in val_str: return 'color: #22C55E; font-weight: bold'
    elif 'UNAVAILABLE' in val_str: return 'color: #94A3B8'
    return ''

def class_color(val):
    if pd.isna(val): return ''
    val_str = str(val).upper()
    if 'AUTO_FIXABLE' in val_str: return 'color: #22C55E; font-weight: bold'
    if 'REVIEW_REQUIRED' in val_str: return 'color: #F59E0B; font-weight: bold'
    if 'UNSAFE_TO_FIX' in val_str: return 'color: #EF4444; font-weight: bold'
    return ''

def safe_str(val): return "N/A" if pd.isna(val) else str(val)

def style_df(df):
    for col in df.columns:
        if df[col].dtype == object: df[col] = df[col].apply(safe_str)
    
    def apply_color(x):
        if hasattr(x, 'name') and x.name in ['Classification', 'Status', 'Severity']:
            return x.map(class_color)
        return x.map(color_status)
        
    return df.style.apply(apply_color, axis=0) if hasattr(df.style, 'apply') else df.style

def validate_default_cols(df_columns, default_cols):
    valid_defaults = [c for c in default_cols if c in df_columns]
    if not valid_defaults and len(df_columns) > 0:
        valid_defaults = list(df_columns[:min(5, len(df_columns))])
    return valid_defaults

def render_clean_table(title, df, default_cols, config_dict, filter_defs, row_label):
    st.markdown(f'''
        <div class='toolbar-header'>
            <div class='toolbar-title'>{title}</div>
            <div class='toolbar-count'>{len(df)} {row_label}</div>
        </div>
    ''', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([4, 1.5, 1.5])
    
    with col1:
        search_term = st.text_input(f"search_{title}", label_visibility="collapsed", placeholder=f"Search {row_label}...")
        
    filtered_df = df
    if search_term:
        filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
        
    active_filters_count = 0
    valid_defaults = validate_default_cols(df.columns, default_cols)
    final_cols = valid_defaults
    
    with col2:
        with st.popover("⚙️ Filters", use_container_width=True):
            with st.form(key=f"form_{title}"):
                filter_selections = {}
                for f_name, f_col, f_options in filter_defs:
                    filter_selections[f_col] = st.multiselect(f_name, options=f_options)
                
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                final_cols = st.multiselect("Visible Columns", df.columns, default=valid_defaults)
                
                c1, c2 = st.columns(2)
                with c1: apply_btn = st.form_submit_button("Apply", type="primary", use_container_width=True)
                with c2: clear_btn = st.form_submit_button("Clear", use_container_width=True)
                
                if clear_btn:
                    filter_selections = {k: [] for k in filter_selections}
                    final_cols = valid_defaults
            
            for col_name, selected_vals in filter_selections.items():
                if selected_vals:
                    filtered_df = filtered_df[filtered_df[col_name].isin(selected_vals)]
                    active_filters_count += len(selected_vals)
                    
    with col3:
        st.download_button("📥 Download CSV", data=filtered_df.to_csv(index=False), file_name=f"{title.replace(' ', '_').lower()}.csv", mime="text/csv", use_container_width=True)
        
    if active_filters_count > 0:
        st.caption(f"_{active_filters_count} filter(s) active_")
        
    filtered_df = filtered_df[[c for c in final_cols if c in filtered_df.columns]]
    st.dataframe(style_df(filtered_df), use_container_width=True, column_config=config_dict, height=450)

# --- Sidebar ---
with st.sidebar:
    st.markdown('''
    <div style='margin-bottom: 2rem; padding: 1rem 0;'>
        <div style='margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.75rem;'>
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0;">
                <rect x="4" y="20" width="6" height="8" fill="#00B8FF" rx="1.5"/>
                <rect x="13" y="12" width="6" height="16" fill="#00B8FF" rx="1.5"/>
                <rect x="22" y="4" width="6" height="24" fill="#00B8FF" rx="1.5"/>
                <path d="M16 2L19 7L16 12L13 7L16 2Z" fill="#7C3AED"/>
            </svg>
            <span style='color: #F8FAFC; font-weight: 800; font-size: 1.4rem; letter-spacing: 0.05em;'>DATAFORGE</span>
        </div>
        <div style='color: #94A3B8; font-size: 0.85rem; letter-spacing: 0.02em;'>From Raw Data to Trusted Insights</div>
    </div>
    ''', unsafe_allow_html=True)
    
    workflow_mode = st.radio("Workflow", ["Single File", "Project Workspace"], horizontal=True)
    
    target_file = None
    
    if workflow_mode == "Single File":
        st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;'>DATASET</h4>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload Data", type=["csv", "xlsx"], label_visibility="collapsed")
        target_file = uploaded_file
        
        if target_file:
            st.markdown(f"""
            <div style='background-color: var(--card-bg); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 1rem;'>
                <div style='color: var(--success-green); font-size: 0.8rem; font-weight: bold; margin-bottom: 0.2rem;'>● UPLOADED</div>
                <div style='color: white; font-size: 0.9rem; word-break: break-all;'>{target_file.name}</div>
                <div style='color: var(--text-muted); font-size: 0.8rem;'>{target_file.size / 1024:.1f} KB</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;'>PROJECT FOLDER</h4>", unsafe_allow_html=True)
        project_path = st.text_input("Project Path", placeholder="e.g., C:/data/my_project")
        
        if project_path:
            pp = Path(project_path).resolve()
            if not pp.exists():
                st.error("Directory not found")
            else:
                if "workspace" not in st.session_state or str(st.session_state.workspace.project_root) != str(pp):
                    ws = ProjectWorkspace.load(pp)
                    if not list(ws.registry.keys()):
                        ws.discover_datasets()
                        ws.save()
                    st.session_state.workspace = ws
                    
                ws = st.session_state.workspace
                if not ws.registry:
                    st.warning("No CSV or Excel files found in folder.")
                else:
                    st.markdown(f"**Found {len(ws.registry)} tables.**")
                    table_names = list(ws.registry.keys())
                    selected_table = st.selectbox("Select Table", table_names)
                    
                    if selected_table:
                        entry = ws.registry[selected_table]
                        st.markdown(f"""
                        <div style='background-color: var(--card-bg); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 1rem;'>
                            <div style='color: var(--primary-cyan); font-size: 0.8rem; font-weight: bold; margin-bottom: 0.2rem;'>● {entry.status}</div>
                            <div style='color: white; font-size: 0.9rem; word-break: break-all;'>{entry.file_name}</div>
                            <div style='color: var(--text-muted); font-size: 0.8rem;'>Rows: {entry.row_count or '?'}, Cols: {entry.column_count or '?'}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        target_file = LocalFileMock(entry.file_path)
    
    st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-top: 2rem;'>CONFIGURATION</h4>", unsafe_allow_html=True)
    rules_file = st.selectbox("Rules Protocol", ["config/rules.yaml", "None"])
    rules_path = rules_file if rules_file != "None" else None
    
    st.markdown("<br/>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        btn_label = "Analyze Table" if workflow_mode == "Project Workspace" else "Analyze Dataset"
        if st.button(btn_label, type="primary", use_container_width=True):
            if not target_file: st.error("Please select a file first.")
            else:
                with st.spinner(f"Analyzing {target_file.name}..."):
                    success, err = run_pipeline(target_file, rules_path)
                    if success: 
                        st.success("Analysis Completed")
                        if workflow_mode == "Project Workspace" and "workspace" in st.session_state:
                            st.session_state.workspace.mark_analyzed(selected_table)
                    else: 
                        st.error(f"Analysis Failed:\\n{err}")
    with c2:
        if st.button("Analyze New", use_container_width=True):
            st.session_state.analysis_results = None
            st.rerun()

    st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-top: 2rem;'>SYSTEM STATUS</h4>", unsafe_allow_html=True)
    if st.session_state.analysis_results: st.markdown("<div style='color: var(--success-green); font-weight: 600; font-size: 0.9rem;'>● Ready / Success</div>", unsafe_allow_html=True)
    else: st.markdown("<div style='color: var(--warning-amber); font-weight: 600; font-size: 0.9rem;'>● Waiting for data</div>", unsafe_allow_html=True)

# --- Main Content ---
st.markdown("<h1 class='app-title'>Analytics Readiness & Data Quality Analyzer</h1>", unsafe_allow_html=True)
st.markdown("<div class='app-subtitle'>Turn raw data into trusted insights, KPIs and Power BI-ready outputs.</div>", unsafe_allow_html=True)
st.markdown("<br/>", unsafe_allow_html=True)

if workflow_mode == "Project Workspace" and "workspace" in st.session_state and st.session_state.workspace.registry:
    st.markdown("### Project Data Model & SQL Analysis")
    p_tab1, p_tab2, p_tab3, p_tab4, p_tab5, p_tab6, p_tab7, p_tab8 = st.tabs(["Data Model", "SQL Analysis Workspace", "Feature Engineering", "KPI Builder", "Business Questions", "Segmentation", "Anomalies", "Date Analysis"])
    
    with p_tab1:
        if st.button("Detect Relationships", type="primary"):
            with st.spinner("Analyzing relationships across tables..."):
                ws = st.session_state.workspace
                tables = {}
                for tname in ws.registry.keys():
                    df, _ = ws.load_table(tname)
                    tables[tname] = df
                
                detector = RelationshipDetector()
                candidates = detector.detect(tables)
                st.session_state.relationship_candidates = candidates
                st.success(f"Detected {len(candidates)} relationships candidates!")
                
        if "relationship_candidates" in st.session_state:
            candidates = st.session_state.relationship_candidates
            st.markdown("#### Review Relationship Candidates")
            if not candidates:
                st.info("No candidates detected.")
            else:
                rel_data = []
                for i, r in enumerate(candidates):
                    rel_data.append({
                        "Accept": r.status == RelationshipStatus.ACCEPTED.value,
                        "Source": f"{r.source_table}.{r.source_column}",
                        "Target": f"{r.target_table}.{r.target_column}",
                        "Cardinality": r.cardinality,
                        "Confidence": f"{r.confidence:.1f}%",
                        "Evidence": " | ".join(r.evidence)
                    })
                
                edited_df = st.data_editor(
                    pd.DataFrame(rel_data),
                    column_config={
                        "Accept": st.column_config.CheckboxColumn(
                            "Accept", help="Select to approve this relationship", default=False
                        )
                    },
                    disabled=["Source", "Target", "Cardinality", "Confidence", "Evidence"],
                    hide_index=True,
                    key="rel_editor"
                )
                
                if st.button("Apply Selected Relationships"):
                    accepted = []
                    for i, row in edited_df.iterrows():
                        c = candidates[i]
                        if row["Accept"]:
                            c.status = RelationshipStatus.ACCEPTED.value
                            accepted.append(c)
                        else:
                            c.status = RelationshipStatus.REJECTED.value
                    
                    dm = DataModel(tables=st.session_state.workspace.registry, relationships=accepted)
                    st.session_state.data_model = dm
                    st.rerun()
                    
        if "data_model" in st.session_state:
            dm = st.session_state.data_model
            st.markdown("#### Accepted Relationships & ER Diagram")
            if not dm.relationships:
                st.info("No relationships accepted.")
            else:
                gen = ERGenerator()
                dot_str = gen.generate_dot(dm)
                st.graphviz_chart(dot_str)

    with p_tab3:
        from src.sql_engine import DuckDBEngine
        from src.feature_engineering import FeatureEngine, FeatureBuilder
        
        ws = st.session_state.workspace
        if "sql_engine" not in st.session_state:
            st.session_state.sql_engine = DuckDBEngine(ws)
        engine = st.session_state.sql_engine
        
        if "fe_engine" not in st.session_state:
            st.session_state.fe_engine = FeatureEngine(engine, ws)
        fe = st.session_state.fe_engine
        
        st.markdown("#### Feature Engineering Module")
        
        f_tables = list(ws.registry.keys())
        if not f_tables:
            st.warning("No tables available.")
        else:
            ft_table = st.selectbox("Source Table", f_tables, key="fe_table")
            
            try:
                base_cols = fe._get_base_columns(ft_table)
            except:
                base_cols = []
                
            ft_type = st.selectbox("Feature Type", [
                "DATE_DIFFERENCE", "DATE_PART", "BOOLEAN_FLAG", "CONDITIONAL_COLUMN", 
                "ARITHMETIC_FORMULA", "BUCKET_CATEGORY"
            ], key="fe_type")
            
            ft_name = st.text_input("New Feature Name", key="fe_name")
            
            st.markdown("##### Configuration")
            feat_def = None
            
            try:
                if ft_type == "DATE_DIFFERENCE":
                    c1, c2, c3 = st.columns(3)
                    start_c = c1.selectbox("Start Date Column", base_cols, key="dd_start")
                    end_c = c2.selectbox("End Date Column", base_cols, key="dd_end")
                    unit_c = c3.selectbox("Unit", ["day", "month", "year"], key="dd_unit")
                    if ft_name and start_c and end_c:
                        feat_def = FeatureBuilder.build_date_difference(ft_name, ft_table, start_c, end_c, unit_c)
                        
                elif ft_type == "DATE_PART":
                    c1, c2 = st.columns(2)
                    col_c = c1.selectbox("Date Column", base_cols, key="dp_col")
                    part_c = c2.selectbox("Part", ["year", "month", "quarter", "week"], key="dp_part")
                    if ft_name and col_c:
                        feat_def = FeatureBuilder.build_date_part(ft_name, ft_table, col_c, part_c)
                        
                elif ft_type == "BOOLEAN_FLAG":
                    c1, c2, c3 = st.columns(3)
                    col_c = c1.selectbox("Column", base_cols, key="bf_col")
                    op_c = c2.selectbox("Operator", [">", "<", ">=", "<=", "==", "!="], key="bf_op")
                    val_c = c3.text_input("Value", key="bf_val")
                    if ft_name and col_c and val_c:
                        feat_def = FeatureBuilder.build_boolean_flag(ft_name, ft_table, col_c, op_c, val_c)
                        
                elif ft_type == "CONDITIONAL_COLUMN":
                    c1, c2, c3, c4 = st.columns(4)
                    col_c = c1.selectbox("Column", base_cols, key="cc_col")
                    op_c = c2.selectbox("Operator", [">", "<", ">=", "<=", "==", "!="], key="cc_op")
                    val_c = c3.text_input("Value", key="cc_val")
                    res_c = c4.text_input("Result (e.g. 'High')", key="cc_res")
                    def_c = st.text_input("Default/Else Result", key="cc_def")
                    if ft_name and col_c and val_c and res_c and def_c:
                        feat_def = FeatureBuilder.build_conditional_column(ft_name, ft_table, [{"col": col_c, "op": op_c, "val": val_c, "result": res_c}], def_c)
                        
                elif ft_type == "ARITHMETIC_FORMULA":
                    c1, c2, c3 = st.columns(3)
                    col1_c = c1.selectbox("Column 1", base_cols, key="af_c1")
                    op_c = c2.selectbox("Operator", ["+", "-", "*", "/"], key="af_op")
                    col2_c = c3.selectbox("Column 2", base_cols, key="af_c2")
                    if ft_name and col1_c and col2_c:
                        feat_def = FeatureBuilder.build_arithmetic(ft_name, ft_table, col1_c, op_c, col2_c)
                        
                elif ft_type == "BUCKET_CATEGORY":
                    c1, c2 = st.columns(2)
                    col_c = c1.selectbox("Column", base_cols, key="bc_col")
                    def_c = c2.text_input("Default Category", key="bc_def")
                    st.caption("Simplified single-bucket UI. (Expandable in future)")
                    b1, b2, b3 = st.columns(3)
                    min_c = b1.text_input("Min Bound (optional)", key="bc_min")
                    max_c = b2.text_input("Max Bound (optional)", key="bc_max")
                    lbl_c = b3.text_input("Category Label", key="bc_lbl")
                    if ft_name and col_c and def_c and lbl_c:
                        bk = {"label": lbl_c}
                        if min_c: bk["min"] = min_c
                        if max_c: bk["max"] = max_c
                        feat_def = FeatureBuilder.build_bucket_category(ft_name, ft_table, col_c, [bk], def_c)
            except Exception as e:
                st.error(f"Configuration Error: {e}")
                
            if feat_def:
                st.markdown("##### Preview")
                try:
                    # Render preview safely
                    df_prev = engine.execute_query(f'SELECT * FROM "{ft_table}_raw" LIMIT 5')
                    # Build a temp preview query
                    cols_str = ", ".join([f'"{c}"' for c in feat_def.source_columns if c in df_prev.columns])
                    if not cols_str: cols_str = "*"
                    preview_q = f'SELECT {cols_str}, {feat_def.expression} AS "{feat_def.feature_name}" FROM "{ft_table}_raw" LIMIT 10'
                    df_res = engine.execute_query(preview_q)
                    st.dataframe(df_res, use_container_width=True)
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Create Feature", type="primary"):
                            try:
                                fe.create_feature(feat_def)
                                st.success(f"Feature '{ft_name}' created successfully!")
                                st.rerun()
                            except Exception as ce:
                                st.error(f"Failed to create: {ce}")
                    with b2:
                        if st.button("Cancel / Reject", type="secondary"):
                            st.info("Feature creation cancelled. No changes made.")
                            st.rerun()
                except Exception as prev_e:
                    st.error(f"Preview Failed: {prev_e}")

            st.markdown("---")
            st.markdown("##### Existing Features")
            exist_feats = fe.get_features(ft_table)
            if not exist_feats:
                st.caption("No features defined for this table.")
            for ex_f in exist_feats:
                with st.expander(f"✨ {ex_f.feature_name} ({ex_f.feature_type})"):
                    st.json({
                        "Type": ex_f.feature_type,
                        "Source Columns": ex_f.source_columns,
                        "Expression": ex_f.expression,
                        "Created": ex_f.created_at
                    })

    with p_tab2:
        st.markdown("#### SQL Workspace")
        
        from src.sql_engine import DuckDBEngine, SecurityError
        from src.query_manager import QueryManager
        from src.sql_templates import SQLTemplateLibrary
        
        ws = st.session_state.workspace
        qm = QueryManager(ws.project_root)
        library = SQLTemplateLibrary()
        
        # We initialize the engine lazily to avoid holding memory if not used
        if "sql_engine" not in st.session_state:
            st.session_state.sql_engine = DuckDBEngine(ws)
            
        engine = st.session_state.sql_engine
        
        c1, c2 = st.columns([3, 1])
        with c1:
            sql_input = st.text_area("Write SQL Query", height=200, placeholder="SELECT * FROM table_name LIMIT 10")
            
            c_btn1, c_btn2, c_btn3 = st.columns(3)
            with c_btn1:
                run_btn = st.button("Run Query (Preview)", type="primary", use_container_width=True)
            with c_btn2:
                export_btn = st.button("Run & Export Full Result", use_container_width=True)
            with c_btn3:
                save_btn = st.button("Save Query", use_container_width=True)
                
            if save_btn and sql_input.strip():
                qm.save_query(f"Saved Query {len(qm.get_saved_queries())+1}", sql_input)
                st.success("Query saved!")
                
            if run_btn and sql_input.strip():
                try:
                    start_t = time.time()
                    res_df = engine.execute_query(sql_input)
                    dur = int((time.time() - start_t) * 1000)
                    qm.log_history(sql_input, "SUCCESS", dur, len(res_df))
                    st.success(f"Query executed in {dur}ms (Preview Limit: {engine.preview_limit})")
                    st.dataframe(res_df, use_container_width=True)
                except Exception as e:
                    qm.log_history(sql_input, "ERROR", 0, 0, str(e))
                    st.error(f"Error: {str(e)}")
                    
            if export_btn and sql_input.strip():
                try:
                    start_t = time.time()
                    out_path = engine.export_query(sql_input)
                    dur = int((time.time() - start_t) * 1000)
                    qm.log_history(sql_input, "EXPORT", dur, None)
                    st.success(f"Exported in {dur}ms to {out_path}")
                    with open(out_path, "rb") as f:
                        st.download_button("Download CSV", data=f, file_name=Path(out_path).name, mime="text/csv")
                except Exception as e:
                    qm.log_history(sql_input, "ERROR", 0, 0, str(e))
                    st.error(f"Error: {str(e)}")
                    
        with c2:
            st.markdown("##### Query Templates")
            tmpl_name = st.selectbox("Select Template", [t.name for t in library.get_all_templates()])
            if tmpl_name:
                tmpl = library.get_template(tmpl_name)
                st.caption(tmpl.description)
                st.code(tmpl.template, language="sql")
                
            st.markdown("##### Saved Queries")
            saved = qm.get_saved_queries()
            if not saved:
                st.caption("No saved queries.")
            for q in saved:
                st.markdown(f"**{q.name}**")
                st.code(q.sql, language="sql")
                
    with p_tab4:
        st.markdown("### KPI Builder & Cross-Validation")
        st.markdown("Define analytical KPIs and validate their SQL ↔ Pandas calculation consistency.")
        
        from src.kpi_engine import KPIManager, KPIDefinition, MetricDefinition, FilterDefinition, CrossValidator, SQLValidator, PandasValidator, KPISemanticChecker
        import uuid
        
        kpi_mgr = KPIManager(st.session_state.workspace)
        engine = DuckDBEngine(st.session_state.workspace)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("#### Create New KPI")
            with st.form("kpi_form"):
                kpi_name = st.text_input("KPI Name", placeholder="e.g. Total Revenue")
                kpi_desc = st.text_area("Business Definition", placeholder="Total sum of successful transactions...")
                
                st.markdown("##### Metric Definition")
                op = st.selectbox("Operation", ["COUNT", "COUNT_DISTINCT", "SUM", "AVG", "MIN", "MAX"])
                
                tables = list(st.session_state.workspace.registry.keys())
                src_tbl = st.selectbox("Source Table", tables, key="kpi_src_tbl")
                
                # Fetch columns for the table
                df_temp, _ = st.session_state.workspace.load_table(src_tbl)
                cols = list(df_temp.columns)
                src_col = st.selectbox("Source Column", cols, key="kpi_src_col")
                
                st.markdown("##### Filters (Optional)")
                f_col = st.selectbox("Filter Column", ["None"] + cols, key="kpi_f_col")
                f_op = st.selectbox("Operator", ["==", "!=", ">", "<", ">=", "<="])
                f_val = st.text_input("Value")
                
                create_kpi_btn = st.form_submit_button("Validate & Save KPI", type="primary")
                
                if create_kpi_btn:
                    if not kpi_name or not src_tbl or not src_col:
                        st.error("Name, Table, and Column are required.")
                    else:
                        filters = []
                        if f_col != "None" and f_val:
                            # Try to infer type
                            try:
                                if "." in f_val: f_val = float(f_val)
                                else: f_val = int(f_val)
                            except:
                                pass
                            filters.append(FilterDefinition(column=f_col, operator=f_op, value=f_val))
                            
                        metric = MetricDefinition(
                            metric_name=kpi_name,
                            operation=op,
                            source_table=src_tbl,
                            source_column=src_col,
                            filters=filters if filters else None
                        )
                        
                        cross = CrossValidator(SQLValidator(engine), PandasValidator(engine))
                        checker = KPISemanticChecker()
                        
                        try:
                            # 1. Semantic Check
                            sem = checker.check_consistency(metric)
                            
                            # 2. Cross Validation
                            res = cross.validate(metric)
                            
                            st.session_state.last_kpi_validation = res
                            st.session_state.last_kpi_semantic = sem
                            
                            if res["status"] == "MATCH":
                                kpi_def = KPIDefinition(
                                    kpi_id=str(uuid.uuid4()),
                                    kpi_name=kpi_name,
                                    business_definition=kpi_desc,
                                    formula=f"{op}({src_col})",
                                    metric_definitions=[metric],
                                    source_tables=[src_tbl],
                                    source_columns=[src_col],
                                    unit="",
                                    description=kpi_desc
                                )
                                kpi_mgr.save_kpi(kpi_def, overwrite=True)
                                st.success(f"KPI '{kpi_name}' validated and saved!")
                            else:
                                st.error("Validation Failed! SQL and Pandas results mismatch.")
                        except Exception as e:
                            st.error(f"Error validating KPI: {e}")
                            
        with c2:
            st.markdown("#### Validation Results")
            if "last_kpi_validation" in st.session_state:
                res = st.session_state.last_kpi_validation
                sem = st.session_state.last_kpi_semantic
                
                if res["status"] == "MATCH":
                    st.success("✅ SQL ↔ Pandas Match")
                else:
                    st.error("❌ SQL ↔ Pandas Mismatch")
                    
                st.markdown(f"**SQL Result:** `{res['sql_result']}`")
                st.markdown(f"**Pandas Result:** `{res['pandas_result']}`")
                if res['absolute_diff'] is not None:
                    st.caption(f"Absolute Difference: {res['absolute_diff']}")
                    
                with st.expander("Semantic Consistency Check", expanded=True):
                    st.code(f"-- SQL Representation\\n{sem['sql_representation']}", language="sql")
                    st.code(f"# Pandas Representation\\n{sem['pandas_representation']}", language="python")
                    st.code(f"// Power BI DAX\\n{sem['powerbi_representation']}", language="dax")
                    
            st.markdown("---")
            st.markdown("#### Saved KPIs")
            kpis = kpi_mgr.load_kpis()
            if not kpis:
                st.info("No KPIs defined yet.")
            else:
                for k in kpis:
                    with st.expander(f"📊 {k.kpi_name}"):
                        st.write(k.business_definition)
                        m = k.metric_definitions[0]
                        st.code(f"{m.operation}({m.source_table}.{m.source_column})", language="sql")
    with p_tab5:
        st.markdown("### Business Question Tracker")
        from src.business_questions import QuestionManager, InvalidStatusError, InvalidTransitionError
        from src.kpi_engine import KPIManager
        from src.sql_engine import DuckDBEngine, SecurityError
        
        q_mgr = QuestionManager(st.session_state.workspace)
        kpi_mgr = KPIManager(st.session_state.workspace)
        db_eng = DuckDBEngine(st.session_state.workspace)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("#### Ask a Question")
            with st.form("new_q_form"):
                new_q = st.text_input("New Business Question")
                if st.form_submit_button("Create Question", type="primary"):
                    if new_q:
                        q_mgr.create_question(new_q)
                        st.success("Question created!")
                        st.rerun()
                    else:
                        st.error("Question cannot be empty.")
                        
            active_qs = q_mgr.get_active_questions()
            archived_qs = q_mgr.get_archived_questions()
            
            view_mode = st.radio("View", ["Active", "Archived"], horizontal=True)
            qs_to_show = active_qs if view_mode == "Active" else archived_qs
            
            st.markdown(f"**{len(qs_to_show)} {view_mode} Questions**")
            
            selected_q_id = None
            for q in qs_to_show:
                if st.button(f"[{q.status}] {q.question[:30]}...", key=f"q_btn_{q.question_id}"):
                    st.session_state.selected_bq_id = q.question_id
                    
            if "selected_bq_id" in st.session_state:
                selected_q_id = st.session_state.selected_bq_id
                
        with c2:
            if selected_q_id:
                q = q_mgr.get_question(selected_q_id)
                if not q:
                    st.info("Question not found.")
                else:
                    st.markdown(f"#### {q.question}")
                    st.caption(f"Status: **{q.status}**")
                    
                    with st.expander("Status & Lifecycle", expanded=True):
                        c_stat, c_act = st.columns(2)
                        new_stat = c_stat.selectbox("Change Status", ["Pending", "Investigating", "Completed"], index=["Pending", "Investigating", "Completed"].index(q.status))
                        reason = c_act.text_input("Reason for change (optional)")
                        if c_act.button("Update Status"):
                            try:
                                q_mgr.transition_status(q.question_id, new_stat, reason if reason else None)
                                st.success("Status updated")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                                
                        if not q.is_archived:
                            if st.button("Archive Question"):
                                q_mgr.archive_question(q.question_id)
                                st.rerun()
                        else:
                            if st.button("Unarchive Question"):
                                q_mgr.unarchive_question(q.question_id)
                                st.rerun()
                                
                        st.markdown("**History:**")
                        for h in q.status_history:
                            st.caption(f"-> {h['new_status']} ({h.get('reason', '')})")

                    with st.expander("Details & Analysis", expanded=True):
                        desc = st.text_area("Description", value=q.description or "")
                        pandas_notes = st.text_area("Pandas Analysis / Notes", value=q.pandas_analysis or "")
                        result_text = st.text_area("Result", value=q.result or "")
                        finding_text = st.text_area("Finding", value=q.finding or "")
                        
                        kpis = kpi_mgr.load_kpis()
                        kpi_options = {"None": None}
                        for k in kpis:
                            kpi_options[f"{k.kpi_name} ({k.kpi_id})"] = k.kpi_id
                            
                        # Handle orphaned references safely
                        cur_kpi_idx = 0
                        if q.related_kpi_id:
                            if q.related_kpi_id not in kpi_options.values():
                                kpi_options[f"Orphaned/Deleted KPI ({q.related_kpi_id})"] = q.related_kpi_id
                            
                        kpi_names = list(kpi_options.keys())
                        cur_idx = 0
                        for i, name in enumerate(kpi_names):
                            if kpi_options[name] == q.related_kpi_id:
                                cur_idx = i
                                break
                        
                        rel_kpi = st.selectbox("Related KPI", kpi_names, index=cur_idx)
                        kpi_val = kpi_options[rel_kpi]
                        
                        rel_vis = st.text_input("Dashboard Visual Reference", value=q.related_dashboard_visual or "")
                        
                        if st.button("Save Details"):
                            q_mgr.update_question(
                                q.question_id,
                                description=desc,
                                pandas_analysis=pandas_notes,
                                result=result_text,
                                finding=finding_text,
                                related_kpi_id=kpi_val,
                                related_dashboard_visual=rel_vis
                            )
                            st.success("Details saved!")
                            st.rerun()
                            
                    with st.expander("SQL Attachment", expanded=True):
                        sql = st.text_area("Attached SQL", value=q.sql_query or "")
                        col_run, col_save = st.columns(2)
                        
                        if col_run.button("Run SQL (Preview)", type="primary"):
                            try:
                                res_df = db_eng.execute_query(sql)
                                st.dataframe(res_df)
                            except Exception as e:
                                st.error(f"Execution Error: {e}")
                                
                        if col_save.button("Save SQL"):
                            q_mgr.update_question(q.question_id, sql_query=sql)
                            st.success("SQL Saved!")
                            st.rerun()



    with p_tab6:
        st.markdown("### Analytical Segmentation")
        from src.segmentation_engine import SegmentationEngine, SegmentDefinition, ExplicitThresholdRule
        from src.kpi_engine import KPIManager
        
        seg_eng = SegmentationEngine(st.session_state.workspace)
        kpi_mgr = KPIManager(st.session_state.workspace)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("#### Create Segmentation")
            with st.form("seg_form"):
                seg_id = st.text_input("Segment ID (Name)")
                entity_type = st.selectbox("Entity Type", ["customer", "seller", "product"])
                
                tables = list(st.session_state.workspace.registry.keys())
                source_table = st.selectbox("Source Table", tables if tables else [""])
                
                entity_key = st.text_input("Entity Key Column")
                
                kpis = kpi_mgr.load_kpis()
                kpi_options = {k.kpi_name: k.kpi_id for k in kpis}
                kpi_sel = st.selectbox("Metric Reference (KPI)", list(kpi_options.keys()) if kpi_options else [""])
                metric_ref = kpi_options.get(kpi_sel, "")
                
                # Simplified Explicit Rule for UI testing
                st.markdown("**Threshold 1 (Lower Bound = 0)**")
                u1 = st.number_input("Upper Bound 1", value=50.0)
                l1_label = st.text_input("Label 1", value="Low")
                
                st.markdown("**Threshold 2 (Upper Bound = Infinity)**")
                l2_label = st.text_input("Label 2", value="High")
                
                missing_val = st.selectbox("Missing Value Handling", ["EXCLUDE", "NULL_LABEL"])
                
                preview = st.form_submit_button("Preview")
                save = st.form_submit_button("Save Configuration")
                
        with c2:
            if preview and seg_id and source_table and entity_key and metric_ref:
                try:
                    rules = [
                        ExplicitThresholdRule(lower_bound=0.0, lower_inclusive=True, upper_bound=u1, upper_inclusive=False, label=l1_label),
                        ExplicitThresholdRule(lower_bound=u1, lower_inclusive=True, upper_bound=999999999.0, upper_inclusive=False, label=l2_label)
                    ]
                    df = seg_eng.preview_segmentation(
                        entity_type=entity_type,
                        source_table=source_table,
                        entity_key=entity_key,
                        metric_reference=metric_ref,
                        method="EXPLICIT_THRESHOLDS",
                        rules=rules,
                        missing_value_handling=missing_val
                    )
                    st.success("Preview Generated!")
                    st.dataframe(df.head(100))
                except Exception as e:
                    st.error(f"Validation Error: {e}")
                    
            if save and seg_id and source_table and entity_key and metric_ref:
                try:
                    rules = [
                        ExplicitThresholdRule(lower_bound=0.0, lower_inclusive=True, upper_bound=u1, upper_inclusive=False, label=l1_label),
                        ExplicitThresholdRule(lower_bound=u1, lower_inclusive=True, upper_bound=999999999.0, upper_inclusive=False, label=l2_label)
                    ]
                    seg_eng.create_segmentation(
                        segment_id=seg_id,
                        entity_type=entity_type,
                        source_table=source_table,
                        entity_key=entity_key,
                        metric_reference=metric_ref,
                        method="EXPLICIT_THRESHOLDS",
                        rules=rules,
                        missing_value_handling=missing_val
                    )
                    st.success("Segmentation Saved!")
                except Exception as e:
                    st.error(f"Error Saving: {e}")
                    
        st.markdown("#### Existing Segmentations")
        for s in seg_eng.load_segmentations():
            st.write(f"- **{s.segment_id}** ({s.entity_type} via {s.metric_reference})")

    with p_tab7:
        st.markdown("### Outlier & Anomaly Analysis")
        from src.anomaly_engine import AnomalyEngine
        ano_eng = AnomalyEngine(st.session_state.workspace)
        
        ac1, ac2 = st.columns([1, 2])
        with ac1:
            with st.form("ano_form"):
                ano_id = st.text_input("Analysis ID")
                tables = list(st.session_state.workspace.registry.keys())
                source_table = st.selectbox("Source Table (Anomaly)", tables if tables else [""])
                source_col = st.text_input("Source Column (Numeric)")
                method = st.selectbox("Detection Method", ["IQR", "Z_SCORE"])
                
                preview_a = st.form_submit_button("Preview")
                save_a = st.form_submit_button("Run & Save Analysis")
                
        with ac2:
            if preview_a and ano_id and source_table and source_col:
                try:
                    res = ano_eng.run_analysis(ano_id, source_table, source_col, method, {})
                    st.success(f"Preview: Found {len(res.outlier_records)} outliers.")
                    if res.outlier_records:
                        import pandas as pd
                        st.dataframe(pd.DataFrame([r.__dict__ for r in res.outlier_records]).head(100))
                except Exception as e:
                    st.error(f"Validation Error: {e}")
                    
            if save_a and ano_id and source_table and source_col:
                try:
                    res = ano_eng.run_analysis(ano_id, source_table, source_col, method, {})
                    ano_eng.save_analysis(res)
                    st.success("Analysis Saved!")
                except Exception as e:
                    st.error(f"Error Saving: {e}")
                    
        st.markdown("#### Existing Analyses")
        for a in ano_eng.load_analyses():
            st.write(f"- **{a.analysis_id}** ({a.method} on {a.source_table}.{a.source_column}): {len(a.outlier_records)} outliers")

    with p_tab8:
        st.markdown("### Date Analysis Engine")
        from src.date_analysis_engine import DateAnalysisEngine
        date_eng = DateAnalysisEngine(st.session_state.workspace)
        
        dc1, dc2 = st.columns([1, 2])
        with dc1:
            with st.form("date_form"):
                config_id = st.text_input("Config ID")
                tables = list(st.session_state.workspace.registry.keys())
                source_table = st.selectbox("Source Table (Date)", tables if tables else [""])
                date_col = st.text_input("Date Column")
                
                preview_d = st.form_submit_button("Preview Date Table")
                save_d = st.form_submit_button("Generate & Save Date Table")
                
        with dc2:
            if preview_d and config_id and source_table and date_col:
                try:
                    df = date_eng.preview_date_table(config_id, source_table, date_col)
                    st.success("Date Table Preview Generated!")
                    st.dataframe(df.head(100))
                except Exception as e:
                    st.error(f"Validation Error: {e}")
                    
            if save_d and config_id and source_table and date_col:
                try:
                    date_eng.create_date_config(config_id, source_table, date_col)
                    st.success("Date Table Generated and Saved!")
                except Exception as e:
                    st.error(f"Error Saving: {e}")
                    
        st.markdown("#### Existing Date Configurations")
        for d in date_eng.load_configs():
            st.write(f"- **{d.config_id}** ({d.source_table}.{d.date_column})")

if not st.session_state.analysis_results:
    if workflow_mode != "Project Workspace":
        st.info("Upload a CSV or XLSX file from the sidebar and click 'Analyze Dataset' to begin.")
    else:
        st.info("Select a table from the sidebar and click 'Analyze Table' to run data quality checks on it.")
else:
    res = st.session_state.analysis_results
    
    tabs = st.tabs(["Overview", "Data Quality", "Issues", "Suggested Fixes", "Re-validation", "KPI Recommendations", "DAX Measures", "SQL Validation", "Export"])
    
    with tabs[0]:
        st.markdown("<h3 style='color: white !important;'>Overview Summary</h3>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", f"{res['profile'].row_count:,}")
        c2.metric("Columns", f"{res['profile'].column_count}")
        
        comp = res.get("comparison_result")
        if comp:
            c3.metric("Readiness Score", f"{comp.after_readiness:.1f}%", delta=f"{comp.readiness_change:+.1f}%")
            c4.metric("Total Issues", comp.after_issue_count, delta=comp.after_issue_count - comp.before_issue_count, delta_color="inverse")
        else:
            c3.metric("Readiness Score", f"{res['readiness'].overall_score:.1f}%")
            c4.metric("Total Issues", len(res['all_issues']))
            
        st.markdown("<h4 style='color: var(--text-muted) !important; margin-top: 2rem;'>Repair State</h4>", unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        if comp:
            r1.metric("Repairs Applied", len([p for p in res["proposals"] if p.approval_state.value == "APPROVED"]))
            r2.metric("Issues Resolved", comp.resolved_issue_count)
            r3.metric("Issues Remaining", comp.remaining_issue_count)
            r4.metric("New Issues", comp.new_issue_count, delta=comp.new_issue_count if comp.new_issue_count > 0 else None, delta_color="inverse")
        else:
            proposals = res.get("proposals", [])
            r1.metric("Proposed Fixes", len(proposals))
            r2.metric("Pending Review", len([p for p in proposals if p.approval_state.value == "PENDING"]))
            r3.metric("AUTO_FIXABLE", sum(1 for p in proposals if p.classification.value == "AUTO_FIXABLE"))
            r4.metric("UNSAFE_TO_FIX", sum(1 for i in res['all_issues'] if i.classification.value == "UNSAFE_TO_FIX"))

    with tabs[1]:
        st.markdown("<h3 style='color: white !important;'>Data Quality Metadata</h3>", unsafe_allow_html=True)
        dt_c1, dt_c2 = st.columns(2)
        with dt_c1:
            st.markdown("<h4 style='color: var(--text-muted) !important;'>Semantic Types</h4>", unsafe_allow_html=True)
            type_counts = Counter(t.detected_type for t in res['type_results'])
            if type_counts: st.bar_chart(pd.DataFrame([{"Type": k, "Count": v} for k, v in type_counts.items()]).set_index("Type"), color="#00B8FF")
        with dt_c2:
            st.markdown("<h4 style='color: var(--text-muted) !important;'>Storage Types</h4>", unsafe_allow_html=True)
            stor_counts = Counter(t.storage_type for t in res['type_results'])
            if stor_counts: st.bar_chart(pd.DataFrame([{"Type": k, "Count": v} for k, v in stor_counts.items()]).set_index("Type"), color="#7C3AED")
                
        cp_dict = {cp.name: cp for cp in res['col_profiles']}
        types_df = pd.DataFrame([{
            "Column": t.column_name, "Storage Type": t.storage_type, "Semantic Type": t.detected_type,
            "Confidence": f"{t.confidence:.0%}", "Null %": f"{cp_dict[t.column_name].null_percentage:.1f}%",
            "Unique %": f"{cp_dict[t.column_name].unique_percentage:.1f}%", "Status": t.status
        } for t in res['type_results']])
        
        render_clean_table("Column Metadata", types_df, ["Column", "Storage Type", "Semantic Type", "Confidence", "Null %", "Unique %", "Status"], {}, [("Semantic Type", "Semantic Type", list(set(types_df["Semantic Type"]))), ("Status", "Status", list(set(types_df["Status"])))], "columns")

    with tabs[2]:
        st.markdown("<h3 style='color: white !important;'>Issues Explorer</h3>", unsafe_allow_html=True)
        issues = res['after_snapshot'].issues if res.get('after_snapshot') else res['all_issues']
        if not issues:
            st.success("No data-quality issues detected.")
        else:
            issues_df = pd.DataFrame([{
                "Issue ID": i.issue_id, "Source": i.source, "Type": i.issue_type, "Classification": i.classification.value, "Severity": i.severity, 
                "Column": i.column or "-", "Row": i.row_index if hasattr(i, 'row_index') and i.row_index is not None else "-", 
                "Message": i.message, "Recommendation": i.recommendation
            } for i in issues])
            
            config_dict = {"Message": st.column_config.TextColumn("Message", width="large"), "Recommendation": st.column_config.TextColumn("Recommendation", width="large")}
            filter_defs = [
                ("Severity", "Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
                ("Classification", "Classification", ["AUTO_FIXABLE", "REVIEW_REQUIRED", "UNSAFE_TO_FIX"]),
                ("Issue Type", "Type", list(set(i.issue_type for i in issues))),
                ("Column", "Column", [c for c in res['profile'].column_names])
            ]
            render_clean_table("Quality Issues", issues_df, ["Issue ID", "Type", "Classification", "Severity", "Column", "Row", "Message", "Recommendation"], config_dict, filter_defs, "issues")

    with tabs[3]:
        st.markdown("<h3 style='color: white !important;'>Suggested Fixes</h3>", unsafe_allow_html=True)
        proposals = res.get("proposals", [])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("AUTO_FIXABLE", sum(1 for p in proposals if p.classification.value == "AUTO_FIXABLE"))
        c2.metric("REVIEW_REQUIRED", sum(1 for p in proposals if p.classification.value == "REVIEW_REQUIRED"))
        c3.metric("UNSAFE_TO_FIX", sum(1 for i in res['all_issues'] if i.classification.value == "UNSAFE_TO_FIX"))
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        if not proposals:
            st.info("No safe deterministic repairs are available.")
        else:
            prop_data = []
            for i, p in enumerate(proposals):
                prop_data.append({
                    "_idx": i,
                    "Approve": p.approval_state.value == "APPROVED",
                    "Row": safe_str(p.row_index),
                    "Column": safe_str(p.column),
                    "Before": safe_str(p.old_value),
                    "Proposed": safe_str(p.proposed_value),
                    "Action": p.action,
                    "Classification": p.classification.value,
                    "Status": p.approval_state.value,
                    "Reason": p.reason
                })
            
            pdf = pd.DataFrame(prop_data)
            
            st.markdown("Select **Approve** to mark a proposal for execution.")
            edited_df = st.data_editor(
                pdf, 
                column_config={"Approve": st.column_config.CheckboxColumn("Approve", default=False)}, 
                disabled=["Row", "Column", "Before", "Proposed", "Action", "Classification", "Status", "Reason", "_idx"],
                hide_index=True,
                use_container_width=True,
                key="proposal_editor"
            )
            
            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                if st.button("Approve All AUTO_FIXABLE", use_container_width=True):
                    for p in proposals:
                        if p.classification.value == "AUTO_FIXABLE":
                            p.approval_state = ApprovalState.APPROVED
                    st.rerun()
            with bc2:
                if st.button("Reject All", use_container_width=True):
                    for p in proposals:
                        p.approval_state = ApprovalState.REJECTED
                    st.rerun()
                    
            # Apply Changes
            st.markdown("<hr>", unsafe_allow_html=True)
            if st.button("Apply Approved Changes", type="primary"):
                for idx, row in edited_df.iterrows():
                    real_idx = row["_idx"]
                    is_approved = row["Approve"]
                    proposals[real_idx].approval_state = ApprovalState.APPROVED if is_approved else ApprovalState.REJECTED
                
                re = RepairEngine()
                instructions = [p.to_repair_instruction() for p in proposals if p.approval_state.value == "APPROVED"]
                
                if not instructions:
                    st.warning("No instructions approved for execution.")
                else:
                    with st.spinner("Applying repairs and re-validating..."):
                        repaired_df, repair_res = re.apply(res["df"], instructions)
                        res["repaired_df"] = repaired_df
                        res["repair_results"] = repair_res
                        
                        rules_yaml = rules_path if 'rules_path' in locals() and rules_path != "None" else None
                        rev_eng = RevalidationEngine(rules_yaml_path=rules_yaml)
                        
                        after_snapshot = rev_eng.run_validation(repaired_df)
                        comparison_result = rev_eng.compare(res["before_snapshot"], after_snapshot)
                        
                        res["after_snapshot"] = after_snapshot
                        res["comparison_result"] = comparison_result
                        
                    st.success(f"Applied {len(instructions)} repair instructions!")
                    st.rerun()

    with tabs[4]:
        st.markdown("<h3 style='color: white !important;'>Re-validation Result</h3>", unsafe_allow_html=True)
        if not res.get("comparison_result"):
            st.info("Re-validation will appear here after executing approved repairs.")
        else:
            comp = res["comparison_result"]
            
            if comp.new_issue_count > 0:
                st.error(f"⚠️ DANGER: The repair process introduced {comp.new_issue_count} new data-quality issues.")
            if comp.readiness_change < 0:
                st.warning("⚠️ WARNING: Readiness decreased after repair.")
            
            sum_c1, sum_c2, sum_c3, sum_c4 = st.columns(4)
            sum_c1.metric("Issues Before", comp.before_issue_count)
            sum_c2.metric("Issues After", comp.after_issue_count, delta=comp.after_issue_count - comp.before_issue_count, delta_color="inverse")
            sum_c3.metric("Resolved", comp.resolved_issue_count)
            sum_c4.metric("New Issues", comp.new_issue_count, delta=comp.new_issue_count if comp.new_issue_count > 0 else None, delta_color="inverse")
            
            r_c1, r_c2 = st.columns(2)
            r_c1.metric("Readiness Before", f"{comp.before_readiness:.1f}%")
            r_c2.metric("Readiness After", f"{comp.after_readiness:.1f}%", delta=f"{comp.readiness_change:+.1f}%")
            
            st.markdown("<h4 style='color: var(--text-muted) !important; margin-top: 1rem;'>Remaining & New Issues</h4>", unsafe_allow_html=True)
            if not comp.remaining_issues and not comp.new_issues:
                st.success("All issues were successfully resolved!")
            else:
                combined = []
                for i in comp.remaining_issues: combined.append({"Status": "🟡 Remaining", "Issue ID": i.issue_id, "Type": i.issue_type, "Severity": i.severity, "Column": i.column})
                for i in comp.new_issues: combined.append({"Status": "🔴 New", "Issue ID": i.issue_id, "Type": i.issue_type, "Severity": i.severity, "Column": i.column})
                st.dataframe(pd.DataFrame(combined), use_container_width=True)

    with tabs[5]:
        kpis_df = pd.DataFrame([{
            "KPI Name": k.kpi_name, "Category": k.category, "Priority": k.priority, "Status": k.status,
            "Calculation Logic": k.calculation_logic, "Explanation": k.explanation,
            "Required Columns": ", ".join(k.required_columns), "Available Columns": ", ".join(k.available_columns)
        } for k in res['kpis']])
        render_clean_table("KPI Recommendations", kpis_df, ["KPI Name", "Category", "Priority", "Status", "Required Columns", "Calculation Logic"], {"Calculation Logic": st.column_config.TextColumn("Calculation Logic", width="large"), "Explanation": st.column_config.TextColumn("Explanation", width="large")}, [("Status", "Status", list(set(kpis_df["Status"]))), ("Category", "Category", list(set(kpis_df["Category"]))), ("Priority", "Priority", list(set(kpis_df["Priority"])))], "KPI recommendations")
        
    with tabs[6]:
        dax_df = pd.DataFrame([{
            "Measure": d.measure_name, "KPI": d.kpi_name, "Status": d.status, "DAX Expression": d.dax_expression
        } for d in res['dax']])
        render_clean_table("DAX Measures", dax_df, ["Measure", "KPI", "Status", "DAX Expression"], {"DAX Expression": st.column_config.TextColumn("DAX Expression", width="large")}, [("Status", "Status", list(set(dax_df["Status"])))], "DAX measures")

    with tabs[7]:
        if not res['sql_results']: st.info("No SQL validations were necessary for this dataset.")
        else:
            sql_df = pd.DataFrame([{
                "Metric": sql.query_name, "Python Result": safe_str(sql.python_result), "SQL Result": safe_str(sql.sql_result),
                "Difference": safe_str(sql.difference), "Status": sql.match_status, "Query": sql.sql
            } for sql in res['sql_results']])
            render_clean_table("SQL Validation", sql_df, ["Metric", "Python Result", "SQL Result", "Difference", "Status"], {"Query": st.column_config.TextColumn("Query", width="large")}, [("Status", "Status", list(set(sql_df["Status"])))], "metrics")
            
    with tabs[8]:
        st.markdown("<h3 style='color: white !important;'>A. DATAFORGE 2.0 Cleaned Data</h3>", unsafe_allow_html=True)
        if not res.get("repair_results"):
            st.info("Cleaned Data export is only available after repairs have been approved and applied.")
        else:
            st.markdown("Ready to export:\n- ✓ Repaired dataset\n- ✓ Validation completed\n- ✓ Change log available\n- ✓ Review summary available")
            
            exporter = ExportService()
            csv_bytes = exporter.export_csv(res["repaired_df"])
            excel_bytes = exporter.export_excel(
                df=res["repaired_df"],
                repair_results=res["repair_results"],
                proposals=res["proposals"],
                comparison_result=res["comparison_result"],
                after_issues=res["after_snapshot"].issues,
                raw_bytes=res.get("raw_bytes"),
                filename=res.get("filename")
            )
            
            dl_c1, dl_c2 = st.columns(2)
            with dl_c1:
                st.download_button(label="Download Cleaned CSV", data=csv_bytes, file_name="DATAFORGE_CLEANED.csv", mime="text/csv", use_container_width=True)
            with dl_c2:
                st.download_button(label="Download Cleaned Excel", data=excel_bytes, file_name="DATAFORGE_CLEANED.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                st.caption("Excel includes: Cleaned_Data, Changes_Made, Needs_Review, and Summary sheets.")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<h3 style='color: white !important;'>B. Analytics Reports</h3>", unsafe_allow_html=True)
        out_dir = res['out_dir']
        cols = st.columns(3)
        idx = 0
        for file in out_dir.iterdir():
            if file.is_file():
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div style='background-color: var(--card-bg); border: 1px solid var(--border-color); padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
                        <h4 style='color: white; margin-top: 0;'>📄 {file.name}</h4>
                        <p style='color: var(--text-muted); font-size: 0.85rem;'>Generated analytics output.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.download_button(label=f"Download {file.name}", data=file.read_text(encoding='utf-8'), file_name=file.name, mime="text/csv", key=f"dl_file_{idx}")
                idx += 1
        
        st.markdown("---")
        zip_data = create_zip_archive(out_dir)
        st.download_button("Download All Reports (ZIP)", zip_data, "analytics_reports.zip", "application/zip", type="primary", use_container_width=True)

