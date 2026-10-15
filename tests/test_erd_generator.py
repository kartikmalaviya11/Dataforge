import pytest
from src.er_generator import ERGenerator
from src.data_model import DataModel, TableSchema, ColumnSchema, RelationshipCandidate

def test_erd_generator_valid_relationships():
    t1 = TableSchema(name="customers", row_count=100, columns={
        "id": ColumnSchema("id", "int", is_unique=True),
        "name": ColumnSchema("name", "str")
    })
    t2 = TableSchema(name="orders", row_count=500, columns={
        "order_id": ColumnSchema("order_id", "int", is_unique=True),
        "customer_id": ColumnSchema("customer_id", "int")
    })
    
    rel = RelationshipCandidate(
        source_table="orders", source_column="customer_id",
        target_table="customers", target_column="id",
        cardinality="N:1", source_unique=False, target_unique=True,
        match_coverage=1.0, orphan_rate=0.0, confidence=99.0, evidence=[],
        status="ACCEPTED"
    )
    
    dm = DataModel(tables={"customers": t1, "orders": t2}, relationships=[rel])
    gen = ERGenerator()
    dot = gen.generate_dot(dm)
    
    assert "digraph ER {" in dot
    assert "customers [label=<" in dot
    assert "orders [label=<" in dot
    assert "id (PK)" in dot
    assert "order_id (PK)" in dot
    assert "orders:customer_id -> customers:id [label=\"N:1\"];" in dot

def test_erd_generator_empty_state():
    dm = DataModel(tables={}, relationships=[])
    gen = ERGenerator()
    dot = gen.generate_dot(dm)
    assert "digraph ER {" in dot
    assert "->" not in dot

def test_erd_generator_ignores_unaccepted_relationships():
    t1 = TableSchema(name="a", row_count=100, columns={"id": ColumnSchema("id", "int")})
    t2 = TableSchema(name="b", row_count=100, columns={"a_id": ColumnSchema("a_id", "int")})
    rel = RelationshipCandidate(
        source_table="b", source_column="a_id", target_table="a", target_column="id",
        cardinality="N:1", source_unique=False, target_unique=False,
        match_coverage=1.0, orphan_rate=0.0, confidence=50.0, evidence=[],
        status="CANDIDATE"
    )
    dm = DataModel(tables={"a": t1, "b": t2}, relationships=[rel])
    gen = ERGenerator()
    dot = gen.generate_dot(dm)
    
    assert "a [label=<" in dot
    assert "b [label=<" in dot
    assert "->" not in dot
