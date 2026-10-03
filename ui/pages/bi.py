from ui.components import dataforge_button, run_action, empty_state
import streamlit as st
from src.workspace import ProjectWorkspace
import pandas as pd

def render_power_bi_model(ws: ProjectWorkspace):
    if 'relationship_candidates' not in st.session_state:
        empty_state('Model prerequisites are not ready', 'Analyze relationships before generating a BI model.', 'Go to Relationships', 'Relationships')
        return
    st.markdown("## Power BI Model")
    if dataforge_button("Generate Model", type="primary"):
        def _do_action():
            from src.model_generator import ModelGenerator
            mg = ModelGenerator(__import__("src.data_model", fromlist=["DataModel"]).DataModel(tables={}, relationships=[]))
            spec = mg.generate()
            st.session_state.pbimodel = spec
            st.success("Model Generated!")
        

        run_action("Generate Model", [("Generating semantic model...", _do_action)])
    if "pbimodel" in st.session_state:
        st.write(st.session_state.pbimodel)

def render_advanced_dax(ws: ProjectWorkspace):
    if not st.session_state.get('kpis'):
        empty_state('No KPIs available', 'Generate KPIs first.', 'Go to KPI Center', 'KPI Center')
        return
    st.markdown("## Advanced DAX Generator")
    if dataforge_button("Generate DAX", type="primary"):
        def _do_action():
            from src.dax_generator import DAXGenerator
            # We need KPIs to generate DAX
            if "kpis" in st.session_state:
                dg = DAXGenerator()
                measures = dg.generate_measures(st.session_state.kpis)
                st.session_state.dax_measures = measures
                st.success("DAX Generated!")
            else:
                st.warning("Generate KPIs first.")
            

        run_action("Generate DAX", [("Generating DAX measures...", _do_action)])
    if "dax_measures" in st.session_state:
        dax_df = pd.DataFrame([{
            "Measure": d.measure_name, "KPI": d.kpi_name, "Status": d.status, "DAX Expression": d.dax_expression
        } for d in st.session_state.dax_measures])
        st.dataframe(dax_df)

def render_dashboard_blueprint(ws: ProjectWorkspace):
    st.markdown("## Dashboard Blueprint")
    if dataforge_button("Generate Blueprint", type="primary"):
        def _do_action():
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
            

        run_action("Generate Blueprint", [("Architecting dashboard blueprint...", _do_action)])
    if "dashboard_blueprint" in st.session_state:
        st.write(st.session_state.dashboard_blueprint)

def render_insight_visuals(ws: ProjectWorkspace):
    if not st.session_state.get('dashboard_blueprint'):
        empty_state('No blueprint available', 'Generate a blueprint first.', 'Go to Dashboard Blueprint', 'Dashboard Blueprint')
        return
    st.markdown("## Insight -> Visual Mapping")
    if dataforge_button("Generate Mapping", type="primary"):
        def _do_action():
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
            

        from ui.components import run_action
        run_action("Generate Mapping", [("Executing", _do_action)])
    if "insight_mappings" in st.session_state:
        st.write([m.__dict__ for m in st.session_state.insight_mappings])

def render_data_lineage(ws: ProjectWorkspace):
    if not st.session_state.get('analysis_results'):
        empty_state('Lineage metadata is not available yet', 'Run a Data Quality Scan first.', 'Go to Data Quality', 'Data Quality')
        return
    st.markdown("## Data Lineage")
    st.info("Lineage graph tracking raw -> KPI.")



