from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any

class RelationshipStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class Cardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:M"

@dataclass
class RelationshipCandidate:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    cardinality: str # Serialized Cardinality
    source_unique: bool
    target_unique: bool
    match_coverage: float
    orphan_rate: float
    confidence: float
    evidence: List[str]
    status: str # Serialized RelationshipStatus

@dataclass
class ColumnSchema:
    name: str
    type: str
    semantic_type: Optional[str] = None
    is_unique: bool = False
    null_rate: float = 0.0

@dataclass
class TableSchema:
    name: str
    row_count: int
    columns: Dict[str, ColumnSchema]

@dataclass
class DataModel:
    tables: Dict[str, TableSchema]
    relationships: List[RelationshipCandidate]
    version: str = "1.0"
