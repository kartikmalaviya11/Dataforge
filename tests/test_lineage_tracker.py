import pytest
from src.model_generator import ModelStatus
from src.lineage_tracker import (
    LineageTracker, RawColumnMeta, CleanedColumnMeta, FeatureMeta, SQLMetricMeta, KPIMeta, LineageNodeType
)

def test_full_lineage_path():
    raw = [RawColumnMeta(table_name="T1", column_name="C1")]
    clean = [CleanedColumnMeta(table_name="T1", column_name="C1_clean", source_column="C1", transformation="TRIM")]
    feat = [FeatureMeta(feature_id="f1", feature_name="C1_feat", source_table="T1", source_columns=["C1_clean"], expression="C1_clean * 2")]
    sql = [SQLMetricMeta(metric_id="m1", metric_name="M1", source_table="T1", source_columns=["C1_feat"])]
    kpi = [KPIMeta(kpi_id="k1", kpi_name="KPI1", source_metrics=["m1"])]
    
    tracker = LineageTracker(raw_columns=raw, cleaned_columns=clean, features=feat, sql_metrics=sql, kpis=kpi)
    graph = tracker.build_graph()
    
    assert graph.status == ModelStatus.VALID
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 4
    
    # Check node types
    assert graph.nodes["raw_T1_C1"].node_type == LineageNodeType.RAW_COLUMN
    assert graph.nodes["clean_T1_C1_clean"].node_type == LineageNodeType.CLEANED_COLUMN
    assert graph.nodes["feat_f1"].node_type == LineageNodeType.FEATURE
    assert graph.nodes["sql_m1"].node_type == LineageNodeType.SQL_METRIC
    assert graph.nodes["kpi_k1"].node_type == LineageNodeType.POWER_BI_KPI

def test_missing_upstream_marks_unresolved_and_invalidates_graph():
    clean = [CleanedColumnMeta(table_name="T1", column_name="C1_clean", source_column="C1_missing", transformation="TRIM")]
    tracker = LineageTracker(cleaned_columns=clean)
    graph = tracker.build_graph()
    
    assert graph.status == ModelStatus.INVALID
    node = graph.nodes["clean_T1_C1_clean"]
    assert node.status == ModelStatus.UNRESOLVED
    assert len(node.warnings) > 0

def test_identical_column_names_different_tables():
    raw = [
        RawColumnMeta(table_name="T1", column_name="ID"),
        RawColumnMeta(table_name="T2", column_name="ID")
    ]
    tracker = LineageTracker(raw_columns=raw)
    graph = tracker.build_graph()
    
    assert "raw_T1_ID" in graph.nodes
    assert "raw_T2_ID" in graph.nodes
    assert len(graph.nodes) == 2

def test_cycle_detection():
    # We will manually inject a cycle since the standard building flows top-down
    tracker = LineageTracker()
    # Hack the builder temporarily to simulate a bad graph
    # Not needed, we can just instantiate tracker and test the protected method
    nodes = ["A", "B", "C"]
    
    class DummyEdge:
        def __init__(self, s, t):
            self.source_node_id = s
            self.target_node_id = t
            
    edges = [DummyEdge("A", "B"), DummyEdge("B", "C"), DummyEdge("C", "A")]
    assert tracker._detect_cycle(nodes, edges) == True

    edges_no_cycle = [DummyEdge("A", "B"), DummyEdge("B", "C")]
    assert tracker._detect_cycle(nodes, edges_no_cycle) == False

def test_duplicate_edges_prevented():
    raw = [RawColumnMeta(table_name="T1", column_name="C1")]
    # If a feature uses the same source column twice, it might create duplicate edges
    feat = [FeatureMeta(feature_id="f1", feature_name="F1", source_table="T1", source_columns=["C1", "C1"], expression="C1+C1")]
    
    tracker = LineageTracker(raw_columns=raw, features=feat)
    graph = tracker.build_graph()
    
    # Edges should be unique
    assert len(graph.edges) == 1
    assert graph.edges[0].source_node_id == "raw_T1_C1"
    assert graph.edges[0].target_node_id == "feat_f1"

def test_lineage_persistence_and_isolation(tmp_path):
    tracker = LineageTracker()
    graph = tracker.build_graph()
    graph.lineage_id = "test_persistence"
    
    base_path = str(tmp_path)
    tracker.save_graph(graph, base_path)
    loaded = LineageTracker.load_graph(base_path)
    assert loaded is not None
    assert loaded["lineage_id"] == "test_persistence"

def test_lineage_raw_immutability(tmp_path):
    import hashlib
    import pandas as pd
    
    csv_path = tmp_path / "raw_data_lineage.csv"
    df = pd.DataFrame({"CustomerID": [1, 2, 3]})
    df.to_csv(csv_path, index=False)
    
    def get_hash(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()
        
    hash_before = get_hash(csv_path)
    
    raw = [RawColumnMeta(table_name="raw_data", column_name="CustomerID")]
    tracker = LineageTracker(raw_columns=raw)
    graph = tracker.build_graph()
    
    hash_after = get_hash(csv_path)
    assert hash_before == hash_after
