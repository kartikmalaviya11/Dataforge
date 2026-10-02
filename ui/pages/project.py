from ui.components import dataforge_button, run_action, empty_state


def render_data_import():
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])

    with c2:
        with st.container(border=True):
            st.markdown(f"""
            <div style="text-align: center; margin-bottom: 1.5rem; margin-top: 1rem;">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1D4ED8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 0.5rem;">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                    <polyline points="2 17 12 22 22 17"></polyline>
                    <polyline points="2 12 12 17 22 12"></polyline>
                </svg>
                <h2 style="margin: 0; padding: 0;">DATAFORGE</h2>
                <div style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;">Professional Data Analytics Workspace</div>
            </div>

            <h3 style="text-align: center; margin-bottom: 0.5rem; font-size: 1.25rem;">Upload Your Data</h3>
            """, unsafe_allow_html=True)

            if "uploader_key" not in st.session_state:
                st.session_state.uploader_key = 0

            import os
            is_testing = os.getenv("DATAFORGE_TESTING") == "1"
            allowed_types = ["csv", "xlsx", "xls"] if not is_testing else None

            uploaded_files = st.file_uploader(
                "Drag & Drop Files Here",
                type=allowed_types,
                accept_multiple_files=True,
                key=f"uploader_{st.session_state.uploader_key}",
                label_visibility="collapsed"
            )

            st.markdown(
                "<div style='color: var(--text-secondary); font-size: 0.85rem; text-align: center; margin-top: -1rem; margin-bottom: 1rem;'>"
                "Supported: CSV &bull; XLSX &bull; XLS"
                "</div>", unsafe_allow_html=True
            )

            if "removed_files" not in st.session_state:
                st.session_state.removed_files = set()

            active_files = [f for f in uploaded_files if f.name not in st.session_state.removed_files]

            if active_files:
                st.markdown("<div style='margin-top: 1.5rem; font-weight: 600; font-size: 0.95rem; color: var(--text-main);'>Selected Files</div>", unsafe_allow_html=True)

                # Table header
                st.markdown("""
                <div style='display: flex; color: var(--text-secondary); font-size: 0.85rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; margin-bottom: 0.5rem;'>
                    <div style='flex: 3;'>Filename</div>
                    <div style='flex: 1;'>Extension</div>
                    <div style='flex: 1;'>Size</div>
                    <div style='flex: 1;'>Status</div>
                    <div style='flex: 1;'>Action</div>
                </div>
                """, unsafe_allow_html=True)

                for f in active_files:
                    size_mb = f.size / (1024 * 1024)
                    ext = Path(f.name).suffix.upper().replace('.', '')
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"""
                        <div style='display: flex; color: var(--text-main); font-size: 0.9rem; margin-bottom: 0.25rem; align-items: center; margin-top: 0.3rem;'>
                            <div style='flex: 3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'><span style='color: var(--success); margin-right: 0.25rem;'>&check;</span> {f.name}</div>
                            <div style='flex: 1;'>{ext}</div>
                            <div style='flex: 1;'>{size_mb:.1f} MB</div>
                            <div style='flex: 1;'>Ready</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        if st.button("Remove", key=f"remove_{f.name}"):
                            st.session_state.removed_files.add(f.name)
                            st.rerun()

            st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

            b1, b2 = st.columns(2)
            if b1.button("Remove All", use_container_width=True):
                st.session_state.uploader_key += 1
                if "removed_files" in st.session_state:
                    st.session_state.removed_files.clear()
                st.rerun()
            if b2.button("Start Analysis", type="primary", use_container_width=True):
                def _validate_files():
                    pass # Done implicitly below via active_files iteration
                def _validate_exts():
                    pass
                def _validate_dups():
                    pass

                # Pre-validation (cannot be in run_action because we want st.error immediately and from ui.components import clear_operation; clear_operation(); st.stop())
                errors = []
                names = set()
                for f in active_files:
                    if f.name in names: errors.append(f"Duplicate filename: {f.name}")
                    names.add(f.name)
                    if f.size == 0: errors.append(f"File is empty: {f.name}")
                    ext = Path(f.name).suffix.lower()
                    if ext not in [".csv", ".xlsx", ".xls"]: errors.append(f"Unsupported format: {f.name}")
                if errors:
                    for e in errors: st.error(e)
                    from ui.components import clear_operation; clear_operation(); st.stop()

                import uuid, hashlib
                ws_path = Path(".dataforge_workspaces") / str(uuid.uuid4())

                def _create_ws():
                    ws_path.mkdir(parents=True, exist_ok=True)
                    return ProjectWorkspace.load(ws_path)

                def _save_raw(ws):
                    saved_count = 0
                    for f in active_files:
                        fb = f.getvalue()
                        tp = ws.project_root / f.name
                        tp.write_bytes(fb)
                        saved_count += 1
                    return saved_count

                def _verify_sha(ws):
                    for f in active_files:
                        fb = f.getvalue()
                        hb = hashlib.sha256(fb).hexdigest()
                        tp = ws.project_root / f.name
                        ha = hashlib.sha256(tp.read_bytes()).hexdigest()
                        if hb != ha: raise Exception(f"Integrity error for {f.name}: Byte match failed!")

                def _discover(ws):
                    ws.discover_datasets()

                def _register(ws):
                    # Handled implicitly by discover_datasets
                    pass

                def _load_profile(ws):
                    for tn in list(ws.registry.keys()): ws.load_table(tn)

                def _persist(ws):
                    ws.discover_datasets()
                    ws.save()

                def _prepare():
                    pass

                # Combine into stages
                # Note: run_action handles exceptions
                ws = None
                def runner():
                    nonlocal ws
                    ws = _create_ws()
                    _save_raw(ws)

                stages = [
                    ("Validate uploaded file objects", _validate_files),
                    ("Validate supported extensions", _validate_exts),
                    ("Validate duplicate filenames", _validate_dups),
                    ("Create workspace", _create_ws),
                    ("Save each raw file", runner),
                    ("Verify SHA-256 for each saved file", lambda: _verify_sha(ws)),
                    ("Discover datasets", lambda: _discover(ws)),
                    ("Register tables", lambda: _register(ws)),
                    ("Load/profile tables where actually supported", lambda: _load_profile(ws)),
                    ("Persist workspace", lambda: _persist(ws)),
                    ("Prepare Overview", _prepare),
                ]

                success, _ = run_action("Starting Analysis", stages)
                if success:
                    st.session_state.workspace = ws
                    st.session_state.current_page = "Overview"
                    st.rerun()

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        with st.expander("Advanced Project Options"):
            project_path = st.text_input("Project Folder", placeholder="e.g., C:/Data/MyProject", label_visibility="collapsed")
            if st.button("Open Existing Project", use_container_width=True):
                if not project_path:
                    st.error("Please provide a valid project folder path.")
                else:
                    pp = Path(project_path).resolve()
                    if not pp.exists():
                        st.error("Directory not found.")
                    else:
                        try:
                            ws = ProjectWorkspace.load(pp)
                            if not list(ws.registry.keys()):
                                ws.discover_datasets()
                                ws.save()
                            st.session_state.workspace = ws
                            st.session_state.current_page = "Overview"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error loading workspace: {e}")



import streamlit as st
import json
from pathlib import Path
from src.workspace import ProjectWorkspace
from ui.theme import badge, metric_card, logo_html, card

def render_overview(ws: ProjectWorkspace):
    # Gather counts safely
    tables_count = len(ws.registry) if ws.registry else 0

    total_rows = 0
    if ws.registry:
        for key, meta in ws.registry.items():
            if hasattr(meta, 'row_count') and meta.row_count is not None:
                total_rows += meta.row_count

    # Load actual metadata relationships, KPIs, findings safely
    rel_count = 0
    kpi_count = 0
    find_count = 0

    rel_path = ws.project_root / '.dataforge' / 'relationships.json'
    if rel_path.exists():
        try:
            rel_count = len(json.loads(rel_path.read_text()))
        except: pass

    kpi_path = ws.project_root / '.dataforge' / 'kpis.json'
    if kpi_path.exists():
        try:
            kpi_count = len(json.loads(kpi_path.read_text()))
        except: pass

    find_path = ws.project_root / '.dataforge' / 'findings.json'
    if find_path.exists():
        try:
            find_count = len(json.loads(find_path.read_text()))
        except: pass

    # Readiness from Phase 10 snapshot or fallback
    readiness_score = "0%"
    hr_path = ws.project_root / '.dataforge' / 'readiness_snapshots.json'
    if hr_path.exists():
        try:
            snaps = json.loads(hr_path.read_text())
            if snaps:
                readiness_score = f"{snaps[-1].get('overall_score', 0):.0f}%"
        except: pass
    elif st.session_state.get("analysis_results") and st.session_state.analysis_results.get("comparison_result"):
        readiness_score = f"{st.session_state.analysis_results['comparison_result'].after_readiness}%"

    issues_count = "0"
    quality_status = "Unknown"

    if st.session_state.get("analysis_results"):
        issues = st.session_state.analysis_results.get("issues", [])
        issues_count = str(len(issues))
        if any(i.severity == "ERROR" for i in issues):
            quality_status = "Blocked"
        elif any(i.severity == "WARNING" for i in issues):
            quality_status = "Needs Review"
        else:
            quality_status = "Ready"
    elif tables_count > 0:
        quality_status = "Not Scanned"
    else:
        quality_status = "No Tables"

    st.markdown("### Project Overview")

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Tables", str(tables_count))
    with c2: metric_card("Rows", f"{total_rows:,}" if total_rows > 0 else "0")
    with c3:
        status_color = "success" if quality_status == "Ready" else ("error" if quality_status == "Blocked" else "warning")
        metric_card("Overall Quality", quality_status, status_color)
    with c4: metric_card("Total Issues", issues_count, "error" if issues_count != "0" else "success")

    c5, c6, c7, c8 = st.columns(4)
    with c5: metric_card("Relationships", str(rel_count), "success" if rel_count > 0 else "neutral")
    with c6: metric_card("KPIs Defined", str(kpi_count), "success" if kpi_count > 0 else "neutral")
    with c7: metric_card("Findings", str(find_count), "success" if find_count > 0 else "neutral")
    with c8: metric_card("Readiness", readiness_score, "success" if readiness_score != "0%" else "neutral")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Quick Actions")
    st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)

    q1, q2, q3, q4 = st.columns(4)
    if q1.button("Run Quality Scan", type="primary", use_container_width=True):
        st.session_state.current_page = "Data Quality"
        st.rerun()
    if q2.button("Detect Relationships", use_container_width=True):
        st.session_state.current_page = "Relationships"
        st.rerun()
    if q3.button("Generate KPIs", use_container_width=True):
        st.session_state.current_page = "KPI Center"
        st.rerun()
    if q4.button("Open SQL Workspace", use_container_width=True):
        st.session_state.current_page = "SQL Workspace"
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
            from src.pipeline import run_pipeline
            def _do_scan():
                s, e = run_pipeline(target_file, None)
                if not s: raise Exception(e)
            s, _ = run_action("Scanning Table", [("Running quality scan", _do_scan)])
            if s:
                st.success("Scan completed.")
                ws.mark_analyzed(selected_table)

    if st.session_state.get("analysis_results"):
        st.success("Results available in memory. View Issues for details.")

def render_issues(ws: ProjectWorkspace):
    st.markdown("## Issues")
    if not st.session_state.get("analysis_results"):
        empty_state("No analyzed dataset available", "Run a Data Quality Scan first.", "Go to Data Quality", "Data Quality")
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
            "Description": issue.message
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(issue_data), use_container_width=True)

def render_cleaning(ws: ProjectWorkspace):
    st.markdown("## Data Cleaning & Repair")
    if not st.session_state.get("analysis_results"):
        empty_state("No analyzed dataset available", "Run a Data Quality Scan first.", "Go to Data Quality", "Data Quality")
        return

    res = st.session_state.analysis_results
    if not res.get("proposals"):
        st.success("No repairs needed.")
        return

    st.markdown(f"Generated {len(res['proposals'])} repair proposals.")

    if st.button("Approve Safe Fixes", type="primary"):
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
        empty_state("No analyzed dataset available", "Run a Data Quality Scan first.", "Go to Data Quality", "Data Quality")
        return

    res = st.session_state.analysis_results
    if res.get("after_snapshot"):
        st.success("Validation completed.")
        st.write(f"Readiness Score: {res['comparison_result'].after_readiness}%")
    elif res.get("before_snapshot"):
        st.write(f"Initial Readiness Score: {res['before_snapshot'].readiness.overall_score}%")
    else:
        st.info("No validation snapshot found.")


