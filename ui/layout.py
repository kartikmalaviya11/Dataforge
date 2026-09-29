import streamlit as st
from pathlib import Path
from src.workspace import ProjectWorkspace
from ui.theme import badge, metric_card

def init_navigation():
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Project Setup"

def nav_button(label: str):
    is_active = st.session_state.current_page == label
    if is_active:
        st.sidebar.markdown(f"**> {label}**")
    else:
        if st.sidebar.button(label, key=f"nav_btn_{label}", use_container_width=True):
            st.session_state.current_page = label
            st.rerun()

def render_sidebar():
    init_navigation()
    st.sidebar.markdown("## 📊 DATAFORGE")
    
    # Project Setup
    st.sidebar.markdown("---")
    if "workspace" not in st.session_state:
        nav_button("Project Setup")
        return st.session_state.current_page
        
    st.sidebar.markdown("<small style='color:gray'>PROJECT</small>", unsafe_allow_html=True)
    for p in ["Overview", "Data Quality", "Issues", "Cleaning", "Validation"]:
        nav_button(p)
        
    st.sidebar.markdown("<small style='color:gray'>ANALYSIS</small>", unsafe_allow_html=True)
    for p in ["Relationships", "Feature Engineering", "SQL Workspace", "Pandas Analysis", 
              "KPI Center", "Business Questions", "Segmentation", "Anomaly Detection", 
              "Date Analysis", "RCA", "Findings", "Recommendations"]:
        nav_button(p)

    st.sidebar.markdown("<small style='color:gray'>BI</small>", unsafe_allow_html=True)
    for p in ["Power BI Model", "Advanced DAX", "Dashboard Blueprint", "Insight Visuals", "Data Lineage"]:
        nav_button(p)

    st.sidebar.markdown("<small style='color:gray'>GOVERNANCE</small>", unsafe_allow_html=True)
    for p in ["Run History", "Dataset Versions", "Readiness", "Assumptions", 
              "Business Impact", "Documentation", "Export Package"]:
        nav_button(p)

    st.sidebar.markdown("<small style='color:gray'>TOOLS</small>", unsafe_allow_html=True)
    for p in ["Domain Templates", "Settings"]:
        nav_button(p)

    return st.session_state.current_page

def render_global_header(ws: ProjectWorkspace):
    tables = len(ws.registry) if ws.registry else 0
    
    st.markdown(f"### Project: {ws.project_root.name}")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"**Tables:** {tables}")
    with col2:
        st.markdown(f"**Quality:** {badge('TBD', 'neutral')}", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**Relationships:** {badge('TBD', 'neutral')}", unsafe_allow_html=True)
    with col4:
        st.markdown(f"**Findings:** {badge('TBD', 'neutral')}", unsafe_allow_html=True)
    with col5:
        st.markdown(f"**Readiness:** {badge('TBD', 'neutral')}", unsafe_allow_html=True)
    
    st.markdown("---")
