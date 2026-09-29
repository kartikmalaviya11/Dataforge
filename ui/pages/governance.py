import streamlit as st
from src.workspace import ProjectWorkspace

def render_run_history(ws: ProjectWorkspace):
    st.markdown("## Run History")
    from src.run_history import RunHistoryManager
    hm = RunHistoryManager(ws.project_root)
    runs = hm.get_all_runs()
    if not runs:
        st.info("No runs logged yet.")
    else:
        st.write(runs)

def render_dataset_versions(ws: ProjectWorkspace):
    st.markdown("## Dataset Versions")
    from src.dataset_versioning import DatasetVersioningManager
    vm = DatasetVersioningManager(ws.project_root)
    versions = vm.get_all_versions()
    if not versions:
        st.info("No versions logged yet.")
    else:
        st.write(versions)

def render_readiness(ws: ProjectWorkspace):
    st.markdown("## Historical Readiness")
    from src.historical_readiness import HistoricalReadinessManager
    rm = HistoricalReadinessManager(ws.project_root)
    snapshots = rm.get_all()
    if not snapshots:
        st.info("No snapshots logged yet.")
    else:
        st.write(snapshots)

def render_assumptions(ws: ProjectWorkspace):
    if st.button("Register Assumption", type="primary"):
        st.success("Registered")
    st.markdown("## Assumptions Register")
    from src.assumption_register import AssumptionRegisterManager
    ar = AssumptionRegisterManager(ws.project_root)
    assumptions = ar.get_all()
    if not assumptions:
        st.info("No assumptions registered.")
    else:
        st.write(assumptions)

def render_business_impact(ws: ProjectWorkspace):
    if st.button("Map Impact", type="primary"):
        st.success("Impact Mapped")
    st.markdown("## Business Impact")
    from src.business_impact import BusinessImpactManager
    bim = BusinessImpactManager(ws.project_root)
    impacts = bim.get_all()
    if not impacts:
        st.info("No business impacts registered.")
    else:
        st.write(impacts)

def render_documentation(ws: ProjectWorkspace):
    st.markdown("## Documentation Generator")
    if st.button("Generate All Docs", type="primary"):
        from src.documentation_generator import DocumentationGenerator
        dg = DocumentationGenerator(__import__("os").path.join(ws.project_root, ".dataforge", "docs"))
        dg.generate_all({})
        st.success("Documentation Generated in `.dataforge/docs/`")

def render_export_package(ws: ProjectWorkspace):
    st.markdown("## Export Package")
    if st.button("Build Export Package", type="primary"):
        from src.project_export import ProjectExportManager
        em = ProjectExportManager(__import__("os").path.join(ws.project_root, ".dataforge", "export"))
        out = em.generate_package({})
        st.success(f"Exported to {out}")

