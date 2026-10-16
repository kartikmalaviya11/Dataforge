from ui.components import dataforge_button, run_action, empty_state
import streamlit as st
from src.workspace import ProjectWorkspace
import pandas as pd
import os
from ui.theme import badge

def render_relationships(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Relationships</h2>
    </div>
    ''', unsafe_allow_html=True)

    if len(ws.registry) < 2:
        empty_state(
            title="No cross-table relationships found",
            description="Relationship detection requires multiple tables. Your project currently has only 1 table.",
            action_label="Upload More Data",
            target_page="Data Import"
        )
        return

    from src.relationship_engine import RelationshipDetector
    rel_path = ws.project_root / ".dataforge" / "relationships.json"

    if "relationship_candidates" not in st.session_state:
        if rel_path.exists():
            st.session_state.relationship_candidates = RelationshipDetector.load_candidates(rel_path)

    if dataforge_button("Detect Relationships", type="primary"):
        tables_cache = {}
        def _load_tables():
            for tname in ws.registry.keys():
                df, _ = ws.load_table(tname)
                tables_cache[tname] = df

        def _detect():
            detector = RelationshipDetector()
            new_candidates = detector.detect(tables_cache)
            if rel_path.exists():
                existing = {
                    (c.source_table, c.source_column, c.target_table, c.target_column): c.status
                    for c in RelationshipDetector.load_candidates(rel_path)
                }
                for nc in new_candidates:
                    key = (nc.source_table, nc.source_column, nc.target_table, nc.target_column)
                    if key in existing:
                        nc.status = existing[key]
            st.session_state.relationship_candidates = new_candidates
            RelationshipDetector.save_candidates(new_candidates, rel_path)

        from ui.components import run_action
        run_action("Detect Relationships", [
            ("Loading tables...", _load_tables),
            ("Detecting candidates...", _detect)
        ])

    if "relationship_candidates" in st.session_state:
        candidates = st.session_state.relationship_candidates
        if not candidates:
            st.info("No candidates detected.")
        else:
            rel_data = []
            for r in candidates:
                stat = r.status.value if hasattr(r.status, "value") else str(r.status)
                card = r.cardinality.value if hasattr(r.cardinality, "value") else str(r.cardinality)
                rel_data.append({
                    "Accept": stat == "ACCEPTED",
                    "Source": f"{r.source_table}.{r.source_column}",
                    "Target": f"{r.target_table}.{r.target_column}",
                    "Cardinality": card,
                    "Confidence": f"{r.confidence:.1f}%",
                })

            edited_df = st.data_editor(
                pd.DataFrame(rel_data),
                key="relationship_editor",
                disabled=["Source", "Target", "Cardinality", "Confidence"],
                use_container_width=True
            )

            # Apply user accept/reject decisions to the actual relationship objects
            if edited_df is not None and not edited_df.empty:
                changed = False
                for idx, row in edited_df.iterrows():
                    if idx < len(candidates):
                        new_status = "ACCEPTED" if row.get("Accept") else "REJECTED"
                        curr_status = candidates[idx].status.value if hasattr(candidates[idx].status, "value") else str(candidates[idx].status)
                        if curr_status != new_status:
                            candidates[idx].status = new_status
                            changed = True
                if changed:
                    RelationshipDetector.save_candidates(candidates, rel_path)

            # Build DataModel to generate ERD
            from src.data_model import DataModel, TableSchema, ColumnSchema
            from src.er_generator import ERGenerator

            tables = {}
            for tname in ws.registry.keys():
                df, _ = ws.load_table(tname)
                cols = {}
                for c in df.columns:
                    is_uniq = bool(len(df) > 0 and df[c].nunique(dropna=False) == len(df))
                    cols[c] = ColumnSchema(name=c, type=str(df[c].dtype), is_unique=is_uniq)
                tables[tname] = TableSchema(name=tname, row_count=len(df), columns=cols)

            accepted_rels = [
                r for r in candidates
                if (r.status == "ACCEPTED" or (hasattr(r.status, "value") and r.status.value == "ACCEPTED"))
            ]
            dm = DataModel(tables=tables, relationships=accepted_rels)
            er_gen = ERGenerator()
            dot_str = er_gen.generate_dot(dm)

            st.markdown("### Entity Relationship Diagram")
            st.graphviz_chart(dot_str)

def render_feature_engineering(ws: 'ProjectWorkspace'):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Feature Engineering</h2>
    </div>
    ''', unsafe_allow_html=True)

    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="fe_table")

    from src.feature_engineering import FeatureEngine, build_arithmetic, build_date_part
    from src.sql_engine import DuckDBEngine

    fe = FeatureEngine(DuckDBEngine(ws), ws)
    features = fe.get_features(target_table)

    if features:
        st.dataframe(pd.DataFrame([f.__dict__ for f in features]))
    else:
        st.info("No features defined.")

    st.markdown("### Create Feature")
    feature_name = st.text_input("New Feature Name", key="fe_name")
    feature_type = st.selectbox("Feature Type", ["Arithmetic", "Date Part"], key="fe_type")

    # Get columns safely
    df, _ = ws.load_table(target_table)
    columns = list(df.columns)

    if feature_type == "Arithmetic":
        col1, col2, col3 = st.columns(3)
        with col1:
            left_col = st.selectbox("Left Column", columns, key="fe_arith_l")
        with col2:
            op = st.selectbox("Operator", ["+", "-", "*", "/"], key="fe_arith_op")
        with col3:
            right_col = st.selectbox("Right Column", columns, key="fe_arith_r")

        if dataforge_button("Create Arithmetic Feature", type="primary"):
            def _do_action():
                if not feature_name:
                    st.error("Please provide a feature name.")
                    return
                try:
                    fd = build_arithmetic(feature_name, target_table, left_col, op, right_col)
                    fe.create_feature(fd)
                    st.success(f"Feature '{feature_name}' created successfully.")
                except Exception as e:
                    st.error(f"Error: {e}")
            run_action("Create Feature", [("Generating code...", _do_action)])

    elif feature_type == "Date Part":
        col1, col2 = st.columns(2)
        with col1:
            date_col = st.selectbox("Date Column", columns, key="fe_date_col")
        with col2:
            unit = st.selectbox("Part to Extract", ["year", "month", "day", "hour", "minute"], key="fe_date_unit")

        if dataforge_button("Extract Date Part", type="primary"):
            def _do_action():
                if not feature_name:
                    st.error("Please provide a feature name.")
                    return
                try:
                    fd = build_date_part(feature_name, target_table, date_col, unit)
                    fe.create_feature(fd)
                    st.success(f"Feature '{feature_name}' created successfully.")
                except Exception as e:
                    st.error(f"Error: {e}")
            run_action("Extract Date Part", [("Generating code...", _do_action)])

def render_sql_workspace(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">SQL Workspace</h2>
    </div>
    ''', unsafe_allow_html=True)
    from src.sql_engine import DuckDBEngine
    first_tbl = list(ws.registry.keys())[0] if ws.registry else "dataset"
    default_q = f'SELECT * FROM "{first_tbl}" LIMIT 5'
    query = st.text_area("SQL Query", default_q)
    if dataforge_button("Run Query", type="primary", key="btn_run_sql_query"):
        def _do_action():
            try:
                db = DuckDBEngine(ws)
                st.session_state.sql_result_df = db.execute_query(query)
                db.close()
            except Exception as e:
                st.session_state.sql_result_df = None
                st.error(f"Error: {e}")

        from ui.components import run_action
        run_action("Run Query", [("Executing query...", _do_action)])

    if st.session_state.get("sql_result_df") is not None:
        st.dataframe(st.session_state.sql_result_df)

def render_pandas_analysis(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Pandas Analysis</h2>
    </div>
    ''', unsafe_allow_html=True)
    st.info("Select a table to analyze.")
    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="pa_table")
    if dataforge_button("Describe", type="primary"):
        def _do_action():
            df, _ = ws.load_table(target_table)
            st.session_state.pandas_describe_df = df.describe()

        from ui.components import run_action
        run_action("Describe Table", [("Profiling table...", _do_action)])

    if st.session_state.get("pandas_describe_df") is not None:
        st.dataframe(st.session_state.pandas_describe_df)
def render_kpi_center(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">KPI Center</h2>
    </div>
    ''', unsafe_allow_html=True)
    if dataforge_button("Generate KPIs", type="primary"):
        def _do_action():
            from src.kpi_engine import KPIEngine
            eng = KPIEngine()
            st.session_state.kpis = []
            for tname in ws.registry.keys():
                df, _ = ws.load_table(tname)
                t_res = st.session_state.get("table_results", {}).get(tname, {})
                st.session_state.kpis.extend(eng.recommend_kpis(len(df), t_res.get("type_results", []), t_res.get("all_issues", [])))
            st.session_state.kpis_generated_banner = True

        from ui.components import run_action
        run_action("Generate KPIs", [("Synthesizing metrics...", _do_action)])

    if st.session_state.get("kpis_generated_banner"):
        st.success("KPIs generated.")

    if "kpis" in st.session_state:
        st.dataframe(pd.DataFrame([__import__("dataclasses").asdict(k) for k in st.session_state.kpis]))

        st.markdown("### KPI Snapshots")
        from src.kpi_engine import KPIManager, KPISnapshot
        import uuid
        import datetime

        km = KPIManager(ws)
        if dataforge_button("Create Snapshot", type="primary", key="snap_btn"):
            def _do_snap():
                from src.dataset_versioning import DatasetVersioningManager
                dvm = DatasetVersioningManager()
                dvm.persistence_dir = os.path.join(ws.project_root, ".dataforge")
                versions = dvm.get_all_versions()
                latest_v_id = versions[-1].version_id if versions else None

                snaps_created = 0
                for k in st.session_state.kpis:
                    try:
                        k_name = getattr(k, "kpi_name", getattr(k, "name", "KPI"))
                        slug = "".join([c if c.isalnum() else "_" for c in k_name.lower()])
                        k_id = getattr(k, "kpi_id", f"kpi_{slug}")

                        val, status_msg = km.calculate_kpi_value(k, ws)
                        if val is None:
                            st.warning(f"Could not calculate snapshot for '{k_name}': {status_msg}")
                            record_val = f"ERROR: {status_msg}"
                        else:
                            record_val = val

                        snap = KPISnapshot(
                            snapshot_id=str(uuid.uuid4()),
                            kpi_id=k_id,
                            kpi_name=k_name,
                            dataset_version_id=latest_v_id,
                            value=record_val,
                            recorded_at=datetime.datetime.now(datetime.UTC).isoformat()
                        )
                        km.save_snapshot(snap)
                        snaps_created += 1
                    except Exception as e:
                        print(f"Error creating snapshot: {e}")

                st.session_state.last_snaps_created = snaps_created

            from ui.components import run_action
            run_action("Create Snapshot", [("Evaluating KPIs...", _do_snap)])

        if st.session_state.get("last_snaps_created"):
            st.success(f"Created {st.session_state.last_snaps_created} KPI snapshots.")

        snapshots = km.load_snapshots()
        if not snapshots:
            st.info("No KPI snapshots logged yet.")
        else:
            st.dataframe(pd.DataFrame([s.to_dict() for s in snapshots]))
            if len(snapshots) >= 2:
                st.markdown("#### Compare Snapshots")
                snap_labels = {f"{s.snapshot_id[:8]} ({s.kpi_name} - v:{s.dataset_version_id or 'none'})": s.snapshot_id for s in snapshots}
                c1, c2 = st.columns(2)
                with c1:
                    sel_a = st.selectbox("Baseline Snapshot (A)", list(snap_labels.keys()), index=0, key="snap_comp_a")
                with c2:
                    sel_b = st.selectbox("Comparison Snapshot (B)", list(snap_labels.keys()), index=min(1, len(snapshots) - 1), key="snap_comp_b")
                if sel_a and sel_b:
                    comp_res = km.compare_snapshots(snap_labels[sel_a], snap_labels[sel_b])
                    st.json(comp_res)

def render_business_questions(ws: ProjectWorkspace):
    if not ws.registry:
        empty_state('No tables available', 'Import data first to explore business questions.', 'Go to Data Import', 'Data Import')
        return

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

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Business Questions</h2>
    </div>
    ''', unsafe_allow_html=True)
    from src.business_questions import QuestionManager
    qm = QuestionManager(ws)

    # Auto-generate suggestions grounded in schema and metrics
    if dataforge_button("Generate Schema Suggestions", type="primary"):
        def _do_action():
            created = qm.generate_schema_suggestions(
                table_results=st.session_state.get('table_results'),
                kpis=kpis
            )
            if created:
                st.session_state.suggestions_banner = f"Generated {len(created)} schema-aware question suggestion(s)."
            else:
                st.session_state.suggestions_banner = "All available schema-grounded question suggestions have already been generated."

        from ui.components import run_action
        run_action("Generate Schema Suggestions", [("Analyzing schema and metrics...", _do_action)])

    if st.session_state.get("suggestions_banner"):
        st.success(st.session_state.suggestions_banner)

    # Manual question creation form
    with st.expander("Add Custom Business Question", expanded=True):
        with st.form("custom_bq_form", clear_on_submit=False):
            q_text = st.text_input("Question *", placeholder="e.g. Which region experienced the highest revenue growth?", key="custom_q_input")
            col_a, col_b = st.columns(2)
            with col_a:
                kpi_names = ["None"] + [getattr(k, "kpi_name", getattr(k, "name", str(k))) for k in (kpis or [])]
                sel_kpi = st.selectbox("Related KPI (Optional)", kpi_names, key="custom_q_kpi")
            with col_b:
                sel_table = st.selectbox("Related Table (Optional)", ["None"] + list(ws.registry.keys()), key="custom_q_table")
            q_desc = st.text_area("Hypothesis / Context (Optional)", placeholder="Explain why this question matters to the business...", key="custom_q_desc")

            submitted = st.form_submit_button("Save Question", type="primary")
            if submitted:
                if not q_text.strip():
                    st.error("Question text cannot be empty.")
                else:
                    try:
                        new_q = qm.create_question(q_text.strip())
                        updates = {}
                        if q_desc.strip():
                            updates["description"] = q_desc.strip()
                        if sel_kpi != "None" and kpis:
                            match_kpi = next((k for k in kpis if getattr(k, "kpi_name", getattr(k, "name", "")) == sel_kpi), None)
                            if match_kpi:
                                updates["related_kpi_id"] = getattr(match_kpi, "kpi_id", None)
                        if updates:
                            qm.update_question(new_q.question_id, **updates)
                        st.session_state.question_saved_banner = True
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Failed to create question: {ex}")

    if st.session_state.get("question_saved_banner"):
        st.success("Question saved successfully.")

    active = qm.get_active_questions()
    st.markdown("### Active Business Questions")
    if active:
        st.dataframe(pd.DataFrame([q.dict() for q in active]), use_container_width=True)
    else:
        st.info("No active questions. Click 'Generate Schema Suggestions' or use the form above to add questions.")
def render_segmentation(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Segmentation</h2>
    </div>
    ''', unsafe_allow_html=True)

    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="seg_table")
    df, _ = ws.load_table(target_table)
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

    if not numeric_cols:
        st.warning("No numeric columns available in the selected table for segmentation.")
        return

    target_col = st.selectbox("Target Column", numeric_cols, key="seg_col")

    # We will provide a simple 3-tier High/Medium/Low segmentation
    st.markdown("### Create High/Medium/Low Segmentation")
    col1, col2 = st.columns(2)
    with col1:
        low_max = st.number_input("Low max (exclusive)", value=100.0, key="seg_low_max")
    with col2:
        med_max = st.number_input("Medium max (exclusive)", value=500.0, key="seg_med_max")

    if dataforge_button("Apply Segmentation", type="primary"):
        def _do_action():
            from src.segmentation_engine import SegmentationEngine, SegmentationConfig, SegmentDefinition, ExplicitThresholdRule
            from src.sql_engine import DuckDBEngine
            se = SegmentationEngine(ws, DuckDBEngine(ws))

            cfg = SegmentationConfig(
                table_name=target_table,
                column_name=target_col,
                segments=[
                    SegmentDefinition("Low", ExplicitThresholdRule(min_val=None, max_val=low_max, end_inclusive=False)),
                    SegmentDefinition("Medium", ExplicitThresholdRule(min_val=low_max, max_val=med_max, start_inclusive=True, end_inclusive=False)),
                    SegmentDefinition("High", ExplicitThresholdRule(min_val=med_max, max_val=None, start_inclusive=True))
                ]
            )
            try:
                res = se.apply_segmentation(cfg, mode="pandas")
                se.save_config("hml_segmentation", cfg)
                st.write("Segmentation summary:")
                st.dataframe(res.groupby('segment').size().reset_index(name='count'))
                st.success("Segments generated and saved.")
            except Exception as e:
                st.error(f"Error applying segmentation: {e}")

        run_action("Apply Segmentation", [("Clustering data points...", _do_action)])

def render_anomaly_detection(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Anomaly Detection</h2>
    </div>
    ''', unsafe_allow_html=True)

    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="anom_table")
    df, _ = ws.load_table(target_table)
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

    if not numeric_cols:
        st.warning("No numeric columns available for anomaly detection.")
        return

    target_col = st.selectbox("Target Column", numeric_cols, key="anom_col")

    col1, col2 = st.columns(2)
    with col1:
        method = st.selectbox("Detection Method", ["IQR", "Z-Score"], key="anom_method")
    with col2:
        threshold = st.number_input("Threshold", value=1.5 if method == "IQR" else 3.0, key="anom_thresh")

    if dataforge_button("Detect Outliers", type="primary"):
        def _do_action():
            from src.anomaly_engine import AnomalyEngine, OutlierAnalysisDefinition
            from src.sql_engine import DuckDBEngine
            ae = AnomalyEngine(ws, DuckDBEngine(ws))
            cfg = OutlierAnalysisDefinition(
                table_name=target_table,
                column_name=target_col,
                method=method.lower(),
                threshold=threshold
            )
            try:
                res = ae.analyze(cfg)
                ae.save_analysis("latest_anomaly", res)

                if res.outliers:
                    st.warning(f"Found {len(res.outliers)} anomalies (total rows: {res.total_rows}).")
                    outliers_df = pd.DataFrame([o.__dict__ for o in res.outliers])
                    st.dataframe(outliers_df)
                else:
                    st.success(f"No anomalies found in {res.total_rows} rows.")
            except Exception as e:
                st.error(f"Error detecting outliers: {e}")

        run_action("Detect Outliers", [("Scanning data for anomalies...", _do_action)])

def render_date_analysis(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action, empty_state

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Date Analysis</h2>
    </div>
    ''', unsafe_allow_html=True)

    if not ws.registry:
        empty_state("No tables available", "Import data first.", "Go to Data Import", "Data Import")
        return

    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="date_table")
    df, _ = ws.load_table(target_table)

    # Simple check for datetime-like columns or strings that look like dates
    # To keep it simple, we will just list all columns and let user select
    date_cols = list(df.columns)
    target_col = st.selectbox("Date Column", date_cols, key="date_col")

    missing_behavior = st.selectbox("Missing Date Behavior", ["pad", "drop", "keep"], key="date_missing")

    if dataforge_button("Generate Date Table", type="primary"):
        def _do_action():
            from src.date_analysis_engine import DateAnalysisEngine, DateDimensionConfig
            from src.sql_engine import DuckDBEngine
            import uuid

            de = DateAnalysisEngine(ws, DuckDBEngine(ws))
            cfg_id = str(uuid.uuid4())

            cfg = DateDimensionConfig(
                config_id=cfg_id,
                source_table=target_table,
                date_column=target_col,
                user_min_date=None,
                user_max_date=None,
                missing_date_behavior=missing_behavior
            )
            try:
                de.register_config(cfg)
                res_df = de.generate_date_table_pandas(cfg_id)
                st.success("Date table generated successfully.")
                st.dataframe(res_df.head())
            except Exception as e:
                st.error(f"Error generating date table: {e}. Ensure column is convertible to dates.")

        run_action("Generate Date Table", [("Building date dimension...", _do_action)])

def parse_rca_condition_value(df_table: pd.DataFrame, col_name: str, op: str, raw_val: Any):
    """Safely and type-accurately parses a condition value for RCA filters."""
    if op in ["IS_NULL", "IS_NOT_NULL"]:
        return None, None
    if raw_val is None or not str(raw_val).strip():
        return None, f"Condition value for '{col_name}' cannot be empty."
    raw_str = str(raw_val).strip()
    col_series = df_table[col_name]
    if op == "IN":
        items = [x.strip() for x in raw_str.split(",") if x.strip()]
        if not items:
            return None, f"Condition 'IN' on '{col_name}' requires at least one comma-separated value."
        if pd.api.types.is_bool_dtype(col_series):
            parsed = []
            for x in items:
                if x.lower() in ["true", "1", "t", "yes"]:
                    parsed.append(True)
                elif x.lower() in ["false", "0", "f", "no"]:
                    parsed.append(False)
                else:
                    return None, f"Values for boolean column '{col_name}' must be True or False."
            return parsed, None
        elif pd.api.types.is_integer_dtype(col_series):
            try:
                return [int(x) for x in items], None
            except ValueError:
                return None, f"Values for integer column '{col_name}' must be integers."
        elif pd.api.types.is_numeric_dtype(col_series):
            try:
                return [float(x) for x in items], None
            except ValueError:
                return None, f"Values for numeric column '{col_name}' must be numbers."
        else:
            return items, None
    else:
        if pd.api.types.is_bool_dtype(col_series):
            if raw_str.lower() in ["true", "1", "t", "yes"]:
                return True, None
            elif raw_str.lower() in ["false", "0", "f", "no"]:
                return False, None
            else:
                return None, f"Value '{raw_str}' must be True or False for boolean column '{col_name}'."
        elif pd.api.types.is_integer_dtype(col_series):
            try:
                return int(raw_str), None
            except ValueError:
                return None, f"Value '{raw_str}' must be an integer for column '{col_name}'."
        elif pd.api.types.is_numeric_dtype(col_series):
            try:
                return float(raw_str), None
            except ValueError:
                return None, f"Value '{raw_str}' must be a number for column '{col_name}'."
        else:
            return raw_str, None

def render_rca(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    import os
    import time
    import hashlib
    from ui.components import dataforge_button, run_action, empty_state
    from ui.theme import badge
    from src.rca_engine import RCAEngine, RCAAnalysisDefinition, RCACondition
    from src.kpi_engine import KPIManager, KPIDefinition, MetricDefinition
    from src.data_model import DataModel, TableSchema, ColumnSchema, RelationshipCandidate, RelationshipStatus

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Root Cause Analysis</h2>
    </div>
    ''', unsafe_allow_html=True)

    if not ws.registry:
        empty_state("No tables available", "Import data first to perform Root Cause Analysis.", "Go to Data Import", "Data Import")
        return

    # Sync and load KPIs
    km = KPIManager(ws)
    kpis = km.load_kpis()
    if not kpis and st.session_state.get('kpis'):
        for item in st.session_state['kpis']:
            if isinstance(item, KPIDefinition):
                km.save_kpi(item, overwrite=True)
            elif hasattr(item, "required_columns") and item.required_columns:
                col = item.required_columns[0]
                src_tbl = None
                for tname in ws.registry.keys():
                    df_t, _ = ws.load_table(tname)
                    if col in df_t.columns:
                        src_tbl = tname
                        break
                if not src_tbl:
                    continue
                calc = getattr(item, "calculation_logic", "").upper()
                op = "SUM"
                if "AVG" in calc or "AVERAGE" in calc:
                    op = "AVG"
                elif "COUNT" in calc:
                    op = "COUNT"
                elif "MIN" in calc:
                    op = "MIN"
                elif "MAX" in calc:
                    op = "MAX"
                slug = "".join([c if c.isalnum() else "_" for c in item.kpi_name.lower()])
                metric = MetricDefinition(
                    metric_name=item.kpi_name,
                    operation=op,
                    source_table=src_tbl,
                    source_column=col
                )
                kdef = KPIDefinition(
                    kpi_id=f"kpi_{slug}",
                    kpi_name=item.kpi_name,
                    business_definition=getattr(item, "explanation", ""),
                    formula=getattr(item, "calculation_logic", f"{op}({col})"),
                    metric_definitions=[metric],
                    source_tables=[src_tbl],
                    source_columns=[col],
                    unit="",
                    description=getattr(item, "explanation", "")
                )
                km.save_kpi(kdef, overwrite=True)
        kpis = km.load_kpis()

    if not kpis:
        empty_state("No KPIs available", "Generate or define KPIs first to perform Root Cause Analysis.", "Go to KPI Center", "KPI Center")
        return

    # Build DataModel from workspace and accepted relationships
    tables = {}
    for tname in ws.registry.keys():
        df_t, _ = ws.load_table(tname)
        cols = {}
        for c in df_t.columns:
            is_uniq = bool(len(df_t) > 0 and df_t[c].nunique(dropna=False) == len(df_t))
            cols[c] = ColumnSchema(name=c, type=str(df_t[c].dtype), is_unique=is_uniq)
        tables[tname] = TableSchema(name=tname, row_count=len(df_t), columns=cols)

    candidates = st.session_state.get("relationship_candidates", [])
    accepted_rels = [r for r in candidates if getattr(r.status, "value", str(r.status)).upper() == "ACCEPTED"]
    if not accepted_rels:
        try:
            from src.model_generator import ModelGenerator
            spec = ModelGenerator.load_specification(os.path.join(ws.project_root, ".dataforge"))
            if spec and "relationships" in spec:
                for r_dict in spec["relationships"]:
                    status = r_dict.get("status", "ACCEPTED")
                    if getattr(status, "value", str(status)).upper() == "ACCEPTED":
                        accepted_rels.append(RelationshipCandidate(
                            source_table=r_dict["source_table"],
                            source_column=r_dict["source_column"],
                            target_table=r_dict["target_table"],
                            target_column=r_dict["target_column"],
                            cardinality=r_dict.get("cardinality", "N:1"),
                            source_unique=r_dict.get("source_unique", False),
                            target_unique=r_dict.get("target_unique", True),
                            match_coverage=r_dict.get("match_coverage", 100.0),
                            orphan_rate=r_dict.get("orphan_rate", 0.0),
                            confidence=r_dict.get("confidence", 100.0),
                            evidence=r_dict.get("evidence", []),
                            status=RelationshipStatus.ACCEPTED
                        ))
        except Exception:
            pass

    dm = DataModel(tables=tables, relationships=accepted_rels)
    re = RCAEngine(ws, dm, km)

    valid_kpis = [k for k in kpis if k.metric_definitions and k.metric_definitions[0].source_table in ws.registry]
    if not valid_kpis:
        st.warning("No KPIs with valid tables found in current workspace.")
        return

    kpi_options = {k.kpi_id: f"{k.kpi_name} ({k.metric_definitions[0].operation} {k.metric_definitions[0].source_table}.{k.metric_definitions[0].source_column})" for k in valid_kpis}
    target_kpi_id = st.selectbox("Target Metric (KPI)", list(kpi_options.keys()), format_func=lambda x: kpi_options[x], key="rca_kpi")
    target_kpi = next((k for k in valid_kpis if k.kpi_id == target_kpi_id), valid_kpis[0])
    source_table = target_kpi.metric_definitions[0].source_table

    # Expose only evidence-backed dimension tables reachable via DataModel
    reachable_tables = re.get_reachable_tables(source_table)
    candidate_dim_tables = [t for t in reachable_tables if t in ws.registry]
    if not candidate_dim_tables:
        candidate_dim_tables = [source_table]

    st.markdown("#### Dimension Analysis")
    c_dim_t, c_dim_c = st.columns(2)
    with c_dim_t:
        dim_table = st.selectbox(
            "Dimension Table",
            candidate_dim_tables,
            key="rca_dim_table",
            help="Only tables reachable via accepted relationships in the Data Model are exposed."
        )
    df_dim, _ = ws.load_table(dim_table)
    with c_dim_c:
        dim_col = st.selectbox("Dimension Column to Analyze", list(df_dim.columns), key="rca_dim_col")

    col1, col2 = st.columns([1, 2])
    with col1:
        baseline = st.selectbox("Baseline Type", ["BASELINE_ALL", "BASELINE_COMPLEMENT"], key="rca_baseline")
    with col2:
        problem = st.text_input("Problem Statement", value=f"Why did {target_kpi.kpi_name} deviate?", key="rca_prob")

    st.markdown("#### Affected Cohort Filter")
    st.caption("Define the condition(s) on the source table identifying the affected cohort.")

    df_source, _ = ws.load_table(source_table)
    source_cols = list(df_source.columns)

    OP_LABELS = {
        "EQUALS": "= (Equals)",
        "NOT_EQUALS": "!= (Not Equals)",
        "GREATER_THAN": "> (Greater Than)",
        "LESS_THAN": "< (Less Than)",
        "GREATER_THAN_OR_EQUAL": ">= (Greater Than or Equal)",
        "LESS_THAN_OR_EQUAL": "<= (Less Than or Equal)",
        "IN": "IN (List of Values)",
        "IS_NULL": "IS NULL (Missing)",
        "IS_NOT_NULL": "IS NOT NULL (Present)"
    }

    f1, f2, f3 = st.columns([2, 2, 3])
    with f1:
        c1_col = st.selectbox("Condition Column", source_cols, key="rca_c1_col")
    with f2:
        c1_op = st.selectbox("Operator", list(OP_LABELS.keys()), format_func=lambda x: OP_LABELS[x], key="rca_c1_op")
    with f3:
        if c1_op in ["IS_NULL", "IS_NOT_NULL"]:
            st.text_input("Value", value="[No value needed]", disabled=True, key="rca_c1_unary")
            c1_val_raw = None
        else:
            c1_val_raw = st.text_input("Condition Value", key="rca_c1_val", placeholder="e.g. Low, 10, True")

    add_second = st.checkbox("Add secondary condition (optional)", key="rca_add_c2")
    c2_col, c2_op, c2_val_raw = None, None, None
    log_op = "AND"
    if add_second:
        l_col, f2_1, f2_2, f2_3 = st.columns([1, 2, 2, 3])
        with l_col:
            log_op = st.selectbox("Logic", ["AND", "OR"], key="rca_log_op")
        with f2_1:
            c2_col = st.selectbox("Second Column", source_cols, key="rca_c2_col")
        with f2_2:
            c2_op = st.selectbox("Second Operator", list(OP_LABELS.keys()), format_func=lambda x: OP_LABELS[x], key="rca_c2_op")
        with f2_3:
            if c2_op in ["IS_NULL", "IS_NOT_NULL"]:
                st.text_input("Second Value", value="[No value needed]", disabled=True, key="rca_c2_unary")
                c2_val_raw = None
            else:
                c2_val_raw = st.text_input("Second Value", key="rca_c2_val", placeholder="e.g. High, 100")

    _parse_condition_value = parse_rca_condition_value

    if dataforge_button("Run RCA", type="primary"):
        if not problem.strip():
            st.error("Problem statement cannot be empty.")
            return

        v1_parsed, err1 = _parse_condition_value(df_source, c1_col, c1_op, c1_val_raw)
        if err1:
            st.error(err1)
            return
        conditions = [RCACondition(column=c1_col, operator=c1_op, value=v1_parsed)]

        if add_second:
            v2_parsed, err2 = _parse_condition_value(df_source, c2_col, c2_op, c2_val_raw)
            if err2:
                st.error(err2)
                return
            conditions.append(RCACondition(column=c2_col, operator=c2_op, value=v2_parsed, logical_operator=log_op))

        def _do_action():
            cond_key = "_".join([f"{c.column}_{c.operator}_{c.value}_{c.logical_operator}" for c in conditions])
            hash_str = f"{problem.strip()}_{source_table}_{target_kpi_id}_{dim_table}_{dim_col}_{baseline}_{cond_key}"
            analysis_id = "rca_" + hashlib.sha256(hash_str.encode("utf-8")).hexdigest()[:12]

            cfg = RCAAnalysisDefinition(
                analysis_id=analysis_id,
                problem_definition=problem.strip(),
                source_table=source_table,
                target_metric_kpi_id=target_kpi_id,
                affected_conditions=conditions,
                baseline_type=baseline,
                dimension_table=dim_table,
                dimension_column=dim_col,
                created_at=time.time()
            )

            try:
                results = re.execute(cfg)
                re.save_analysis(cfg)
                re.save_result(results, analysis_id=cfg.analysis_id)
                st.session_state["rca_latest_result"] = {
                    "results": results,
                    "analysis_id": analysis_id,
                    "target_kpi": target_kpi.kpi_name,
                    "dim_table": dim_table,
                    "dim_col": dim_col
                }
                st.session_state.rca_success = True
            except Exception as e:
                import traceback
                print(f"[RCA Error] {e}\n{traceback.format_exc()}")
                raise e

        run_action("Run RCA", [("Analyzing root cause associations...", _do_action)])

    if st.session_state.get("rca_success"):
        st.success("Root Cause Analysis completed successfully.")

    # Display results if available
    if "rca_latest_result" in st.session_state:
        res_data = st.session_state["rca_latest_result"]
        results = res_data.get("results", [])
        if not results:
            st.info("No dimension groups found for the specified conditions.")
        else:
            st.markdown("### Analysis Results")
            classifications = [r.association_classification for r in results]
            if "Large Observed Association" in classifications:
                overall = "Large Observed Association"
                badge_type = "danger"
            elif "Observed Association" in classifications:
                overall = "Observed Association"
                badge_type = "warning"
            else:
                overall = "Insufficient Evidence"
                badge_type = "neutral"

            st.markdown(f"**Overall Classification:** {badge(overall, badge_type)}", unsafe_allow_html=True)
            st.caption("Note: Associations reflect observed statistical differences between cohorts, not causal proof.")

            rows = []
            for r in results:
                rows.append({
                    "Dimension Value": str(r.dimension_value),
                    "Affected Metric": round(r.affected_metric_value, 2) if r.affected_metric_value is not None else "N/A",
                    "Baseline Metric": round(r.baseline_metric_value, 2) if r.baseline_metric_value is not None else "N/A",
                    "Absolute Diff": round(r.absolute_difference, 2) if r.absolute_difference is not None else "N/A",
                    "Relative Diff %": f"{r.relative_difference_pct:+.1f}%" if r.relative_difference_pct is not None else "N/A",
                    "Affected Sample": r.affected_sample_size,
                    "Baseline Sample": r.baseline_sample_size,
                    "Classification": r.association_classification
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)


def render_findings(ws: 'ProjectWorkspace'):
    import streamlit as st
    import pandas as pd
    from ui.components import dataforge_button, run_action

    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Findings</h2>
    </div>
    ''', unsafe_allow_html=True)
    from src.finding_engine import FindingEngine, FindingDefinition
    import time, uuid

    fe = FindingEngine(ws)
    findings = fe.load_findings()
    if findings:
        st.dataframe(pd.DataFrame([f.dict() for f in findings]))
    else:
        st.info("No findings.")

    st.markdown("### Record New Finding")
    problem = st.text_input("Problem / Subject", key="fnd_prob")
    evidence = st.text_area("Evidence Statement", key="fnd_ev")

    if dataforge_button("Record Finding", type="primary"):
        def _do_action():
            if not problem or not evidence:
                st.error("Please provide both problem and evidence.")
                return
            fd = FindingDefinition(
                finding_id=str(uuid.uuid4()),
                problem=problem,
                evidence_statement=evidence,
                created_at=time.time(),
                updated_at=time.time()
            )
            fe.save_finding(fd)
            st.success("Finding recorded.")

        run_action("Record Finding", [("Saving finding...", _do_action)])

def render_recommendations(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Recommendations</h2>
    </div>
    ''', unsafe_allow_html=True)
    if dataforge_button("View Recommendations"):
        def _do_action():
            st.success("No current recommendations. Increase Data Quality.")










        from ui.components import run_action
        run_action("View Recommendations", [("Fetching recommendations...", _do_action)])
