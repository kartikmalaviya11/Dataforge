import streamlit as st
import json
from pathlib import Path
from src.workspace import ProjectWorkspace
from ui.theme import badge, metric_card, logo_html, card, clean_html

def init_navigation():
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Data Import"

def nav_button(label: str, disabled: bool = False):
    is_active = st.session_state.current_page == label
    if is_active:
        active_html = f"""
        <div style="border-left: 3px solid var(--primary); background: linear-gradient(90deg, rgba(56, 103, 255, 0.22) 0%, rgba(120, 87, 255, 0.12) 100%); border: 1px solid rgba(56, 103, 255, 0.25); border-left: 3px solid var(--primary); padding: 0.52rem 0.85rem; margin: 0 0.5rem 0.25rem 0.5rem; color: #FFFFFF; font-weight: 600; border-radius: 8px; font-size: 0.85rem; display: flex; align-items: center; box-shadow: 0 2px 8px rgba(56, 103, 255, 0.15);">
            <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--primary); margin-right: 8px; box-shadow: 0 0 8px var(--primary);"></span>
            {label}
        </div>
        """
        st.sidebar.markdown(clean_html(active_html), unsafe_allow_html=True)
    else:
        if disabled:
            lock_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.4;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>'
            disabled_html = f"""
            <div style="padding: 0.48rem 0.85rem; margin: 0 0.5rem 0.2rem 0.5rem; color: #4B5E78; font-weight: 500; display: flex; align-items: center; justify-content: space-between; font-size: 0.85rem; border-radius: 6px; border-left: 3px solid transparent;">
                <span>{label}</span>
                {lock_svg}
            </div>
            """
            st.sidebar.markdown(clean_html(disabled_html), unsafe_allow_html=True)
        else:
            if st.sidebar.button(label, key=f"nav_btn_{label}", use_container_width=True):
                from ui.components import clear_operation
                clear_operation()
                st.session_state.current_page = label
                st.rerun()

def render_sidebar():
    init_navigation()

    st.sidebar.markdown(clean_html(logo_html()), unsafe_allow_html=True)

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

    # Calculate total rows across tables
    total_rows = 0
    any_rows = False
    if ws.registry:
        for meta in ws.registry.values():
            if hasattr(meta, 'row_count') and meta.row_count is not None:
                total_rows += meta.row_count
                any_rows = True

    # Calculate global status
    status_text = "Ready"
    status_level = "success"

    if tables == 0:
        status_text = "Not Initialized"
        status_level = "neutral"
    elif st.session_state.get("analysis_results"):
        issues = st.session_state.analysis_results.get("issues", [])
        if any(getattr(i, "severity", None) in ("ERROR", "CRITICAL") for i in issues):
            status_text = "Blocked"
            status_level = "error"
        elif any(getattr(i, "severity", None) in ("WARNING", "WARN") for i in issues):
            status_text = "Needs Review"
            status_level = "warning"

    project_title = "Active Project"
    if tables > 0:
        first_table = list(ws.registry.keys())[0]
        project_title = f"{first_table.capitalize()}" + (" & Related" if tables > 1 else "")

    rows_pill = f"<div style='font-size: 0.85rem;'><span style='color: var(--text-secondary); margin-right: 0.25rem;'>Rows:</span> <b style='color: var(--text-primary);'>{total_rows:,}</b></div>" if any_rows else ""

    header_html = (
        f"<div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.25rem; background: var(--surface); padding: 0.85rem 1.25rem; border-radius: 12px; border: 1px solid var(--border);'>"
        f"<div style='display: flex; align-items: center; gap: 0.75rem;'>"
        f"<div style='width: 38px; height: 38px; border-radius: 10px; background: rgba(56, 103, 255, 0.12); border: 1px solid rgba(56, 103, 255, 0.25); display: flex; align-items: center; justify-content: center; color: var(--primary);'>"
        f"<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z'/></svg>"
        f"</div>"
        f"<div>"
        f"<div style='font-size: 1.05rem; font-weight: 750; color: var(--text-primary); letter-spacing: -0.01em;'>{project_title}</div>"
        f"<span style='color: var(--text-muted); font-size: 0.78rem;'>Project ID: <code style='color: var(--accent-cyan);'>{ws.project_root.name[:8]}</code></span>"
        f"</div>"
        f"</div>"
        f"<div style='display: flex; gap: 1.25rem; align-items: center; flex-wrap: wrap;'>"
        f"<div style='font-size: 0.85rem;'><span style='color: var(--text-secondary); margin-right: 0.5rem;'>State:</span>{badge(status_text, status_level)}</div>"
        f"<div style='font-size: 0.85rem;'><span style='color: var(--text-secondary); margin-right: 0.25rem;'>Tables:</span> <b style='color: var(--text-primary);'>{tables}</b></div>"
        f"{rows_pill}"
        f"</div>"
        f"</div>"
    )
    st.markdown(clean_html(header_html), unsafe_allow_html=True)
