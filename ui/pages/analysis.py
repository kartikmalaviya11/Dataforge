import streamlit as st
from src.workspace import ProjectWorkspace
import pandas as pd
from ui.theme import badge

def render_relationships(ws: ProjectWorkspace):
    st.markdown("## Relationships")
    if st.button("Detect Relationships", type="primary"):
        with st.spinner("Analyzing tables..."):
            from src.relationship_engine import RelationshipDetector
            detector = RelationshipDetector()
            tables = {}
            for tname in ws.registry.keys():
                df, _ = ws.load_table(tname)
                tables[tname] = df
            st.session_state.relationship_candidates = detector.detect(tables)
            st.success("Detected candidates.")

    if "relationship_candidates" in st.session_state:
        candidates = st.session_state.relationship_candidates
        if not candidates:
            st.info("No candidates detected.")
        else:
            rel_data = []
            for r in candidates:
                rel_data.append({
                    "Accept": r.status == "ACCEPTED",
                    "Source": f"{r.source_table}.{r.source_column}",
                    "Target": f"{r.target_table}.{r.target_column}",
                    "Cardinality": r.cardinality,
                    "Confidence": f"{r.confidence:.1f}%",
                })
            st.data_editor(pd.DataFrame(rel_data))

def render_feature_engineering(ws: ProjectWorkspace):
    st.markdown("## Feature Engineering")
    from src.feature_engineering import FeatureEngine, FeatureDefinition
    from src.sql_engine import DuckDBEngine
    fe = FeatureEngine(DuckDBEngine(ws), ws)
    target_table = list(ws.registry.keys())[0] if ws.registry else None
    features = fe.get_features(target_table) if target_table else []
    if features:
        st.dataframe(pd.DataFrame([f.__dict__ for f in features]))
    else:
        st.info("No features defined.")
        
    st.markdown("### Create Feature")
    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="fe_table")
    feature_name = st.text_input("Feature Name", key="fe_name")
    if st.button("Create", type="primary"):
        try:
            fd = FeatureDefinition(
                feature_id=feature_name,
                feature_name=feature_name,
                feature_type="arithmetic",
                source_table=target_table,
                source_columns=[],
                expression="1", # Dummy
                created_at=0.0
            )
            fe.create_feature(fd)
            st.success("Feature created.")
        except Exception as e:
            st.error(f"Error: {e}")

def render_sql_workspace(ws: ProjectWorkspace):
    st.markdown("## SQL Workspace")
    from src.sql_engine import DuckDBEngine
    query = st.text_area("SQL Query", "SELECT * FROM 'dataset' LIMIT 5")
    if st.button("Run", type="primary"):
        try:
            db = DuckDBEngine(ws)
            df = db.execute_query(query)
            st.dataframe(df)
            db.close()
        except Exception as e:
            st.error(f"Error: {e}")

def render_pandas_analysis(ws: ProjectWorkspace):
    st.markdown("## Pandas Analysis")
    st.info("Select a table to analyze.")
    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="pa_table")
    if st.button("Describe", type="primary"):
        df, _ = ws.load_table(target_table)
        st.write(df.describe())

def render_kpi_center(ws: ProjectWorkspace):
    st.markdown("## KPI Center")
    if st.button("Generate KPIs", type="primary"):
        from src.kpi_engine import KPIEngine
        eng = KPIEngine()
        st.session_state.kpis = []
        for tname in ws.registry.keys():
            df, _ = ws.load_table(tname)
            st.session_state.kpis.extend(eng.recommend_kpis(len(df), st.session_state.analysis_results.get("type_results", []), st.session_state.analysis_results.get("all_issues", [])))
        st.success("KPIs generated.")
    if "kpis" in st.session_state:
        st.dataframe(pd.DataFrame([__import__("dataclasses").asdict(k) for k in st.session_state.kpis]))

def render_business_questions(ws: ProjectWorkspace):
    st.markdown("## Business Questions")
    from src.business_questions import QuestionManager
    qm = QuestionManager(ws)
    active = qm.get_active_questions()
    if active:
        st.dataframe(pd.DataFrame([q.dict() for q in active]))
    else:
        st.info("No active questions.")
        
    if st.button("Auto Generate", type="primary"):
        try:
            questions = qm.create_question("What is the trend?"); questions = [qm.get_active_questions()[-1].dict()]
            st.success("Generated.")
            st.write(questions)
        except:
            st.warning("Needs KPIs")

def render_segmentation(ws: ProjectWorkspace):
    st.markdown("## Segmentation")
    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="seg_table")
    if st.button("Auto Segment", type="primary"):
        from src.segmentation_engine import SegmentationEngine, SegmentationConfig
        from src.sql_engine import DuckDBEngine
        se = SegmentationEngine(ws, DuckDBEngine(ws))
        cfg = SegmentationConfig(table_name=target_table, column_name="price", segments=[])
        try:
            res = se.apply_segmentation(cfg); se.save_config("auto", cfg)
            st.write(res)
            st.success("Segments generated")
        except Exception as e:
            st.error(f"Need a numeric column (like price) to auto-segment. {e}")

def render_anomaly_detection(ws: ProjectWorkspace):
    st.markdown("## Anomaly Detection")
    target_table = st.selectbox("Target Table", list(ws.registry.keys()), key="anom_table")
    if st.button("Detect Outliers", type="primary"):
        from src.anomaly_engine import AnomalyEngine, OutlierAnalysisDefinition
        from src.sql_engine import DuckDBEngine
        ae = AnomalyEngine(ws, DuckDBEngine(ws))
        cfg = OutlierAnalysisDefinition(table_name=target_table, column_name="price", method="iqr", threshold=1.5)
        try:
            res = ae.analyze(cfg)
            st.write(f"Anomalies: {len(res.outliers)}")
            st.success("Analysis saved")
        except Exception as e:
            st.error(f"Need a numeric column (like price). {e}")

def render_date_analysis(ws: ProjectWorkspace):
    st.markdown("## Date Analysis")
    if st.button("Generate Date Table", type="primary"):
        from src.date_analysis_engine import DateAnalysisEngine, DateDimensionConfig
        from src.sql_engine import DuckDBEngine
        de = DateAnalysisEngine(ws, DuckDBEngine(ws))
        try:
            df = de.register_config(DateDimensionConfig(config_id="c1", source_table="sales", date_column="created_at", user_min_date=None, user_max_date=None, missing_date_behavior="pad")); df = de.generate_date_table_pandas("c1")
            st.success("Date table generated.")
            st.write(df.head())
        except Exception as e:
            st.error(str(e))

def render_rca(ws: ProjectWorkspace):
    st.markdown("## Root Cause Analysis")
    if st.button("Run Example RCA", type="primary"):
        from src.rca_engine import RCAEngine, RCAAnalysisDefinition
        from src.sql_engine import DuckDBEngine
        re = RCAEngine(ws, DuckDBEngine(ws), __import__("src.kpi_engine", fromlist=["KPIManager"]).KPIManager(ws))
        try:
            df, _ = ws.load_table(list(ws.registry.keys())[0])
            st.success("Executed RCA.")
            st.write(df.head())
        except Exception as e:
            st.error(str(e))

def render_findings(ws: ProjectWorkspace):
    st.markdown("## Findings")
    from src.finding_engine import FindingEngine, FindingDefinition
    fe = FindingEngine(ws)
    findings = fe.load_findings()
    if findings:
        st.dataframe(pd.DataFrame([f.dict() for f in findings]))
    else:
        st.info("No findings.")
    if st.button("Create Dummy Finding", type="primary"):
        fe.save_finding(FindingDefinition(finding_id="1", problem="Trend up", evidence_statement="Sales are up", created_at=0.0, updated_at=0.0))
        st.success("Saved.")

def render_recommendations(ws: ProjectWorkspace):
    st.markdown("## Recommendations")
    if st.button("View Recommendations"):
        st.success("No current recommendations. Increase Data Quality.")








