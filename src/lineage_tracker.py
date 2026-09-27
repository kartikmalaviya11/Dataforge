import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from src.model_generator import ModelStatus

class LineageNodeType(Enum):
    RAW_COLUMN = "RAW_COLUMN"
    CLEANED_COLUMN = "CLEANED_COLUMN"
    FEATURE = "FEATURE"
    SQL_METRIC = "SQL_METRIC"
    POWER_BI_KPI = "POWER_BI_KPI"

@dataclass
class LineageNode:
    node_id: str
    node_type: LineageNodeType
    object_name: str
    table_name: Optional[str]
    column_name: Optional[str]
    created_at: float
    status: ModelStatus
    warnings: List[str]
    metadata: Dict[str, str] = field(default_factory=dict)

@dataclass
class LineageEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    transformation: str
    source_phase: str

@dataclass
class DataLineageGraph:
    lineage_id: str
    nodes: Dict[str, LineageNode]
    edges: List[LineageEdge]
    status: ModelStatus
    created_at: float
    updated_at: float

# Dummy definitions for input
@dataclass
class RawColumnMeta:
    table_name: str
    column_name: str

@dataclass
class CleanedColumnMeta:
    table_name: str
    column_name: str
    source_column: str
    transformation: str

@dataclass
class FeatureMeta:
    feature_id: str
    feature_name: str
    source_table: str
    source_columns: List[str]
    expression: str

@dataclass
class SQLMetricMeta:
    metric_id: str
    metric_name: str
    source_table: str
    source_columns: List[str]

@dataclass
class KPIMeta:
    kpi_id: str
    kpi_name: str
    source_metrics: List[str]

class LineageTracker:
    def __init__(self, raw_columns: List[RawColumnMeta] = None, 
                 cleaned_columns: List[CleanedColumnMeta] = None, 
                 features: List[FeatureMeta] = None, 
                 sql_metrics: List[SQLMetricMeta] = None, 
                 kpis: List[KPIMeta] = None):
        self.raw_columns = raw_columns or []
        self.cleaned_columns = cleaned_columns or []
        self.features = features or []
        self.sql_metrics = sql_metrics or []
        self.kpis = kpis or []

    def build_graph(self) -> DataLineageGraph:
        nodes = {}
        edges = []
        status = ModelStatus.VALID
        
        # 1. Add Raw Columns
        for r in self.raw_columns:
            nid = f"raw_{r.table_name}_{r.column_name}"
            nodes[nid] = LineageNode(
                node_id=nid, node_type=LineageNodeType.RAW_COLUMN,
                object_name=r.column_name, table_name=r.table_name, column_name=r.column_name,
                created_at=time.time(), status=ModelStatus.VALID, warnings=[]
            )
            
        # 2. Add Cleaned Columns
        for c in self.cleaned_columns:
            nid = f"clean_{c.table_name}_{c.column_name}"
            src_id = f"raw_{c.table_name}_{c.source_column}"
            
            node_status = ModelStatus.VALID
            warnings = []
            if src_id not in nodes:
                node_status = ModelStatus.UNRESOLVED
                warnings.append(f"Missing upstream RAW_COLUMN: {src_id}")
                status = ModelStatus.INVALID
            else:
                edges.append(LineageEdge(
                    edge_id=f"{src_id}->{nid}",
                    source_node_id=src_id, target_node_id=nid,
                    transformation=c.transformation, source_phase="Cleaning"
                ))
                
            nodes[nid] = LineageNode(
                node_id=nid, node_type=LineageNodeType.CLEANED_COLUMN,
                object_name=c.column_name, table_name=c.table_name, column_name=c.column_name,
                created_at=time.time(), status=node_status, warnings=warnings
            )
            
        # 3. Add Features
        for f in self.features:
            nid = f"feat_{f.feature_id}"
            node_status = ModelStatus.VALID
            warnings = []
            
            for sc in f.source_columns:
                # Try cleaned first, then raw
                src_id = f"clean_{f.source_table}_{sc}"
                if src_id not in nodes:
                    src_id = f"raw_{f.source_table}_{sc}"
                    
                if src_id not in nodes:
                    node_status = ModelStatus.UNRESOLVED
                    warnings.append(f"Missing upstream column {sc} in {f.source_table} for feature {f.feature_id}")
                    status = ModelStatus.INVALID
                else:
                    edges.append(LineageEdge(
                        edge_id=f"{src_id}->{nid}",
                        source_node_id=src_id, target_node_id=nid,
                        transformation=f.expression, source_phase="FeatureEngineering"
                    ))
                    
            nodes[nid] = LineageNode(
                node_id=nid, node_type=LineageNodeType.FEATURE,
                object_name=f.feature_name, table_name=f.source_table, column_name=f.feature_name,
                created_at=time.time(), status=node_status, warnings=warnings
            )
            
        # 4. Add SQL Metrics
        for sm in self.sql_metrics:
            nid = f"sql_{sm.metric_id}"
            node_status = ModelStatus.VALID
            warnings = []
            
            for sc in sm.source_columns:
                # Try feature, then clean, then raw
                # simplified: assume metric uses features directly if matching name, else columns
                src_ids = []
                feat_src = next((x for x in nodes.values() if x.node_type == LineageNodeType.FEATURE and x.table_name == sm.source_table and x.column_name == sc), None)
                if feat_src:
                    src_ids.append(feat_src.node_id)
                else:
                    cl_src = f"clean_{sm.source_table}_{sc}"
                    if cl_src in nodes:
                        src_ids.append(cl_src)
                    else:
                        rw_src = f"raw_{sm.source_table}_{sc}"
                        if rw_src in nodes:
                            src_ids.append(rw_src)
                            
                if not src_ids:
                    node_status = ModelStatus.UNRESOLVED
                    warnings.append(f"Missing upstream for metric {sm.metric_id} col {sc}")
                    status = ModelStatus.INVALID
                else:
                    for src_id in src_ids:
                        edges.append(LineageEdge(
                            edge_id=f"{src_id}->{nid}",
                            source_node_id=src_id, target_node_id=nid,
                            transformation="SQL", source_phase="SQL_Metric"
                        ))
                        
            nodes[nid] = LineageNode(
                node_id=nid, node_type=LineageNodeType.SQL_METRIC,
                object_name=sm.metric_name, table_name=sm.source_table, column_name=None,
                created_at=time.time(), status=node_status, warnings=warnings
            )
            
        # 5. Add KPIs
        for k in self.kpis:
            nid = f"kpi_{k.kpi_id}"
            node_status = ModelStatus.VALID
            warnings = []
            
            for ms in k.source_metrics:
                src_id = f"sql_{ms}"
                if src_id not in nodes:
                    node_status = ModelStatus.UNRESOLVED
                    warnings.append(f"Missing upstream SQL metric {ms} for KPI {k.kpi_id}")
                    status = ModelStatus.INVALID
                else:
                    edges.append(LineageEdge(
                        edge_id=f"{src_id}->{nid}",
                        source_node_id=src_id, target_node_id=nid,
                        transformation="KPI", source_phase="KPI_Engine"
                    ))
                    
            nodes[nid] = LineageNode(
                node_id=nid, node_type=LineageNodeType.POWER_BI_KPI,
                object_name=k.kpi_name, table_name=None, column_name=None,
                created_at=time.time(), status=node_status, warnings=warnings
            )
            
        # Cycle Detection
        if self._detect_cycle(nodes, edges):
            status = ModelStatus.INVALID
            # optionally mark nodes as INVALID
            
        # Duplicate edge prevention is implicitly handled if we use a set for edges, but dataclass List is fine if we check
        unique_edges = []
        seen_edges = set()
        for e in edges:
            if e.edge_id not in seen_edges:
                seen_edges.add(e.edge_id)
                unique_edges.append(e)

        graph = DataLineageGraph(
            lineage_id="lineage_1",
            nodes=nodes,
            edges=unique_edges,
            status=status,
            created_at=time.time(),
            updated_at=time.time()
        )
        return graph
        
    def save_graph(self, graph: DataLineageGraph, base_path: str = ".dataforge"):
        import os, json, dataclasses
        os.makedirs(base_path, exist_ok=True)
        path = os.path.join(base_path, "lineage_graph.json")
        with open(path, "w") as f:
            json.dump(dataclasses.asdict(graph), f, indent=2, default=lambda x: x.value if isinstance(x, Enum) else x)

    @staticmethod
    def load_graph(base_path: str = ".dataforge") -> Optional[Dict]:
        import os, json
        path = os.path.join(base_path, "lineage_graph.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
            
    def _detect_cycle(self, nodes, edges) -> bool:
        adj = {n: [] for n in nodes}
        for e in edges:
            if e.source_node_id in adj:
                adj[e.source_node_id].append(e.target_node_id)
                
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False
            
        for n in nodes:
            if n not in visited:
                if dfs(n):
                    return True
        return False
