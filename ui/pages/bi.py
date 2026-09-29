import streamlit as st
from src.workspace import ProjectWorkspace
import pandas as pd

def render_power_bi_model(ws: ProjectWorkspace):
    st.markdown("## Power BI Model")
    if st.button("Generate Model", type="primary"):
        from src.model_generator import ModelGenerator
        mg = ModelGenerator(__import__("src.data_model", fromlist=["DataModel"]).DataModel(tables={}, relationships=[]))
        spec = mg.generate()
        st.session_state.pbimodel = spec
        st.success("Model Generated!")
        
    if "pbimodel" in st.session_state:
        st.write(st.session_state.pbimodel)

def render_advanced_dax(ws: ProjectWorkspace):
    st.markdown("## Advanced DAX Generator")
    if st.button("Generate DAX", type="primary"):
        from src.dax_generator import DAXGenerator
        # We need KPIs to generate DAX
        if "kpis" in st.session_state:
            dg = DAXGenerator()
            measures = dg.generate_measures(st.session_state.kpis)
            st.session_state.dax_measures = measures
            st.success("DAX Generated!")
        else:
            st.warning("Generate KPIs first.")
            
    if "dax_measures" in st.session_state:
        dax_df = pd.DataFrame([{
            "Measure": d.measure_name, "KPI": d.kpi_name, "Status": d.status, "DAX Expression": d.dax_expression
        } for d in st.session_state.dax_measures])
        st.dataframe(dax_df)

def render_dashboard_blueprint(ws: ProjectWorkspace):
    st.markdown("## Dashboard Blueprint")
    if st.button("Generate Blueprint", type="primary"):
        try:
            from src.dashboard_blueprint import DashboardBlueprintManager
            mgr = DashboardBlueprintManager(str(ws.project_root))
            # Use kpis from session if available, else empty list
            import dataclasses; kpis = [dataclasses.asdict(k) for k in st.session_state.get("kpis", [])]
            questions = []
            blueprint = mgr.generate_blueprint("Main Dashboard", kpis, questions)
            st.session_state.dashboard_blueprint = blueprint
            st.success("Blueprint Generated")
        except ImportError:
            st.error("Backend not implemented yet.")
        except Exception as e:
            st.error(f"Error: {e}")
            
    if "dashboard_blueprint" in st.session_state:
        st.write(st.session_state.dashboard_blueprint)

def render_insight_visuals(ws: ProjectWorkspace):
    st.markdown("## Insight -> Visual Mapping")
    if st.button("Generate Mapping", type="primary"):
        try:
            from src.insight_mapping import InsightVisualMapper
            from src.finding_engine import FindingEngine
            
            fe = FindingEngine(ws)
            findings = fe.load_findings()
            mapper = InsightVisualMapper(ws)
            mappings = [mapper.generate_mapping(f) for f in findings]
            st.session_state.insight_mappings = mappings
            st.success("Mapping Generated")
        except ImportError:
            st.error("Backend not implemented yet.")
            
    if "insight_mappings" in st.session_state:
        st.write([m.__dict__ for m in st.session_state.insight_mappings])

def render_data_lineage(ws: ProjectWorkspace):
    st.markdown("## Data Lineage")
    st.info("Lineage graph tracking raw -> KPI.")



