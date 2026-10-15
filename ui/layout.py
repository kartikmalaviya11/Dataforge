import streamlit as st
import json
from pathlib import Path
from src.workspace import ProjectWorkspace
from ui.theme import badge, metric_card, logo_html, card

def init_navigation():
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Data Import"

def nav_button(label: str, disabled: bool = False):
    is_active = st.session_state.current_page == label
    if is_active:
        st.sidebar.markdown(f"""
        <div style="
            border-left: 3px solid var(--primary);
            background-color: var(--sidebar-hover);
            padding: 0.5rem 1rem;
            margin: 0 0.75rem 0.25rem 0.75rem;
            color: #FFFFFF;
            font-weight: 600;
            border-radius: 6px;
            font-size: 0.9rem;
        ">{label}</div>
        """, unsafe_allow_html=True)
    else:
        if disabled:
            lock_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.4;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>'
            st.sidebar.markdown(f"""
            <div style="
                padding: 0.5rem 1rem;
                margin: 0 0.75rem 0.25rem 0.75rem;
                color: #64748B;
                font-weight: 500;
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-size: 0.9rem;
                border-left: 3px solid transparent;
            ">{label} {lock_svg}</div>
            """, unsafe_allow_html=True)
        else:
            if st.sidebar.button(label, key=f"nav_btn_{label}", use_container_width=True):
                from ui.components import clear_operation
                clear_operation()
                st.session_state.current_page = label
                st.rerun()

def render_sidebar():
    init_navigation()

    st.sidebar.markdown(logo_html(), unsafe_allow_html=True)

    workspace_loaded = "workspace" in st.session_state

    nav_button("Data Import", disabled=False)

    st.sidebar.markdown("<div class='sidebar-section'>PROJECT</div>", unsafe_allow_html=True)
    for p in ["Overview", "Data Quality", "Issues", "Cleaning", "Validation"]:
        nav_button(p, disabled=not workspace_loaded)

    st.sidebar.markdown("<div class='sidebar-section'>ANALYSIS</div>", unsafe_allow_html=True)
    for p in ["Relationships", "Feature Engineering", "SQL Workspace", "Pandas Analysis",
              "KPI Center", "Business Questions", "Segmentation", "Anomaly Detection",
              "Date Analysis", "RCA", "Findings", "Recommendations"]:
        nav_button(p, disabled=not workspace_loaded)

    st.sidebar.markdown("<div class='sidebar-section'>BI</div>", unsafe_allow_html=True)
    for p in ["Power BI Model", "Data Lineage", "Advanced DAX", "Dashboard Blueprint", "Insight → Visual"]:
        nav_button(p, disabled=not workspace_loaded)

    st.sidebar.markdown("<div class='sidebar-section'>GOVERNANCE</div>", unsafe_allow_html=True)
    for p in ["Run History", "Dataset Versioning", "Historical Readiness", "Readiness Checklist", "Assumptions",
              "Business Impact", "Documentation", "Export Package"]:
        nav_button(p, disabled=not workspace_loaded)

    st.sidebar.markdown("<div class='sidebar-section'>TOOLS</div>", unsafe_allow_html=True)
    for p in ["Domain Templates"]:
        nav_button(p, disabled=not workspace_loaded)

    return st.session_state.current_page

def render_global_header(ws: ProjectWorkspace):
    tables = len(ws.registry) if ws.registry else 0

    # Calculate global status
    status_text = "Ready"
    status_level = "success"

    if st.session_state.get("analysis_results"):
        issues = st.session_state.analysis_results.get("issues", [])
        if any(i.severity == "ERROR" for i in issues):
            status_text = "Blocked"
            status_level = "error"
        elif any(i.severity == "WARNING" for i in issues):
            status_text = "Needs Review"
            status_level = "warning"
    elif tables == 0:
        status_text = "Not Initialized"
        status_level = "neutral"

    project_title = "Active Project"
    if tables > 0:
        first_table = list(ws.registry.keys())[0]
        project_title = f"{first_table.capitalize()}" + (" & Related" if tables > 1 else "")

    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.875rem; margin-bottom: 1.25rem;">
        <div>
            <div style="font-size: 1.125rem; font-weight: 700; color: var(--text-primary);">{project_title}</div>
            <span style="color: var(--text-muted); font-size: 0.8125rem;">Project ID: <code>{ws.project_root.name[:8]}</code></span>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
            <div style="font-size: 0.875rem;"><span style="color: var(--text-secondary); margin-right: 0.5rem;">State:</span>{badge(status_text, status_level)}</div>
            <div style="font-size: 0.875rem;"><span style="color: var(--text-secondary); margin-right: 0.25rem;">Tables:</span> <b>{tables}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
