import streamlit as st
from pathlib import Path
from src.workspace import ProjectWorkspace
from src.pipeline import run_pipeline
from ui.theme import card, badge, metric_card

def render_project_setup():
    st.markdown("## Project Setup")
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
                st.success("Project loaded successfully!")
                st.session_state.current_page = "Overview"
                st.rerun()

def render_overview(ws: ProjectWorkspace):
    st.markdown("## Project Overview")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Tables", str(len(ws.registry)))
    with c2: metric_card("Overall Quality", "TBD", "warning")
    with c3: metric_card("Total Issues", "TBD", "error")
    with c4: metric_card("KPIs Defined", "TBD", "success")
    
    st.markdown("### Quick Actions")
    col1, col2, col3 = st.columns(3)
    if col1.button("Run Quality Scan", type="primary", use_container_width=True):
        st.session_state.current_page = "Data Quality"
        st.rerun()
    if col2.button("Analyze Relationships", use_container_width=True):
        st.session_state.current_page = "Relationships"
        st.rerun()
    if col3.button("Generate KPIs", use_container_width=True):
        st.session_state.current_page = "KPI Center"
        st.rerun()

def render_data_quality(ws: ProjectWorkspace):
    st.markdown("## Data Quality Scan")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_table = st.selectbox("Select Table", list(ws.registry.keys()))
    with col2:
        if st.button("Scan Table", type="primary", use_container_width=True):
            entry = ws.registry[selected_table]
            class LocalFileMock:
                def __init__(self, path):
                    from pathlib import Path
                    self.path = Path(path)
                    self.name = self.path.name
                    self.size = self.path.stat().st_size
                def getvalue(self):
                    return self.path.read_bytes()
            target_file = LocalFileMock(entry.file_path)
            with st.spinner(f"Scanning {target_file.name}..."):
                success, err = run_pipeline(target_file, None)
                if success:
                    st.success("Scan completed.")
                    ws.mark_analyzed(selected_table)
                else:
                    st.error(f"Scan failed: {err}")

    if st.session_state.get("analysis_results"):
        st.success("Results available in memory. View Issues for details.")

def render_issues(ws: ProjectWorkspace):
    st.markdown("## Issues")
    if not st.session_state.get("analysis_results"):
        st.info("Run a Quality Scan first.")
        return
        
    res = st.session_state.analysis_results
    if not res.get("issues"):
        st.success("No issues found!")
        return
        
    st.markdown(f"Found {len(res['issues'])} issues.")
    issue_data = []
    for issue in res['issues']:
        issue_data.append({
            "Issue ID": issue.issue_id,
            "Severity": issue.severity,
            "Type": issue.issue_type,
            "Column": issue.column,
            "Rows Affected": issue.affected_count,
            "Description": issue.description
        })
    st.dataframe(issue_data, use_container_width=True)

def render_cleaning(ws: ProjectWorkspace):
    st.markdown("## Data Cleaning & Repair")
    if not st.session_state.get("analysis_results"):
        st.info("Run a Quality Scan first.")
        return
        
    res = st.session_state.analysis_results
    if not res.get("proposals"):
        st.success("No repairs needed.")
        return
        
    st.markdown(f"Generated {len(res['proposals'])} repair proposals.")
    
    if st.button("Approve Safe Fixes"):
        from src.repair_engine import RepairEngine
        re = RepairEngine()
        instructions = [p.to_repair_instruction() for p in res["proposals"] if p.approval_state.value == "APPROVED"]
        
        with st.spinner("Applying repairs..."):
            repaired_df, repair_res = re.apply(res["df"], instructions)
            res["repaired_df"] = repaired_df
            res["repair_results"] = repair_res
            st.success("Repairs applied.")

def render_validation(ws: ProjectWorkspace):
    st.markdown("## Validation Results")
    if not st.session_state.get("analysis_results"):
        st.info("Run a Quality Scan first.")
        return
        
    res = st.session_state.analysis_results
    if res.get("after_snapshot"):
        st.success("Validation completed.")
        st.write(f"Readiness Score: {res['comparison_result'].after_readiness}%")
    elif res.get("before_snapshot"):
        st.write(f"Initial Readiness Score: {res['before_snapshot'].readiness.overall_score}%")
    else:
        st.info("No validation snapshot found.")
