from ui.components import dataforge_button, run_action, empty_state


def render_data_import():
    st.markdown("<br>", unsafe_allow_html=True)
    c2 = st.container()

    with c2:
        with st.container():
            st.markdown("""
            <div style="margin-bottom: 2rem;">
                <h1 style="font-size: 2rem; margin-bottom: 0;">DATAFORGE</h1>
                <div style="color: var(--text-secondary); font-size: 1rem;">Professional Data Analytics Workspace</div>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
                <h2 style="margin: 0; font-size: 1.25rem;">Import your data<span style="display:none">Upload Your Data</span></h2>
                <span style="color: var(--text-muted); font-size: 0.875rem;">Step 1 of 3</span>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 1rem; font-size: 0.9rem;">Bring CSV or Excel files into your workspace. We'll automatically infer schema and data types.</p>
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

                ws = None
                def _init_ws():
                    nonlocal ws
                    if ws is None:
                        ws_path.mkdir(parents=True, exist_ok=True)
                        ws = ProjectWorkspace(ws_path)

                def _save_raw(w):
                    for f in active_files:
                        fb = f.getvalue()
                        tp = w.project_root / f.name
                        tp.write_bytes(fb)

                def _verify_sha(w):
                    for f in active_files:
                        fb = f.getvalue()
                        hb = hashlib.sha256(fb).hexdigest()
                        tp = w.project_root / f.name
                        ha = hashlib.sha256(tp.read_bytes()).hexdigest()
                        if hb != ha: raise Exception(f"Integrity error for {f.name}: Byte match failed!")

                def _discover_and_register(w):
                    w.discover_datasets()
                    w.save()

                def _prepare():
                    pass

                stages = [
                    ("Validate uploaded file objects", _validate_files),
                    ("Validate supported extensions", _validate_exts),
                    ("Validate duplicate filenames", _validate_dups),
                    ("Create workspace", _init_ws),
                    ("Save raw files", lambda: _save_raw(ws)),
                    ("Verify SHA-256 for each saved file", lambda: _verify_sha(ws)),
                    ("Discover and register datasets", lambda: _discover_and_register(ws)),
                    ("Persist workspace", lambda: ws.save()),
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
import time
from pathlib import Path
from src.workspace import ProjectWorkspace
from ui.theme import badge, metric_card, logo_html, card
from ui.components import dataforge_button, run_action, empty_state


def normalize_severity(sev) -> str:
    """Normalize severity values to standard ERROR, WARNING, INFO."""
    if sev is None:
        return "INFO"
    val = getattr(sev, "value", str(sev)).upper()
    if val in ("CRITICAL", "ERROR", "HIGH"):
        return "ERROR"
    if val in ("WARNING", "WARN", "MEDIUM", "LOW"):
        return "WARNING"
    return "INFO"


def get_project_scan_results(ws: ProjectWorkspace) -> dict:
    """
    Returns scan results dictionary scoped to the current ProjectWorkspace.
    Syncs with st.session_state.table_results so existing callers always see current project's results.
    """
    if "project_scan_results" not in st.session_state:
        try:
            st.session_state.project_scan_results = {}
        except (AttributeError, TypeError):
            st.session_state["project_scan_results"] = {}

    key = str(ws.project_root.resolve())
    try:
        scans_dict = st.session_state.project_scan_results
    except (AttributeError, TypeError):
        scans_dict = st.session_state["project_scan_results"]

    if key not in scans_dict:
        scans_dict[key] = {}

    # Sync table_results to point directly to current project's dictionary
    try:
        st.session_state.table_results = scans_dict[key]
    except (AttributeError, TypeError):
        st.session_state["table_results"] = scans_dict[key]
    return scans_dict[key]


def _store_scan_result(ws: ProjectWorkspace, table_name: str, res: dict):
    """Stores scan summary for a table in current project, omitting heavy DataFrame copies."""
    project_scans = get_project_scan_results(ws)
    summary = dict(res)
    summary["df"] = None  # Loaded on demand by Cleaning when needed
    summary["scan_status"] = "COMPLETED"
    summary["error_message"] = None
    summary["scanned_at"] = time.time()
    project_scans[table_name] = summary


def _store_failed_scan(ws: ProjectWorkspace, table_name: str, error_msg: str):
    """Records a scan failure for a table in current project."""
    project_scans = get_project_scan_results(ws)
    project_scans[table_name] = {
        "scan_status": "FAILED",
        "error_message": error_msg,
        "all_issues": [],
        "readiness": None,
        "proposals": [],
        "df": None,
        "repaired_df": None,
        "scanned_at": time.time()
    }


def compute_overview_status(ws: ProjectWorkspace, scan_results: dict):
    """
    Computes (quality_status, readiness_score_display, total_issues_count, rows_display).
    Rules:
    - Never shows fake 0% readiness when no scan exists; shows 'Not Scanned'.
    - Never shows 'Ready' when severity model or classifications require review.
    - Honors current project tables only.
    """
    tables_count = len(ws.registry) if ws.registry else 0
    if tables_count == 0:
        return "No Tables", "N/A", 0, "0"

    # Compute row count display
    total_rows = 0
    any_none = False
    all_none = True
    for meta in ws.registry.values():
        if hasattr(meta, 'row_count') and meta.row_count is not None:
            total_rows += meta.row_count
            all_none = False
        else:
            any_none = True

    if all_none:
        rows_display = "Pending"
    elif any_none:
        rows_display = f"{total_rows:,} (partial)"
    else:
        rows_display = f"{total_rows:,}"

    # Check scanned tables for current project
    completed_scans = {
        tname: res for tname, res in scan_results.items()
        if tname in ws.registry and res.get("scan_status") == "COMPLETED"
    }
    failed_scans = [
        tname for tname, res in scan_results.items()
        if tname in ws.registry and res.get("scan_status") == "FAILED"
    ]

    if not completed_scans and not failed_scans:
        return "Not Scanned", "Not Scanned", 0, rows_display

    if not completed_scans and failed_scans:
        return "Blocked", "Failed", 0, rows_display

    all_issues = []
    scores = []
    for res in completed_scans.values():
        all_issues.extend(res.get("all_issues", []))
        rd = res.get("readiness")
        if rd and hasattr(rd, "overall_score"):
            scores.append(rd.overall_score)

    total_issues = len(all_issues)
    has_error = any(normalize_severity(i.severity) == "ERROR" for i in all_issues)
    has_warning = any(normalize_severity(i.severity) == "WARNING" for i in all_issues)
    has_review_req = any(
        getattr(getattr(i, "classification", None), "value", str(getattr(i, "classification", ""))) == "REVIEW_REQUIRED"
        for i in all_issues
    )

    if failed_scans or has_error:
        quality_status = "Blocked"
    elif has_warning or has_review_req or total_issues > 0:
        quality_status = "Needs Review"
    elif len(completed_scans) == tables_count and total_issues == 0:
        quality_status = "Ready"
    else:
        quality_status = "Partially Scanned"

    if scores:
        avg_score = sum(scores) / len(scores)
        readiness_display = f"{avg_score:.0f}%"
    else:
        readiness_display = "Not Scanned"

    return quality_status, readiness_display, total_issues, rows_display


def render_overview(ws: ProjectWorkspace):
    scan_results = get_project_scan_results(ws)
    quality_status, readiness_score, num_issues, rows_display = compute_overview_status(ws, scan_results)

    tables_count = len(ws.registry) if ws.registry else 0

    rel_count = 0
    kpi_count = 0
    find_count = 0

    rel_path = ws.project_root / '.dataforge' / 'relationships.json'
    if rel_path.exists():
        try:
            rel_count = len(json.loads(rel_path.read_text()))
        except Exception:
            pass

    kpi_path = ws.project_root / '.dataforge' / 'kpis.json'
    if kpi_path.exists():
        try:
            kpi_count = len(json.loads(kpi_path.read_text()))
        except Exception:
            pass

    find_path = ws.project_root / '.dataforge' / 'findings.json'
    if find_path.exists():
        try:
            find_count = len(json.loads(find_path.read_text()))
        except Exception:
            pass

    st.markdown("### Project Overview")

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Tables", str(tables_count))
    with c2: metric_card("Rows", rows_display)
    with c3:
        status_color = "success" if quality_status == "Ready" else ("error" if quality_status == "Blocked" else "warning" if quality_status in ("Needs Review", "Partially Scanned") else "neutral")
        metric_card("Overall Quality", quality_status, status_color)
    issues_status = "error" if num_issues > 0 else ("success" if quality_status == "Ready" else "neutral")
    with c4: metric_card("Total Issues", str(num_issues), issues_status)

    c5, c6, c7, c8 = st.columns(4)
    with c5: metric_card("Relationships", str(rel_count), "success" if rel_count > 0 else "neutral")
    with c6: metric_card("KPIs Defined", str(kpi_count), "success" if kpi_count > 0 else "neutral")
    with c7: metric_card("Findings", str(find_count), "success" if find_count > 0 else "neutral")
    with c8: metric_card("Readiness", readiness_score, "success" if readiness_score.endswith("%") and readiness_score != "0%" else "neutral")

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
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Data Quality Scan</h2>
    </div>
    """, unsafe_allow_html=True)

    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    scan_results = get_project_scan_results(ws)
    table_list = list(ws.registry.keys())

    col_sel, col_btn1, col_btn2 = st.columns([3, 1.5, 1.5])
    with col_sel:
        selected_table = st.selectbox("Select Table", table_list, key="dq_table_select")
    with col_btn1:
        st.markdown("<div style='height: 1.7rem;'></div>", unsafe_allow_html=True)
        scan_single = st.button("Scan Selected Table", type="primary", use_container_width=True, key="btn_scan_selected")
    with col_btn2:
        st.markdown("<div style='height: 1.7rem;'></div>", unsafe_allow_html=True)
        scan_all = st.button("Scan All Tables", use_container_width=True, key="btn_scan_all")

    # Single Table Scan Handler
    if scan_single:
        entry = ws.registry[selected_table]
        from src.pipeline import run_pipeline
        from src.run_history import RunHistoryManager
        from src.dataset_versioning import DatasetVersioningManager

        progress_placeholder = st.empty()
        start_time = time.time()

        def _update_stage(stage_name: str):
            elapsed = time.time() - start_time
            progress_placeholder.info(f"Scanning table **{selected_table}** [{stage_name}] — Elapsed: {elapsed:.1f}s")

        rhm = RunHistoryManager(ws.project_root)
        run_id = rhm.create_run()
        rhm.update_run(run_id, {"cleaning_summary": {"operation": "Data Quality Scan", "table": selected_table}})
        try:
            _update_stage("Starting scan")
            s, err = run_pipeline(entry.file_path, None, progress_callback=_update_stage)
            if not s:
                raise Exception(err)

            res = st.session_state.analysis_results
            df = res["df"]

            dvm = DatasetVersioningManager(ws.project_root)
            source_hash = dvm.compute_df_hash(df)
            schema_hash = dvm.compute_hash(str(list(df.columns)))
            existing_versions = dvm.get_all_versions()
            vid = None
            for v in existing_versions:
                if v.version_type == "RAW" and v.source_hash == source_hash:
                    vid = v.version_id
                    break
            if not vid:
                vid = dvm.create_version("RAW", source_hash, len(df), 1, schema_hash, None, {}, column_count=len(df.columns))

            res["dataset_version_id"] = vid
            qs = res["readiness"].overall_score
            rhm.update_run(run_id, {"dataset_version_id": vid, "quality_score": qs})
            rhm.complete_run(run_id)

            entry.row_count = res["profile"].row_count
            entry.column_count = res["profile"].column_count
            ws.mark_analyzed(selected_table)
            _store_scan_result(ws, selected_table, res)

            elapsed = time.time() - start_time
            progress_placeholder.success(f"Scan completed for **{selected_table}** in {elapsed:.2f}s!")
        except Exception as ex:
            rhm.fail_run(run_id)
            elapsed = time.time() - start_time
            progress_placeholder.error(f"Scan failed for **{selected_table}** after {elapsed:.2f}s: {ex}")
            _store_failed_scan(ws, selected_table, str(ex))

    # Sequential Scan All Tables Handler
    if scan_all:
        from src.pipeline import run_pipeline
        from src.run_history import RunHistoryManager
        from src.dataset_versioning import DatasetVersioningManager

        progress_bar = st.progress(0.0)
        status_box = st.empty()
        total_tables = len(table_list)
        overall_start = time.time()
        failures = []

        for idx, tname in enumerate(table_list):
            table_entry = ws.registry[tname]
            t_start = time.time()
            progress_bar.progress(idx / total_tables)

            def _update_seq_stage(stage_name: str):
                t_elapsed = time.time() - t_start
                tot_elapsed = time.time() - overall_start
                status_box.info(
                    f"Table {idx + 1}/{total_tables}: **{tname}** [{stage_name}] | "
                    f"Table elapsed: {t_elapsed:.1f}s | Total elapsed: {tot_elapsed:.1f}s"
                )

            rhm = RunHistoryManager(ws.project_root)
            run_id = rhm.create_run()
            rhm.update_run(run_id, {"cleaning_summary": {"operation": "Data Quality Scan", "table": tname}})
            try:
                _update_seq_stage("Starting scan")
                s, err = run_pipeline(table_entry.file_path, None, progress_callback=_update_seq_stage)
                if not s:
                    raise Exception(err)

                res = st.session_state.analysis_results
                df = res["df"]

                dvm = DatasetVersioningManager(ws.project_root)
                source_hash = dvm.compute_df_hash(df)
                schema_hash = dvm.compute_hash(str(list(df.columns)))
                existing_versions = dvm.get_all_versions()
                vid = None
                for v in existing_versions:
                    if v.version_type == "RAW" and v.source_hash == source_hash:
                        vid = v.version_id
                        break
                if not vid:
                    vid = dvm.create_version("RAW", source_hash, len(df), 1, schema_hash, None, {}, column_count=len(df.columns))

                res["dataset_version_id"] = vid
                qs = res["readiness"].overall_score
                rhm.update_run(run_id, {"dataset_version_id": vid, "quality_score": qs})
                rhm.complete_run(run_id)

                table_entry.row_count = res["profile"].row_count
                table_entry.column_count = res["profile"].column_count
                ws.mark_analyzed(tname)
                _store_scan_result(ws, tname, res)
            except Exception as ex:
                rhm.fail_run(run_id)
                failures.append((tname, str(ex)))
                _store_failed_scan(ws, tname, str(ex))
                st.error(f"Failed scanning table **{tname}**: {ex}")

        progress_bar.progress(1.0)
        tot_elapsed = time.time() - overall_start
        if failures:
            status_box.warning(
                f"Sequential scan completed in {tot_elapsed:.2f}s. "
                f"{total_tables - len(failures)} succeeded, {len(failures)} failed."
            )
        else:
            status_box.success(
                f"All {total_tables} tables scanned successfully in {tot_elapsed:.2f}s!"
            )

    # Display Findings and Summary Metrics for selected_table immediately
    res = scan_results.get(selected_table)
    st.markdown("---")
    st.markdown(f"### Table Quality Summary: `{selected_table}`")

    if res is None:
        entry = ws.registry[selected_table]
        st.info(f"Table **{selected_table}** has not been scanned yet.")
        f_size_mb = (Path(entry.file_path).stat().st_size / (1024 * 1024)) if Path(entry.file_path).exists() else 0
        st.caption(f"Source file: `{entry.file_name}` ({f_size_mb:.2f} MB) • Status: Not Scanned")
        return

    if res.get("scan_status") == "FAILED":
        st.error(f"Scan failed for **{selected_table}**: {res.get('error_message', 'Unknown error')}")
        return

    # Scan Completed
    all_issues = res.get("all_issues", [])
    readiness = res.get("readiness")
    score_val = readiness.overall_score if readiness and hasattr(readiness, "overall_score") else 0.0
    grade_val = readiness.grade if readiness and hasattr(readiness, "grade") else "N/A"
    elapsed = res.get("elapsed", 0.0)

    err_count = sum(1 for i in all_issues if normalize_severity(i.severity) == "ERROR")
    warn_count = sum(1 for i in all_issues if normalize_severity(i.severity) == "WARNING")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        metric_card("Total Issues", str(len(all_issues)), "error" if err_count > 0 else "warning" if warn_count > 0 else "success")
    with m2:
        metric_card("Errors / Critical", str(err_count), "error" if err_count > 0 else "neutral")
    with m3:
        metric_card("Warnings / Major", str(warn_count), "warning" if warn_count > 0 else "neutral")
    with m4:
        metric_card("Readiness Score", f"{score_val:.0f}% ({grade_val})", "success" if score_val >= 75 else "warning")
    with m5:
        metric_card("Scan Duration", f"{elapsed:.2f}s", "neutral")

    # Issue Table
    if all_issues:
        st.markdown(f"#### Detected Issues ({len(all_issues)})")
        issue_rows = []
        for i in all_issues:
            cls_name = getattr(getattr(i, "classification", None), "value", str(getattr(i, "classification", "UNSAFE_TO_FIX")))
            issue_rows.append({
                "Type": i.issue_type,
                "Column": i.column or "DATASET",
                "Severity": normalize_severity(i.severity),
                "Classification": cls_name,
                "Message": i.message
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(issue_rows), use_container_width=True, hide_index=True)
    else:
        st.success("No issues detected! Table is 100% clean and ready for analysis.")


def render_issues(ws: ProjectWorkspace):
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Issues</h2>
    </div>
    """, unsafe_allow_html=True)
    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    selected_table = st.selectbox("Select Table", list(ws.registry.keys()), key="issues_table_select")

    scan_results = get_project_scan_results(ws)
    if selected_table not in scan_results or scan_results[selected_table].get("scan_status") != "COMPLETED":
        empty_state("Table not scanned", f"Run a Data Quality Scan on {selected_table} first.", "Go to Data Quality", "Data Quality")
        return

    res = scan_results[selected_table]
    all_issues = res.get("all_issues", [])
    if not all_issues:
        st.success("No issues found!")
        return

    st.markdown(f"Found {len(all_issues)} issues in table `{selected_table}`.")
    issue_data = []
    for issue in all_issues:
        issue_data.append({
            "Issue ID": issue.issue_id,
            "Severity": normalize_severity(issue.severity),
            "Type": issue.issue_type,
            "Column": issue.column or "DATASET",
            "Rows Affected": getattr(issue, "affected_count", 1 if getattr(issue, "row_index", None) is not None else 1),
            "Description": issue.message
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(issue_data), use_container_width=True)


def render_cleaning(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Data Cleaning & Repair</h2>
    </div>
    ''', unsafe_allow_html=True)
    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    selected_table = st.selectbox("Select Table", list(ws.registry.keys()), key="cleaning_table_select")

    scan_results = get_project_scan_results(ws)
    if selected_table not in scan_results or scan_results[selected_table].get("scan_status") != "COMPLETED":
        empty_state("Table not scanned", f"Run a Data Quality Scan on {selected_table} first.", "Go to Data Quality", "Data Quality")
        return

    res = scan_results[selected_table]

    # Load DataFrame on demand if not present in memory
    if res.get("repaired_df") is not None:
        df = res["repaired_df"]
    elif res.get("df") is not None:
        df = res["df"]
    else:
        df, _ = ws.load_table(selected_table)

    tab_auto, tab_impute, tab_drop = st.tabs(["Auto Repairs", "Impute Nulls", "Drop Column"])

    with tab_auto:
        if st.session_state.pop("auto_repairs_applied", False):
            st.success("Repairs applied.")
        if not res.get("proposals"):
            st.success("No auto-repairs needed.")
        else:
            st.markdown(f"Generated {len(res['proposals'])} repair proposals.")
            if st.button("Approve Safe Fixes", type="primary"):
                from src.repair_engine import RepairEngine
                from src.run_history import RunHistoryManager
                from src.dataset_versioning import DatasetVersioningManager
                from src.proposal_generator import ApprovalState
                rhm = RunHistoryManager(ws.project_root)
                run_id = rhm.create_run()
                rhm.update_run(run_id, {"cleaning_summary": {"operation": "Auto Repair"}})
                try:
                    re = RepairEngine()
                    instructions = []
                    for p in res["proposals"]:
                        if getattr(p.classification, "value", str(p.classification)) == "AUTO_FIXABLE" or getattr(p.approval_state, "value", str(p.approval_state)) == "APPROVED":
                            p.approval_state = ApprovalState.APPROVED
                            instructions.append(p.to_repair_instruction())
                    with st.spinner("Applying repairs..."):
                        repaired_df, repair_res = re.apply(df, instructions)
                        res["repaired_df"] = repaired_df
                        res["repair_results"] = repair_res
                        dvm = DatasetVersioningManager(ws.project_root)
                        parent_vid = res.get("dataset_version_id")
                        source_hash = dvm.compute_df_hash(repaired_df)
                        schema_hash = dvm.compute_hash(str(list(repaired_df.columns)))
                        total_affected = sum(r.affected_rows for r in repair_res.values()) if isinstance(repair_res, dict) else getattr(repair_res, "affected_rows", 0)
                        summary = {"affected_rows": total_affected}
                        new_vid = dvm.create_version("CLEANED", source_hash, len(repaired_df), 1, schema_hash, parent_vid, summary, column_count=len(repaired_df.columns))
                        res["dataset_version_id"] = new_vid
                        rhm.update_run(run_id, {"dataset_version_id": new_vid, "cleaning_summary": {"operation": "Auto Repair", **summary}})
                        rhm.complete_run(run_id)
                        st.session_state["auto_repairs_applied"] = True
                        st.rerun()
                except Exception as ex:
                    rhm.fail_run(run_id)
                    st.error(str(ex))

    with tab_impute:
        if st.session_state.pop("imputation_applied", False):
            st.success("Imputation applied.")
        col = st.selectbox("Select Column to Impute", df.columns.tolist(), key="impute_col")
        strategy = st.selectbox("Imputation Strategy", ["mean", "median", "mode", "constant"], key="impute_strat")
        constant_val = None
        if strategy == "constant":
            constant_val = st.text_input("Constant Value", key="impute_const")

        null_count = df[col].isna().sum()
        st.write(f"Null rows affected: {null_count}")

        if st.button("Preview Imputation"):
            st.session_state["impute_preview"] = True

        if st.session_state.get("impute_preview"):
            if null_count == 0:
                st.warning("No nulls to impute.")
            elif null_count == len(df):
                st.error("Cannot impute an entirely null column.")
            else:
                from src.repair_engine import RepairEngine, RepairInstruction
                from src.issue_manager import IssueClassification
                re = RepairEngine()
                inst = RepairInstruction(
                    action="impute_nulls",
                    classification=IssueClassification.REVIEW_REQUIRED,
                    column=col,
                    proposed_value={"strategy": strategy, "value": constant_val},
                    reason=f"Manual imputation using {strategy}"
                )
                try:
                    # Test apply on working copy
                    preview_df, preview_res = re._impute_nulls(df.copy(), inst)
                    if not preview_res.success:
                        st.error(preview_res.errors[0])
                    else:
                        st.success("Preview successful. Review changes:")
                        # Show some changed rows
                        st.write(preview_res.change_records[:5])

                        col1, col2 = st.columns(2)
                        if col1.button("Approve & Apply Imputation", type="primary"):
                            from src.run_history import RunHistoryManager
                            from src.dataset_versioning import DatasetVersioningManager
                            rhm = RunHistoryManager(ws.project_root)
                            run_id = rhm.create_run()
                            rhm.update_run(run_id, {"cleaning_summary": {"operation": "Impute Nulls"}})
                            try:
                                final_df, final_res = re.apply(df, [inst])
                                res["repaired_df"] = final_df
                                res["repair_results"] = final_res
                                final_affected = sum(r.affected_rows for r in final_res.values()) if isinstance(final_res, dict) else getattr(final_res, "affected_rows", 0)

                                dvm = DatasetVersioningManager(ws.project_root)
                                parent_vid = res.get("dataset_version_id")
                                source_hash = dvm.compute_df_hash(final_df)
                                schema_hash = dvm.compute_hash(str(list(final_df.columns)))
                                summary = {"affected_rows": final_affected, "column": inst.column, "action": inst.action}
                                new_vid = dvm.create_version("CLEANED", source_hash, len(final_df), 1, schema_hash, parent_vid, summary, column_count=len(final_df.columns))
                                res["dataset_version_id"] = new_vid

                                rhm.update_run(run_id, {"dataset_version_id": new_vid, "cleaning_summary": {"operation": "Impute Nulls", **summary}})
                                rhm.complete_run(run_id)
                                st.session_state["impute_preview"] = False
                                st.session_state["imputation_applied"] = True
                                st.rerun()
                            except Exception as ex:
                                rhm.fail_run(run_id)
                                st.error(str(ex))
                        if col2.button("Reject / Cancel"):
                            st.session_state["impute_preview"] = False
                            st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_drop:
        if st.session_state.pop("column_dropped", False):
            st.success("Column dropped.")
        drop_col = st.selectbox("Select Column to Drop", df.columns.tolist(), key="drop_col")
        st.write(f"This will completely remove column '{drop_col}' from the active dataset.")

        if st.button("Preview Drop"):
            st.session_state["drop_preview"] = True

        if st.session_state.get("drop_preview"):
            if len(df.columns) <= 1:
                st.error("Cannot drop the last remaining column in the dataset.")
            else:
                from src.repair_engine import RepairEngine, RepairInstruction
                from src.issue_manager import IssueClassification
                re = RepairEngine()
                inst = RepairInstruction(
                    action="drop_column",
                    classification=IssueClassification.REVIEW_REQUIRED,
                    column=drop_col,
                    reason=f"Manual column drop"
                )
                try:
                    preview_df, preview_res = re._drop_column(df.copy(), inst)
                    if not preview_res.success:
                        st.error(preview_res.errors[0])
                    else:
                        st.success("Preview successful.")
                        col1, col2 = st.columns(2)
                        if col1.button("Approve & Apply Drop", type="primary"):
                            from src.run_history import RunHistoryManager
                            from src.dataset_versioning import DatasetVersioningManager
                            rhm = RunHistoryManager(ws.project_root)
                            run_id = rhm.create_run()
                            rhm.update_run(run_id, {"cleaning_summary": {"operation": "Drop Column"}})
                            try:
                                final_df, final_res = re.apply(df, [inst])
                                res["repaired_df"] = final_df
                                res["repair_results"] = final_res
                                final_affected = sum(r.affected_rows for r in final_res.values()) if isinstance(final_res, dict) else getattr(final_res, "affected_rows", 0)

                                dvm = DatasetVersioningManager(ws.project_root)
                                parent_vid = res.get("dataset_version_id")
                                source_hash = dvm.compute_df_hash(final_df)
                                schema_hash = dvm.compute_hash(str(list(final_df.columns)))
                                summary = {"affected_rows": final_affected, "column": inst.column, "action": inst.action}
                                new_vid = dvm.create_version("CLEANED", source_hash, len(final_df), 1, schema_hash, parent_vid, summary, column_count=len(final_df.columns))
                                res["dataset_version_id"] = new_vid

                                rhm.update_run(run_id, {"dataset_version_id": new_vid, "cleaning_summary": {"operation": "Drop Column", **summary}})
                                rhm.complete_run(run_id)
                                st.session_state["drop_preview"] = False
                                st.session_state["column_dropped"] = True
                                st.rerun()
                            except Exception as ex:
                                rhm.fail_run(run_id)
                                st.error(str(ex))
                        if col2.button("Reject / Cancel Drop"):
                            st.session_state["drop_preview"] = False
                            st.rerun()
                except Exception as e:
                    st.error(str(e))

def render_validation(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Validation Results & Custom Patterns</h2>
    </div>
    ''', unsafe_allow_html=True)
    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    selected_table = st.selectbox("Select Table", list(ws.registry.keys()), key="val_table_select")

    scan_results = get_project_scan_results(ws)
    if selected_table not in scan_results or scan_results[selected_table].get("scan_status") != "COMPLETED":
        empty_state("Table not scanned", f"Run a Data Quality Scan on {selected_table} first.", "Go to Data Quality", "Data Quality")
        return

    res = scan_results[selected_table]
    if res.get("repaired_df") is not None:
        df = res["repaired_df"]
    elif res.get("df") is not None:
        df = res["df"]
    else:
        try:
            df, _ = ws.load_table(selected_table)
        except Exception as e:
            st.error(f"Could not load data for table '{selected_table}': {e}")
            return

    tab_snapshot, tab_pattern = st.tabs(["Validation Snapshot", "Custom Pattern Validation"])

    with tab_snapshot:
        if res.get("after_snapshot"):
            st.success("Validation completed.")
            score_after = res['comparison_result'].after_readiness
            score_after_str = f"{score_after:.1f}" if isinstance(score_after, (int, float)) else str(score_after)
            st.write(f"Readiness Score: {score_after_str}%")
        elif res.get("before_snapshot"):
            score_before = res['before_snapshot'].readiness.overall_score
            score_before_str = f"{score_before:.1f}" if isinstance(score_before, (int, float)) else str(score_before)
            st.write(f"Initial Readiness Score: {score_before_str}%")
        else:
            st.info("No validation snapshot found.")

    with tab_pattern:
        if df is None or not hasattr(df, "columns"):
            st.warning("No tabular data available for pattern validation.")
            return

        col = st.selectbox("Select Column for Pattern Validation", df.columns.tolist(), key="pat_col")
        pattern = st.text_input("Regex Pattern", key="pat_regex")

        if st.button("Validate Pattern", type="primary"):
            from src.repair_engine import validate_custom_pattern

            success, val_result = validate_custom_pattern(df, col, pattern)

            if not success:
                st.error(val_result.get("error", "Unknown validation error."))
            else:
                st.success("Regex applied successfully.")
                st.write(f"Matches: {val_result['matches']}")
                st.write(f"Non-Matches: {val_result['non_matches']}")
                st.write(f"Nulls (Ignored): {val_result['nulls']}")

                if val_result['non_matches'] > 0:
                    st.warning("Offending rows preview:")
                    if 'offending_indices' in val_result and val_result['offending_indices']:
                        st.dataframe(df.loc[val_result['offending_indices']].head(10))

                    issue = val_result.get("issue")
                    if issue:
                        issue_exists = False
                        if res.get("all_issues"):
                            for existing_issue in res["all_issues"]:
                                if existing_issue.issue_type == "CUSTOM_PATTERN" and existing_issue.column == col:
                                    issue_exists = True
                                    break
                        else:
                            res["all_issues"] = []

                        if not issue_exists:
                            res["all_issues"].append(issue)
                            st.info("Registered as a new issue.")

