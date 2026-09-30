import streamlit as st
from ui.theme import apply_theme
from ui.layout import render_sidebar, render_global_header
from ui.pages.project import (
    render_overview, render_data_import, render_data_quality, 
    render_issues, render_cleaning, render_validation
)
from ui.pages.analysis import (
    render_relationships, render_feature_engineering, render_sql_workspace,
    render_pandas_analysis, render_kpi_center, render_business_questions,
    render_segmentation, render_anomaly_detection, render_date_analysis,
    render_rca, render_findings, render_recommendations
)
from ui.pages.bi import (
    render_power_bi_model, render_advanced_dax, render_dashboard_blueprint,
    render_insight_visuals, render_data_lineage
)
from ui.pages.governance import (
    render_run_history, render_dataset_versions, render_readiness,
    render_assumptions, render_business_impact, render_documentation,
    render_export_package
)
from ui.pages.tools import render_domain_templates, render_settings

# Set page config and apply global CSS
apply_theme()

# Render Sidebar Navigation
current_page = render_sidebar()

# Main Content Routing
if current_page == "Data Import":
    render_data_import()
else:
    if "workspace" in st.session_state:
        ws = st.session_state.workspace
        render_global_header(ws)
        
        # Route to the correct page
        if current_page == "Overview":
            render_overview(ws)
        elif current_page == "Data Quality":
            render_data_quality(ws)
        elif current_page == "Issues":
            render_issues(ws)
        elif current_page == "Cleaning":
            render_cleaning(ws)
        elif current_page == "Validation":
            render_validation(ws)
            
        elif current_page == "Relationships":
            render_relationships(ws)
        elif current_page == "Feature Engineering":
            render_feature_engineering(ws)
        elif current_page == "SQL Workspace":
            render_sql_workspace(ws)
        elif current_page == "Pandas Analysis":
            render_pandas_analysis(ws)
        elif current_page == "KPI Center":
            render_kpi_center(ws)
        elif current_page == "Business Questions":
            render_business_questions(ws)
        elif current_page == "Segmentation":
            render_segmentation(ws)
        elif current_page == "Anomaly Detection":
            render_anomaly_detection(ws)
        elif current_page == "Date Analysis":
            render_date_analysis(ws)
        elif current_page == "RCA":
            render_rca(ws)
        elif current_page == "Findings":
            render_findings(ws)
        elif current_page == "Recommendations":
            render_recommendations(ws)
            
        elif current_page == "Power BI Model":
            render_power_bi_model(ws)
        elif current_page == "Advanced DAX":
            render_advanced_dax(ws)
        elif current_page == "Dashboard Blueprint":
            render_dashboard_blueprint(ws)
        elif current_page == "Insight Visuals":
            render_insight_visuals(ws)
        elif current_page == "Data Lineage":
            render_data_lineage(ws)
            
        elif current_page == "Run History":
            render_run_history(ws)
        elif current_page == "Dataset Versions":
            render_dataset_versions(ws)
        elif current_page == "Readiness":
            render_readiness(ws)
        elif current_page == "Assumptions":
            render_assumptions(ws)
        elif current_page == "Business Impact":
            render_business_impact(ws)
        elif current_page == "Documentation":
            render_documentation(ws)
        elif current_page == "Export Package":
            render_export_package(ws)
            
        elif current_page == "Domain Templates":
            render_domain_templates(ws)
        elif current_page == "Settings":
            render_settings(ws)
        else:
            st.info(f"Page '{current_page}' is under construction.")
    else:
        st.warning("Please load a project first in 'Project Setup'.")
