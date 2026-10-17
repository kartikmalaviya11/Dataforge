from ui.theme import clean_html
from ui.components import dataforge_button, run_action, empty_state
import streamlit as st
from src.workspace import ProjectWorkspace
import pandas as pd

def render_power_bi_model(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    if 'relationship_candidates' not in st.session_state:
        empty_state('Model prerequisites are not ready', 'Analyze relationships before generating a BI model.', 'Go to Relationships', 'Relationships')
        return

    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Power BI Model</h2>
    </div>
    '''), unsafe_allow_html=True)

    if dataforge_button("Generate Model", type="primary"):
        def _do_action():
            from src.model_generator import ModelGenerator
            from src.data_model import DataModel, TableSchema, ColumnSchema

            # Build DataModel
            tables = {}
            for tname in ws.registry.keys():
                df, _ = ws.load_table(tname)
                cols = {}
                for c in df.columns:
                    is_uniq = bool(len(df) > 0 and df[c].nunique(dropna=False) == len(df))
                    cols[c] = ColumnSchema(name=c, type=str(df[c].dtype), is_unique=is_uniq)
                tables[tname] = TableSchema(name=tname, row_count=len(df), columns=cols)

            accepted_rels = [r for r in st.session_state.relationship_candidates if r.status == "ACCEPTED"]

            dm = DataModel(tables=tables, relationships=accepted_rels)
            mg = ModelGenerator(dm)

            try:
                import os
                spec = mg.generate()
                st.session_state.pbimodel = spec
                try:
                    mg.save_specification(spec, base_path=os.path.join(ws.project_root, ".dataforge"))
                except Exception:
                    pass
                st.success("Power BI Semantic Model Generated!")
            except Exception as e:
                st.error(f"Failed to generate model: {e}")

        run_action("Generate Model", [("Generating semantic model...", _do_action)])

    if "pbimodel" in st.session_state:
        st.json(st.session_state.pbimodel.__dict__)

def render_advanced_dax(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    import os
    from ui.components import dataforge_button, run_action, empty_state
    from src.model_generator import ModelGenerator
    from src.data_model import DataModel, TableSchema, ColumnSchema

    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">DAX Generation</h2>
    </div>
    '''), unsafe_allow_html=True)

    base_dataforge = os.path.join(ws.project_root, ".dataforge")
    if "dax_measures" not in st.session_state:
        persisted_measures = ModelGenerator.load_dax_measures(base_dataforge)
        if persisted_measures:
            st.session_state.dax_measures = persisted_measures

    kpis = st.session_state.get('kpis')
    if not kpis:
        try:
            from src.kpi_engine import KPIManager
            km = KPIManager(ws)
            kpis = km.load_kpis()
            if kpis:
                st.session_state.kpis = kpis
        except Exception:
            pass

    if not kpis and "dax_measures" not in st.session_state:
        empty_state("No KPIs", "Generate KPIs first to create DAX measures.", "Go to KPI Center", "KPI Center")
        return

    if dataforge_button("Generate DAX", type="primary"):
        def _do_action():
            try:
                import dataclasses

                # Build actual supported project model
                tables = {}
                for tname in ws.registry.keys():
                    df, _ = ws.load_table(tname)
                    if df is not None:
                        cols = {
                            c: ColumnSchema(name=c, type=str(df[c].dtype), is_unique=bool(len(df) > 0 and df[c].nunique(dropna=False) == len(df)))
                            for c in df.columns
                        }
                        tables[tname] = TableSchema(name=tname, row_count=len(df), columns=cols)

                candidates = st.session_state.get("relationship_candidates", [])
                accepted_rels = [r for r in candidates if getattr(r, "status", None) == "ACCEPTED"]
                dm = DataModel(tables=tables, relationships=accepted_rels)

                mg = ModelGenerator(dm)
                kpi_items = [dataclasses.asdict(k) if dataclasses.is_dataclass(k) else k for k in kpis] if kpis else []

                dax_measures = mg.generate_dax_measures(kpi_items)
                mg.save_dax_measures(dax_measures, base_path=base_dataforge)
                st.session_state.dax_measures = dax_measures
                st.session_state.dax_measures_banner = f"Generated and saved {len(dax_measures)} DAX measures."
            except Exception as e:
                st.error(f"Error: {e}")

        run_action("Generate DAX", [("Writing DAX...", _do_action)])

    if st.session_state.get("dax_measures_banner"):
        st.success(st.session_state.dax_measures_banner)

    if "dax_measures" in st.session_state and st.session_state.dax_measures:
        for m in st.session_state.dax_measures:
            st.code(f"""{m['measure_name']} =
{m['dax_expression']}""", language="dax")
            st.caption(f"Table: {m['table']} | Format: {m['format_string']}")

def render_dashboard_blueprint(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Dashboard Blueprint</h2>
    </div>
    '''), unsafe_allow_html=True)

    kpis = st.session_state.get('kpis')
    if not kpis:
        empty_state("No KPIs", "Generate KPIs first to create a dashboard blueprint.", "Go to KPI Center", "KPI Center")
        return

    if dataforge_button("Generate Blueprint", type="primary"):
        def _do_action():
            from src.dashboard_blueprint import DashboardBlueprintManager
            import dataclasses

            mgr = DashboardBlueprintManager(str(ws.project_root))
            kpi_dicts = [dataclasses.asdict(k) for k in kpis]

            try:
                blueprint = mgr.generate_blueprint("Main Dashboard", kpi_dicts, [])
                st.session_state.dashboard_blueprint = blueprint
                st.success("Blueprint Generated")
            except Exception as e:
                st.error(f"Error: {e}")

        run_action("Generate Blueprint", [("Structuring layout...", _do_action)])

    if "dashboard_blueprint" in st.session_state:
        bp = st.session_state.dashboard_blueprint
        st.write(f"**{bp.title}**")
        st.write("Pages:", len(bp.pages))
        for p in bp.pages:
            with st.expander(f"Page: {p.title}"):
                for v in p.visuals:
                    st.write(f"- {v.type}: {v.title}")

def render_insight_visuals(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Insight -> Visual Mapping</h2>
    </div>
    '''), unsafe_allow_html=True)

    from src.finding_engine import FindingEngine
    fe = FindingEngine(ws)
    findings = fe.load_findings()

    if not findings:
        empty_state("No Findings Available", "Record insights in the Analysis page first.", "Go to Findings", "Findings")
        return

    if dataforge_button("Generate Mapping", type="primary"):
        def _do_action():
            from src.insight_mapping import InsightVisualMapper
            mapper = InsightVisualMapper(ws)
            mappings = [mapper.generate_mapping(f) for f in findings]
            st.session_state.insight_mappings = mappings
            st.success(f"Generated visual mappings for {len(mappings)} findings.")

        run_action("Generate Mapping", [("Analyzing finding semantics...", _do_action)])

    if "insight_mappings" in st.session_state:
        df = pd.DataFrame([m.__dict__ for m in st.session_state.insight_mappings])
        st.dataframe(df)

def render_data_lineage(ws: ProjectWorkspace):
    if not st.session_state.get('table_results'):
        empty_state('Lineage metadata is not available yet', 'Run a Data Quality Scan first.', 'Go to Data Quality', 'Data Quality')
        return
    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Data Lineage</h2>
    </div>
    '''), unsafe_allow_html=True)
    from src.dataset_versioning import DatasetVersioningManager
    dvm = DatasetVersioningManager(ws.project_root)
    versions = dvm.get_all_versions()

    if not versions:
        st.info("No lineage operations have been recorded yet.")
        return

    edges = []
    nodes = []

    for v in versions:
        # Build node text
        op = "Scan" if v.version_type == "RAW" else v.change_summary.get("operation", "Transform")
        label = f"[{v.version_id[:6]}] {v.version_type}\n({v.row_count} rows)"
        nodes.append((v.version_id, label))

        if v.parent_version_id:
            edges.append((v.parent_version_id, v.version_id, op))

    # Try to use graphviz if available, else fallback to text
    try:
        import graphviz
        graph = graphviz.Digraph(
            node_attr={'shape': 'box', 'style': 'rounded,filled', 'fillcolor': '#10233D', 'fontcolor': '#F4F7FF', 'color': '#3867FF', 'fontname': 'sans-serif'},
            edge_attr={'color': '#3867FF', 'fontcolor': '#9AAAC2', 'fontname': 'sans-serif', 'fontsize': '9'}
        )
        for n_id, label in nodes:
            graph.node(n_id, label)
        for src, dst, op in edges:
            graph.edge(src, dst, label=op)
        st.graphviz_chart(graph)
    except ImportError:
        st.warning("Graphviz not installed. Displaying lineage as a table.")
        import pandas as pd
        lineage_data = [{"Version ID": n_id, "Parent ID": v.parent_version_id, "Type": v.version_type, "Operation": v.change_summary.get("operation", "RAW")} for n_id, label in nodes for v in versions if v.version_id == n_id]
        st.dataframe(pd.DataFrame(lineage_data))

    st.info("Note: Only dataset-level lineage tracking (Scan/Cleaning) is currently supported in this view.")



