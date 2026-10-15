from ui.components import dataforge_button, run_action, empty_state
import streamlit as st
from src.workspace import ProjectWorkspace

def render_run_history(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Run History</h2>
    </div>
    ''', unsafe_allow_html=True)
    from src.run_history import RunHistoryManager
    hm = RunHistoryManager(ws.project_root)
    runs = hm.get_all_runs()
    if not runs:
        st.info("No runs logged yet.")
    else:
        import pandas as pd
        st.dataframe(pd.DataFrame([r.__dict__ for r in runs]))

def render_dataset_versions(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Dataset Versions</h2>
    </div>
    ''', unsafe_allow_html=True)
    from src.dataset_versioning import DatasetVersioningManager, DatasetVersion
    import uuid, datetime

    vm = DatasetVersioningManager(ws.project_root)
    versions = vm.get_all_versions()

    if dataforge_button("Create Snapshot", type="primary"):
        def _do_action():
            tables = list(ws.registry.keys())
            if not tables:
                st.error("No tables in workspace to snapshot.")
                return

            for t in tables:
                df, _ = ws.load_table(t)
                # Compute mock SHA for df
                import hashlib
                sha = hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values).hexdigest()

                dv = DatasetVersion(
                    version_id=str(uuid.uuid4()),
                    dataset_name=t,
                    version_tag=f"v_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                    created_at=datetime.datetime.now(datetime.UTC).isoformat(),
                    sha256_hash=sha,
                    row_count=len(df),
                    column_count=len(df.columns)
                )
                vm.register_version(dv)
            st.success(f"Snapshot created for {len(tables)} tables.")

        run_action("Create Snapshot", [("Saving version state...", _do_action)])

    versions = vm.get_all_versions() # Refresh
    if not versions:
        st.info("No versions logged yet.")
    else:
        st.dataframe(pd.DataFrame([v.__dict__ for v in versions]))

def render_readiness(ws: ProjectWorkspace):
    if not st.session_state.get('table_results'):
        empty_state('No analyzed dataset available', 'Run a Data Quality Scan first.', 'Go to Data Quality', 'Data Quality')
        return
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Historical Readiness</h2>
    </div>
    ''', unsafe_allow_html=True)
    from src.historical_readiness import HistoricalReadinessManager
    rm = HistoricalReadinessManager(ws.project_root)
    snapshots = rm.get_all()
    if not snapshots:
        st.info("No snapshots logged yet.")
    else:
        import pandas as pd
        st.dataframe(pd.DataFrame([s.__dict__ for s in snapshots]))

def render_assumptions(ws: ProjectWorkspace):
    import streamlit as st
    import pandas as pd
    from src.assumption_register import AssumptionRegisterManager

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Assumptions Register</h2>
    </div>
    ''', unsafe_allow_html=True)

    ar = AssumptionRegisterManager(ws.project_root)

    with st.expander("Register New Assumption", expanded=True):
        with st.form("assumption_form", clear_on_submit=False):
            title = st.text_input("Assumption Title *", placeholder="e.g., Currency values normalized to USD", key="assump_title")
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("Category", [
                    "Data Quality", "Business Logic", "Pipeline / ETL", "Statistical Model", "Regulatory / Compliance"
                ], key="assump_cat")
                risk = st.selectbox("Risk Level", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], key="assump_risk")
            with col2:
                available_targets = list(ws.registry.keys())
                kpis = st.session_state.get("kpis", [])
                for k in kpis:
                    k_name = getattr(k, "kpi_name", k.get("kpi_name", "") if isinstance(k, dict) else "")
                    if k_name and k_name not in available_targets:
                        available_targets.append(k_name)
                used_in = st.multiselect("Used In (Tables / KPIs)", available_targets, key="assump_used_in")
                reason = st.text_input("Justification / Source", placeholder="e.g., Confirmed with domain team", key="assump_reason")

            description = st.text_area("Detailed Description *", placeholder="Explain the rationale, constraints, and impact if this assumption is violated...", key="assump_desc")

            submitted = st.form_submit_button("Register Assumption", type="primary")
            if submitted:
                if not title.strip() or not description.strip():
                    st.error("Both 'Assumption Title' and 'Detailed Description' are required. Assumption was not registered.")
                else:
                    try:
                        a_id = ar.create(
                            title=title.strip(),
                            description=description.strip(),
                            reason=reason.strip() if reason.strip() else category,
                            risk=risk,
                            used_in=used_in
                        )
                        st.session_state.assumption_saved_banner = f"Assumption '{title.strip()}' registered successfully (ID: {a_id})."
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to register assumption: {e}")

    if st.session_state.get("assumption_saved_banner"):
        st.success(st.session_state.assumption_saved_banner)

    assumptions = ar.get_all()
    st.markdown("### Registered Project Assumptions")
    if not assumptions:
        st.info("No assumptions registered yet. Use the form above to document key project assumptions.")
    else:
        st.dataframe(pd.DataFrame([a.__dict__ for a in assumptions]), use_container_width=True)

def render_business_impact(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Business Impact</h2>
    </div>
    ''', unsafe_allow_html=True)

    kpis = st.session_state.get('kpis', [])
    if not kpis:
        empty_state("No KPIs available", "Generate KPIs first.", "Go to KPI Center", "KPI Center")
        return

    all_issues = []
    for t_res in st.session_state.get('table_results', {}).values():
        all_issues.extend(t_res.get('all_issues', []))

    if not all_issues:
        empty_state("No Quality Issues", "No quality issues found to map.", "Go to Data Quality", "Data Quality")
        return

    from src.business_impact import BusinessImpactManager, BusinessImpact
    import datetime

    bim = BusinessImpactManager(ws.project_root)
    impacts = bim.get_all()
    if not impacts:
        st.info("No business impacts registered.")
    else:
        st.dataframe(pd.DataFrame([i.__dict__ for i in impacts]))

    st.markdown("### Map Issue to KPI")
    issue_options = {i.issue_id: f"{i.table_name}.{i.column_name}: {i.issue_type}" for i in all_issues}
    issue_id = st.selectbox("Select Quality Issue", list(issue_options.keys()), format_func=lambda x: issue_options[x], key="bi_issue")

    kpi_options = {k.kpi_id: k.name for k in kpis}
    kpi_id = st.selectbox("Select Affected KPI", list(kpi_options.keys()), format_func=lambda x: kpi_options[x], key="bi_kpi")

    desc = st.text_area("Impact Description", key="bi_desc")

    if dataforge_button("Map Impact", type="primary"):
        def _do_action():
            if not desc:
                st.error("Please provide a description.")
                return

            selected_issue = next(i for i in all_issues if i.issue_id == issue_id)
            bi = BusinessImpact(
                issue_id=issue_id,
                affected_records=selected_issue.affected_count,
                affected_kpi=kpi_options[kpi_id],
                business_impact_description=desc,
                evidence=f"Detected {selected_issue.affected_count} records with {selected_issue.issue_type}",
                status="POTENTIAL_IMPACT",
                created_at=datetime.datetime.now(datetime.UTC).isoformat()
            )
            bim.register_impact(bi)
            st.success("Impact Mapped and Registered")

        run_action("Map Impact", [("Mapping business impact...", _do_action)])

def render_documentation(ws: ProjectWorkspace):
    if not st.session_state.get('table_results'):
        empty_state('Documentation requires project metadata', 'Run a Data Quality Scan first.', 'Go to Data Quality', 'Data Quality')
        return
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Documentation Generator</h2>
    </div>
    ''', unsafe_allow_html=True)
    if dataforge_button("Generate All Docs", type="primary"):
        def _do_action():
            import os
            from src.documentation_generator import DocumentationGenerator
            docs_dir = os.path.join(ws.project_root, ".dataforge", "docs")
            dg = DocumentationGenerator(docs_dir)
            meta = dg.compile_project_metadata(
                workspace=ws,
                table_results=st.session_state.get("table_results"),
                kpis=st.session_state.get("kpis")
            )
            dg.generate_all(meta)
            st.session_state.docs_generated_banner = True

        run_action("Generate All Docs", [("Compiling project documentation...", _do_action)])

    if st.session_state.get("docs_generated_banner"):
        st.success("Documentation Generated in `.dataforge/docs/`")

def render_export_package(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Export Package</h2>
    </div>
    ''', unsafe_allow_html=True)
    if dataforge_button("Build Export Package", type="primary"):
        def _do_action():
            from src.project_export import ProjectExportManager
            em = ProjectExportManager(__import__("os").path.join(ws.project_root, ".dataforge", "export"))
            out = em.generate_package(workspace=ws)
            st.session_state.export_package_path = out

        run_action("Build Export Package", [("Bundling export package...", _do_action)])

    if st.session_state.get("export_package_path"):
        st.success(f"Exported to {st.session_state.export_package_path}")