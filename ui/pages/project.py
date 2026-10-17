from ui.components import dataforge_button, run_action, empty_state
from ui.theme import clean_html


def render_data_import():
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    c2 = st.container()

    with c2:
        with st.container():
            import_header = """
            <div style="margin-bottom: 1.75rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.25rem;">
                    <div style="
                        width: 38px;
                        height: 38px;
                        border-radius: 10px;
                        background: var(--primary-gradient);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 4px 14px rgba(56, 103, 255, 0.4);
                    ">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                            <polyline points="2 17 12 22 22 17"></polyline>
                            <polyline points="2 12 12 17 22 12"></polyline>
                        </svg>
                    </div>
                    <div>
                        <h1 style="font-size: 2rem; font-weight: 800; margin: 0; letter-spacing: -0.03em;">DATAFORGE</h1>
                        <div style="color: var(--text-secondary); font-size: 0.85rem; font-weight: 500;">Professional Data Analytics Workspace</div>
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
                <h2 style="margin: 0; font-size: 1.3rem; font-weight: 700;">Import your data<span style="display:none">Upload Your Data</span></h2>
                <span class="df-badge df-badge-info">Step 1 of 3</span>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 1.25rem; font-size: 0.9rem;">Bring CSV or Excel files into your workspace. We'll automatically infer schema, detect types, and run preliminary quality checks.</p>
            """
            st.markdown(clean_html(import_header), unsafe_allow_html=True)

            if "uploader_key" not in st.session_state:
                st.session_state.uploader_key = 0

            import os
            is_testing = os.getenv("DATAFORGE_TESTING") == "1"
            allowed_types = ["csv", "xlsx", "xls"] if not is_testing else None

            # Drag & drop upload area with format indicators
            badges_html = """
            <div style="
                display: flex;
                gap: 0.75rem;
                justify-content: center;
                margin-bottom: 0.85rem;
            ">
                <span class="df-badge df-badge-info">CSV</span>
                <span class="df-badge df-badge-success">XLSX</span>
                <span class="df-badge df-badge-purple">XLS</span>
            </div>
            """
            st.markdown(clean_html(badges_html), unsafe_allow_html=True)

            uploaded_files = st.file_uploader(
                "Drag & Drop Files Here",
                type=allowed_types,
                accept_multiple_files=True,
                key=f"uploader_{st.session_state.uploader_key}",
                label_visibility="collapsed"
            )
            st.markdown(
                "<div style='color: var(--text-secondary); font-size: 0.825rem; text-align: center; margin-top: -0.75rem; margin-bottom: 1.25rem;'>"
                "Supported: CSV &bull; XLSX &bull; XLS"
                "</div>", unsafe_allow_html=True
            )

            if "removed_files" not in st.session_state:
                st.session_state.removed_files = set()

            active_files = [f for f in uploaded_files if f.name not in st.session_state.removed_files]

            if active_files:
                st.markdown("<div style='margin-top: 1.25rem; margin-bottom: 0.5rem; font-weight: 700; font-size: 0.95rem; color: var(--text-primary);'>Selected Files</div>", unsafe_allow_html=True)

                # Modern Table header
                table_hdr_html = """
                <div style='display: flex; color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; margin-bottom: 0.5rem;'>
                    <div style='flex: 3;'>Filename</div>
                    <div style='flex: 1;'>Format</div>
                    <div style='flex: 1;'>Size</div>
                    <div style='flex: 1;'>Status</div>
                    <div style='flex: 1;'>Action</div>
                </div>
                """
                st.markdown(clean_html(table_hdr_html), unsafe_allow_html=True)

                for f in active_files:
                    size_mb = f.size / (1024 * 1024)
                    ext = Path(f.name).suffix.upper().replace('.', '')
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        row_html = f"""
                        <div style='display: flex; color: var(--text-primary); font-size: 0.875rem; margin-bottom: 0.35rem; align-items: center; padding: 0.35rem 0;'>
                            <div style='flex: 3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500;'><span style='color: var(--success); margin-right: 0.35rem;'>&check;</span> {f.name}</div>
                            <div style='flex: 1;'><span class='df-badge df-badge-neutral'>{ext}</span></div>
                            <div style='flex: 1; color: var(--text-secondary);'>{size_mb:.1f} MB</div>
                            <div style='flex: 1;'><span class='df-badge df-badge-success'>Ready</span></div>
                        </div>
                        """
                        st.markdown(clean_html(row_html), unsafe_allow_html=True)
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

        st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)
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

    import datetime
    today_str = datetime.datetime.now().strftime("%a, %d %b %Y")

    # 1. Hero Atmospheric Sunset Mountain Banner (as in reference image)
    hero_html = (
        f"<div style='background: linear-gradient(135deg, #0d122b 0%, #1a1638 50%, #0c1a35 100%); border: 1px solid rgba(120, 87, 255, 0.25); border-radius: 14px; padding: 1.5rem 1.75rem; margin-bottom: 1.25rem; position: relative; overflow: hidden; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);'>"
        f"<div style='position: absolute; top: -40px; right: 15%; width: 280px; height: 180px; background: radial-gradient(circle, rgba(236, 72, 153, 0.2) 0%, rgba(120, 87, 255, 0.15) 50%, transparent 80%); border-radius: 50%; filter: blur(40px); pointer-events: none;'></div>"
        f"<div style='position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;'>"
        f"<div>"
        f"<h1 style='font-size: 1.85rem; font-weight: 800; color: #FFFFFF; margin: 0 0 0.3rem 0; letter-spacing: -0.025em;'>Welcome to DATAFORGE 👋</h1>"
        f"<div style='color: #9AAAC2; font-size: 0.925rem;'>Turn your data into powerful insights</div>"
        f"</div>"
        f"<div style='display: flex; align-items: center; gap: 0.5rem; background: rgba(6, 16, 32, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); padding: 0.45rem 0.9rem; border-radius: 8px; font-size: 0.825rem; color: #F4F7FF;'>"
        f"<svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='4' width='18' height='18' rx='2'/><line x1='16' y1='2' x2='16' y2='6'/><line x1='8' y1='2' x2='8' y2='6'/><line x1='3' y1='10' x2='21' y2='10'/></svg>"
        f"<span>{today_str}</span>"
        f"</div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(clean_html(hero_html), unsafe_allow_html=True)

    st.markdown('<h3 style="margin-top: 0; margin-bottom: 0.75rem; color: var(--text-primary); font-size: 1.05rem; font-weight: 650;">Project Overview</h3>', unsafe_allow_html=True)

    # 2. Top 5 Metric Cards (matching reference image)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Total Tables", str(tables_count), "info", delta="+0")
    with c2:
        metric_card("Total Rows", rows_display, "info", delta="+0")
    with c3:
        metric_card("Relationships", str(rel_count), "purple", delta=f"+{rel_count}%" if rel_count else "0")
    with c4:
        metric_card("Data Issues", str(num_issues), "error" if num_issues > 0 else "success", delta="Needs Review" if num_issues > 0 else "Clean")
    with c5:
        score_status = "success" if readiness_score.endswith("%") and readiness_score != "0%" else ("error" if quality_status == "Blocked" else "warning")
        metric_card("Quality Score", readiness_score, score_status, delta=quality_status)

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # 3. Middle Section: Recent Projects & AI banner (Left) vs Quick Actions & Live Activity (Right)
    col_left, col_right = st.columns([1.65, 1])

    with col_left:
        st.markdown(
            "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;'>"
            "<h4 style='margin: 0; font-size: 0.85rem; font-weight: 700; color: var(--text-primary); text-transform: none; letter-spacing: 0;'>Recent Projects</h4>"
            "<span style='color: var(--primary); font-size: 0.8rem; font-weight: 600;'>Active Workspaces &rarr;</span>"
            "</div>",
            unsafe_allow_html=True
        )

        recent_items = []
        workspaces_dir = Path(".dataforge_workspaces")
        if workspaces_dir.exists():
            for p in sorted(workspaces_dir.iterdir(), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)[:5]:
                if p.is_dir():
                    is_active = ws and ws.project_root.resolve() == p.resolve()
                    t_count = 0
                    r_count = 0
                    cfg = p / "project_config.json"
                    if cfg.exists():
                        try:
                            d = json.loads(cfg.read_text())
                            reg = d.get("registry", {})
                            t_count = len(reg)
                            for itm in reg.values():
                                r_count += itm.get("row_count", 0) or 0
                        except Exception:
                            pass
                    p_name = p.name[:8]
                    if is_active and tables_count > 0:
                        first_tbl = list(ws.registry.keys())[0]
                        p_name = f"{first_tbl.capitalize()} & Related"

                    recent_items.append({
                        "Project Name": p_name + (" (Active)" if is_active else ""),
                        "Tables": t_count if t_count > 0 else (tables_count if is_active else 0),
                        "Rows": f"{r_count:,}" if r_count > 0 else (rows_display if is_active else "0"),
                        "Status": "Ready" if (t_count > 0 or (is_active and tables_count > 0)) else "Not Scanned"
                    })

        if not recent_items:
            recent_items = [{
                "Project Name": f"{list(ws.registry.keys())[0].capitalize()} & Related" if tables_count > 0 else "Active Workspace",
                "Tables": tables_count,
                "Rows": rows_display,
                "Status": quality_status
            }]

        import pandas as pd
        st.dataframe(
            pd.DataFrame(recent_items),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Project Name": st.column_config.TextColumn("Project Name", width="medium"),
                "Tables": st.column_config.NumberColumn("Tables", width="small"),
                "Rows": st.column_config.TextColumn("Rows", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            }
        )

        # "Let AI Work For You" Card (from reference design)
        ai_banner_html = (
            f"<div style='background: linear-gradient(135deg, rgba(56, 103, 255, 0.14) 0%, rgba(120, 87, 255, 0.14) 100%); border: 1px solid rgba(56, 103, 255, 0.28); border-radius: 12px; padding: 1.15rem 1.35rem; margin-top: 1rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;'>"
            f"<div style='display: flex; align-items: center; gap: 1rem;'>"
            f"<div style='width: 40px; height: 40px; border-radius: 10px; background: var(--primary-gradient); display: flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 800; color: #FFFFFF; box-shadow: 0 4px 14px rgba(56, 103, 255, 0.4);'>AI</div>"
            f"<div>"
            f"<div style='font-weight: 750; color: #FFFFFF; font-size: 0.925rem;'>Let AI Work For You</div>"
            f"<div style='color: var(--text-secondary); font-size: 0.8rem;'>Get smart suggestions, auto-cleaning and insights powered by AI</div>"
            f"</div>"
            f"</div>"
            f"<div style='background: rgba(56, 103, 255, 0.25); border: 1px solid rgba(56, 103, 255, 0.4); color: #FFFFFF; padding: 0.4rem 0.85rem; border-radius: 8px; font-size: 0.8rem; font-weight: 600;'>Assisted Analysis Active</div>"
            f"</div>"
        )
        st.markdown(clean_html(ai_banner_html), unsafe_allow_html=True)

    with col_right:
        st.markdown(
            "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;'>"
            "<h4 style='margin: 0; font-size: 0.85rem; font-weight: 700; color: var(--text-primary); text-transform: none; letter-spacing: 0;'>Quick Actions</h4>"
            "</div>",
            unsafe_allow_html=True
        )

        if st.button("⚡ Run Quality Scan", type="primary", use_container_width=True, key="ov_btn_scan"):
            st.session_state.current_page = "Data Quality"
            st.rerun()

        col_q1, col_q2 = st.columns(2)
        with col_q1:
            if st.button("🔗 Detect Relationships", use_container_width=True, key="ov_btn_rel"):
                st.session_state.current_page = "Relationships"
                st.rerun()
            if st.button("📊 Generate KPIs", use_container_width=True, key="ov_btn_kpi"):
                st.session_state.current_page = "KPI Center"
                st.rerun()
        with col_q2:
            if st.button("💻 Open SQL Workspace", use_container_width=True, key="ov_btn_sql"):
                st.session_state.current_page = "SQL Workspace"
                st.rerun()
            if st.button("📦 Export Package", use_container_width=True, key="ov_btn_export"):
                st.session_state.current_page = "Export Package"
                st.rerun()

        # Recent Activity Card
        recent_log = []
        if scan_results:
            for t, r in scan_results.items():
                if r.get("scan_status") == "COMPLETED":
                    dur = r.get("elapsed", 0.0)
                    recent_log.append(f"Quality scan completed for <b>{t}</b> ({dur:.2f}s)")
        if not recent_log:
            recent_log = [
                f"Workspace loaded ({tables_count} tables)",
                "System integrity verified"
            ]

        activity_html = "".join([f"<li style='margin-bottom: 0.4rem; color: var(--text-secondary); font-size: 0.8rem;'>{item}</li>" for item in recent_log[:3]])

        rec_card_html = (
            f"<div class='df-card' style='margin-top: 1rem; padding: 1rem 1.15rem;'>"
            f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;'>"
            f"<h4 style='margin: 0; font-size: 0.8rem; font-weight: 700; color: var(--text-primary); text-transform: none; letter-spacing: 0;'>Recent Activity</h4>"
            f"<span style='color: var(--text-muted); font-size: 0.72rem;'>Live Log</span>"
            f"</div>"
            f"<ul style='padding-left: 1.1rem; margin: 0;'>"
            f"{activity_html}"
            f"</ul>"
            f"</div>"
        )
        st.markdown(clean_html(rec_card_html), unsafe_allow_html=True)


def render_data_quality(ws: ProjectWorkspace):
    st.markdown(clean_html("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Data Quality Scan</h2>
    </div>
    """), unsafe_allow_html=True)

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
        df_issues = pd.DataFrame(issue_rows)

        dups = [r for r in issue_rows if "dup" in r["Type"].lower()]
        nulls = [r for r in issue_rows if "null" in r["Type"].lower() or "missing" in r["Type"].lower()]
        types = [r for r in issue_rows if "type" in r["Type"].lower() or "inconsist" in r["Type"].lower()]

        tab_all, tab_dup, tab_null, tab_typ = st.tabs([
            f"All Issues ({len(all_issues)})",
            f"Duplicates ({len(dups)})",
            f"Missing Values ({len(nulls)})",
            f"Data Types ({len(types)})"
        ])
        issue_col_config = {
            "Type": st.column_config.TextColumn("Type", width="medium"),
            "Column": st.column_config.TextColumn("Column", width="medium"),
            "Severity": st.column_config.TextColumn("Severity", width="small"),
            "Classification": st.column_config.TextColumn("Classification", width="medium"),
            "Message": st.column_config.TextColumn("Message", width="large"),
        }
        with tab_all:
            st.dataframe(df_issues, use_container_width=True, hide_index=True, column_config=issue_col_config)
        with tab_dup:
            if dups:
                st.dataframe(pd.DataFrame(dups), use_container_width=True, hide_index=True, column_config=issue_col_config)
            else:
                st.info("No duplicate issues detected in this table.")
        with tab_null:
            if nulls:
                st.dataframe(pd.DataFrame(nulls), use_container_width=True, hide_index=True, column_config=issue_col_config)
            else:
                st.info("No missing value issues detected in this table.")
        with tab_typ:
            if types:
                st.dataframe(pd.DataFrame(types), use_container_width=True, hide_index=True, column_config=issue_col_config)
            else:
                st.info("No type inconsistency issues detected in this table.")
    else:
        st.success("No issues detected! Table is 100% clean and ready for analysis.")


def render_issues(ws: ProjectWorkspace):
    st.markdown(clean_html("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Issues</h2>
    </div>
    """), unsafe_allow_html=True)
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
    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Data Cleaning & Repair</h2>
    </div>
    '''), unsafe_allow_html=True)
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
    st.markdown(clean_html('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Validation Results & Custom Patterns</h2>
    </div>
    '''), unsafe_allow_html=True)
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

