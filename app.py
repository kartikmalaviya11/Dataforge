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
from src.issue_manager import IssueManager
from src.scoring import calculate_readiness_score
from src.kpi_engine import KPIEngine
from src.dax_generator import DAXGenerator
from src.report_generator import ReportGenerator
from src.sql_analyzer import SQLAnalyzer

# --- Page Config & Styling ---
st.set_page_config(page_title="DATAFORGE — Analytics Readiness", page_icon="♦", layout="wide", initial_sidebar_state="expanded")

# Dark Theme CSS Injection
st.markdown("""
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
""", unsafe_allow_html=True)

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
            
        im = IssueManager()
        all_issues = im.consolidate(quality_issues + rule_issues)
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
        
        st.session_state.analysis_results = {
            "profile": profile, "col_profiles": col_profiles, "type_results": type_results,
            "all_issues": all_issues, "readiness": readiness, "kpis": kpis, "dax": dax,
            "sql_results": sql_results, "out_dir": out_dir, "filename": uploaded_file.name,
            "filesize": uploaded_file.size, "elapsed": time.time() - start_time
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

def safe_str(val): return "N/A" if pd.isna(val) else str(val)

def style_df(df):
    for col in df.columns:
        if df[col].dtype == object: df[col] = df[col].apply(safe_str)
    return df.style.map(color_status) if hasattr(df.style, 'map') else df.style.applymap(color_status)

def validate_default_cols(df_columns, default_cols):
    """Ensure default columns exist in the DataFrame. Fallback if empty."""
    valid_defaults = [c for c in default_cols if c in df_columns]
    if not valid_defaults and len(df_columns) > 0:
        valid_defaults = list(df_columns[:min(5, len(df_columns))])
    return valid_defaults

def render_clean_table(title, df, default_cols, config_dict, filter_defs, row_label):
    st.markdown(f"""
        <div class='toolbar-header'>
            <div class='toolbar-title'>{title}</div>
            <div class='toolbar-count'>{len(df)} {row_label}</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([4, 1.5, 1.5])
    
    with col1:
        search_term = st.text_input(f"search_{title}", label_visibility="collapsed", placeholder=f"Search {row_label}...")
        
    filtered_df = df
    if search_term:
        filtered_df = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
        
    active_filters_count = 0
    
    # Validation of default_cols
    valid_defaults = validate_default_cols(df.columns, default_cols)
    final_cols = valid_defaults
    
    with col2:
        with st.popover("⚙️ Filters", use_container_width=True):
            with st.form(key=f"form_{title}"):
                filter_selections = {}
                for f_name, f_col, f_options in filter_defs:
                    filter_selections[f_col] = st.multiselect(f_name, options=f_options)
                
                # Column visibility filter included cleanly in popover
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                final_cols = st.multiselect("Visible Columns", df.columns, default=valid_defaults)
                
                c1, c2 = st.columns(2)
                with c1:
                    apply_btn = st.form_submit_button("Apply", type="primary", use_container_width=True)
                with c2:
                    clear_btn = st.form_submit_button("Clear", use_container_width=True)
                
                if clear_btn:
                    filter_selections = {k: [] for k in filter_selections}
                    final_cols = valid_defaults
            
            # Apply popover filters outside form scope
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
    st.markdown("""
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
    """, unsafe_allow_html=True)
    
    st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;'>DATASET</h4>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Data", type=["csv", "xlsx"], label_visibility="collapsed")
    
    if uploaded_file:
        st.markdown(f"""
        <div style='background-color: var(--card-bg); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 1rem;'>
            <div style='color: var(--success-green); font-size: 0.8rem; font-weight: bold; margin-bottom: 0.2rem;'>● UPLOADED</div>
            <div style='color: white; font-size: 0.9rem; word-break: break-all;'>{uploaded_file.name}</div>
            <div style='color: var(--text-muted); font-size: 0.8rem;'>{uploaded_file.size / 1024:.1f} KB</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-top: 2rem;'>CONFIGURATION</h4>", unsafe_allow_html=True)
    rules_file = st.selectbox("Rules Protocol", ["config/rules.yaml", "None"])
    rules_path = rules_file if rules_file != "None" else None
    
    st.markdown("<br/>", unsafe_allow_html=True)
    
    if st.button("Analyze Dataset", type="primary"):
        if not uploaded_file: st.error("Please upload a file first.")
        else:
            with st.spinner("Analyzing dataset..."):
                success, err = run_pipeline(uploaded_file, rules_path)
                if success: st.success("Analysis Completed")
                else: st.error(f"Analysis Failed:\n{err}")

    st.markdown("<h4 style='color: var(--primary-cyan) !important; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-top: 2rem;'>SYSTEM STATUS</h4>", unsafe_allow_html=True)
    if st.session_state.analysis_results: st.markdown("<div style='color: var(--success-green); font-weight: 600; font-size: 0.9rem;'>● Ready / Success</div>", unsafe_allow_html=True)
    else: st.markdown("<div style='color: var(--warning-amber); font-weight: 600; font-size: 0.9rem;'>● Waiting for data</div>", unsafe_allow_html=True)

# --- Main Content ---
st.markdown("<h1 class='app-title'>Analytics Readiness & Data Quality Analyzer</h1>", unsafe_allow_html=True)
st.markdown("<div class='app-subtitle'>Turn raw data into trusted insights, KPIs and Power BI-ready outputs.</div>", unsafe_allow_html=True)
st.markdown("<br/>", unsafe_allow_html=True)

if st.session_state.analysis_results:
    res = st.session_state.analysis_results
    
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Rows", f"{res['profile'].row_count:,}")
    m2.metric("Columns", f"{res['profile'].column_count}")
    m3.metric("Readiness Score", f"{res['readiness'].overall_score:.1f}%")
    m4.metric("Grade", "A" if res['readiness'].overall_score >= 90 else "B" if res['readiness'].overall_score >= 80 else "C" if res['readiness'].overall_score >= 70 else "D" if res['readiness'].overall_score >= 60 else "F")
    m5.metric("Issues", f"{len(res['all_issues'])}")
    m6.metric("KPIs Available", f"{sum(1 for k in res['kpis'] if k.status != 'UNAVAILABLE')}")
    m7.metric("DAX Measures", f"{len(res['dax'])}")
    
    st.markdown("<br/>", unsafe_allow_html=True)
    tabs = st.tabs(["Overview", "Data Quality", "Data Types", "KPIs", "DAX Measures", "SQL Validation", "Downloads"])
    
    with tabs[0]:
        st.markdown("<h3 style='color: white !important;'>Overview Summary</h3>", unsafe_allow_html=True)
        col_ov1, col_ov2 = st.columns(2)
        with col_ov1:
            st.markdown("<h4 style='color: var(--text-muted) !important;'>Readiness Dimensions</h4>", unsafe_allow_html=True)
            score_df = pd.DataFrame([{"Dimension": k, "Score": v} for k, v in res['readiness'].dimension_scores.items()])
            if not score_df.empty: st.bar_chart(score_df.set_index("Dimension"), color="#00B8FF")
        with col_ov2:
            st.markdown("<h4 style='color: var(--text-muted) !important;'>Issues by Severity</h4>", unsafe_allow_html=True)
            sev_counts = Counter(i.severity for i in res['all_issues'])
            if sev_counts: st.bar_chart(pd.DataFrame([{"Severity": k, "Count": v} for k, v in sev_counts.items()]).set_index("Severity"), color="#7C3AED")
            else: st.success("No Issues Found")
                
        st.markdown("<h4 style='color: var(--text-muted) !important; margin-top: 2rem;'>Top KPI Recommendations</h4>", unsafe_allow_html=True)
        kpi_table = pd.DataFrame([{"KPI": k.kpi_name, "Category": k.category, "Priority": k.priority, "Status": k.status} for k in res['kpis'][:5]])
        st.dataframe(style_df(kpi_table), use_container_width=True)
        
    with tabs[1]:
        q_c1, q_c2, q_c3, q_c4, q_c5 = st.columns(5)
        sev_counts = Counter(i.severity for i in res['all_issues'])
        q_c1.metric("Total Issues", len(res['all_issues']))
        q_c2.metric("Critical", sev_counts.get("CRITICAL", 0))
        q_c3.metric("High", sev_counts.get("HIGH", 0))
        q_c4.metric("Medium", sev_counts.get("MEDIUM", 0))
        q_c5.metric("Low", sev_counts.get("LOW", 0))
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        issues_df = pd.DataFrame([{
            "Issue ID": i.issue_id, "Source": i.source, "Type": i.issue_type, "Severity": i.severity, 
            "Column": i.column or "-", "Row": i.row_index if hasattr(i, 'row_index') and i.row_index is not None else "-", 
            "Message": i.message, "Recommendation": i.recommendation
        } for i in res['all_issues']])
        
        default_cols = ["Issue ID", "Type", "Severity", "Column", "Row", "Message", "Recommendation"]
        config_dict = {"Message": st.column_config.TextColumn("Message", width="large"), "Recommendation": st.column_config.TextColumn("Recommendation", width="large")}
        filter_defs = [
            ("Severity", "Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
            ("Issue Type", "Type", list(set(i.issue_type for i in res['all_issues']))),
            ("Column", "Column", [c for c in res['profile'].column_names])
        ]
        render_clean_table("Quality Issues", issues_df, default_cols, config_dict, filter_defs, "issues")
            
    with tabs[2]:
        dt_c1, dt_c2 = st.columns(2)
        with dt_c1:
            st.markdown("<h4 style='color: var(--text-muted) !important;'>Semantic Types</h4>", unsafe_allow_html=True)
            type_counts = Counter(t.detected_type for t in res['type_results'])
            if type_counts: st.bar_chart(pd.DataFrame([{"Type": k, "Count": v} for k, v in type_counts.items()]).set_index("Type"), color="#00B8FF")
        with dt_c2:
            st.markdown("<h4 style='color: var(--text-muted) !important;'>Storage Types</h4>", unsafe_allow_html=True)
            stor_counts = Counter(t.storage_type for t in res['type_results'])
            if stor_counts: st.bar_chart(pd.DataFrame([{"Type": k, "Count": v} for k, v in stor_counts.items()]).set_index("Type"), color="#7C3AED")
                
        st.markdown("<hr>", unsafe_allow_html=True)
        
        cp_dict = {cp.name: cp for cp in res['col_profiles']}
        types_df = pd.DataFrame([{
            "Column": t.column_name, "Storage Type": t.storage_type, "Semantic Type": t.detected_type,
            "Confidence": f"{t.confidence:.0%}", "Null %": f"{cp_dict[t.column_name].null_percentage:.1f}%",
            "Unique %": f"{cp_dict[t.column_name].unique_percentage:.1f}%", "Status": t.status
        } for t in res['type_results']])
        
        default_cols = ["Column", "Storage Type", "Semantic Type", "Confidence", "Null %", "Unique %", "Status"]
        filter_defs = [
            ("Semantic Type", "Semantic Type", list(set(types_df["Semantic Type"]))),
            ("Status", "Status", list(set(types_df["Status"])))
        ]
        render_clean_table("Column Metadata", types_df, default_cols, {}, filter_defs, "columns")

    with tabs[3]:
        kpis_df = pd.DataFrame([{
            "KPI Name": k.kpi_name, "Category": k.category, "Priority": k.priority, "Status": k.status,
            "Calculation Logic": k.calculation_logic, "Explanation": k.explanation,
            "Required Columns": ", ".join(k.required_columns), "Available Columns": ", ".join(k.available_columns)
        } for k in res['kpis']])
        
        default_cols = ["KPI Name", "Category", "Priority", "Status", "Required Columns", "Calculation Logic"]
        config_dict = {"Calculation Logic": st.column_config.TextColumn("Calculation Logic", width="large"), "Explanation": st.column_config.TextColumn("Explanation", width="large")}
        filter_defs = [
            ("Status", "Status", list(set(kpis_df["Status"]))),
            ("Category", "Category", list(set(kpis_df["Category"]))),
            ("Priority", "Priority", list(set(kpis_df["Priority"])))
        ]
        render_clean_table("KPI Recommendations", kpis_df, default_cols, config_dict, filter_defs, "KPI recommendations")
        
    with tabs[4]:
        dax_df = pd.DataFrame([{
            "Measure": d.measure_name, "KPI": d.kpi_name, "Status": d.status, "DAX Expression": d.dax_expression
        } for d in res['dax']])
        
        default_cols = ["Measure", "KPI", "Status", "DAX Expression"]
        config_dict = {"DAX Expression": st.column_config.TextColumn("DAX Expression", width="large")}
        filter_defs = [("Status", "Status", list(set(dax_df["Status"])))]
        render_clean_table("DAX Measures", dax_df, default_cols, config_dict, filter_defs, "DAX measures")

    with tabs[5]:
        if not res['sql_results']: st.info("No SQL validations were necessary for this dataset.")
        else:
            sql_df = pd.DataFrame([{
                "Metric": sql.query_name, "Python Result": safe_str(sql.python_result), "SQL Result": safe_str(sql.sql_result),
                "Difference": safe_str(sql.difference), "Status": sql.match_status, "Query": sql.sql
            } for sql in res['sql_results']])
            
            default_cols = ["Metric", "Python Result", "SQL Result", "Difference", "Status"]
            config_dict = {"Query": st.column_config.TextColumn("Query", width="large")}
            filter_defs = [("Status", "Status", list(set(sql_df["Status"])))]
            render_clean_table("SQL Validation", sql_df, default_cols, config_dict, filter_defs, "metrics")
            
    with tabs[6]:
        st.markdown("<h4 style='color: var(--text-muted) !important;'>Exported Analytics Packages</h4>", unsafe_allow_html=True)
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
