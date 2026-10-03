import pytest
import pandas as pd
from src.data_model import RelationshipCandidate, RelationshipStatus, Cardinality, DataModel, TableSchema
from src.relationship_engine import RelationshipDetector
from src.er_generator import ERGenerator

def test_ground_truth_cardinalities():
    # 1:1
    df1 = pd.DataFrame({'id1': [1,2,3]})
    df2 = pd.DataFrame({'id2': [1,2,3]})
    
    detector = RelationshipDetector()
    candidates = detector.detect({"table1": df1, "table2": df2})
    
    assert len(candidates) == 2  # t1->t2 and t2->t1
    assert candidates[0].cardinality == Cardinality.ONE_TO_ONE
    assert candidates[1].cardinality == Cardinality.ONE_TO_ONE
    
    # 1:N / N:1
    df_parent = pd.DataFrame({'pk': [1,2,3]})
    df_child = pd.DataFrame({'fk': [1,1,2,2,3,3]})
    
    candidates = detector.detect({"parent": df_parent, "child": df_child})
    # child.fk -> parent.pk is N:1
    # parent.pk -> child.fk is 1:N
    c_n1 = next(c for c in candidates if c.source_table == "child" and c.target_table == "parent")
    assert c_n1.cardinality == Cardinality.MANY_TO_ONE
    assert c_n1.target_unique == True
    
    # duplicate parent keys (forces rejection if names differ)
    df_dup = pd.DataFrame({'other_col': [1,1,2]})
    candidates = detector.detect({"parent": df_dup, "child": df_child})
    assert len(candidates) == 0 # no PK target possible

def test_many_to_many_cardinality():
    df1 = pd.DataFrame({'shared_id': [1, 1, 2, 3]})
    df2 = pd.DataFrame({'shared_id': [1, 2, 2, 3]})
    
    detector = RelationshipDetector()
    candidates = detector.detect({"t1": df1, "t2": df2})
    
    c = next(c for c in candidates if c.source_table == "t1" and c.target_table == "t2")
    assert c.cardinality == Cardinality.MANY_TO_MANY
    assert c.source_unique == False
    assert c.target_unique == False

def test_orphan_foreign_keys():
    df_parent = pd.DataFrame({'pk': [1,2,3]})
    df_child = pd.DataFrame({'fk': [1,2,3,4]}) # 4 is orphan
    
    detector = RelationshipDetector()
    candidates = detector.detect({"parent": df_parent, "child": df_child})
    
    # We want child -> parent
    c = next(c for c in candidates if c.source_table == "child" and c.target_table == "parent")
    assert c.orphan_rate == 25.0 # 1 out of 4
    assert c.match_coverage == 75.0
    assert c.confidence < 100.0 # penalty applied

def test_false_positive_protections():
    # city, state, zip, status, price overlap
    df1 = pd.DataFrame({
        'city': ['Surat', 'Mumbai'],
        'state': ['GJ', 'MH'],
        'zip': [123, 456],
        'status': ['Active', 'Closed'],
        'amount': [100.5, 200.0]
    })
    
    df2 = pd.DataFrame({
        'city': ['Surat', 'Delhi'],
        'state': ['GJ', 'DL'],
        'postal': [123, 789],
        'status': ['Active', 'Pending'],
        'price': [100.5, 300.0]
    })
    
    detector = RelationshipDetector()
    candidates = detector.detect({"t1": df1, "t2": df2})
    assert len(candidates) == 0, "False positives detected!"

def test_determinism():
    df_parent = pd.DataFrame({'customer_id': [1,2,3], 'city': ['A','B','C']})
    df_child = pd.DataFrame({'customer_id': [1,2,3], 'order_id': [10,20,30]})
    
    detector = RelationshipDetector()
    
    results = []
    for _ in range(10):
        # We pass tables in different dict order if possible, though python dicts are ordered.
        # Just running it 10 times to ensure internal sets/dicts sorting is deterministic.
        candidates = detector.detect({"child": df_child, "parent": df_parent})
        results.append(candidates)
        
    for i in range(1, 10):
        assert results[0] == results[i]

def test_er_generator():
    model = DataModel(
        tables={},
        relationships=[
            RelationshipCandidate(
                source_table="orders", source_column="customer_id",
                target_table="customers", target_column="customer_id",
                cardinality=Cardinality.MANY_TO_ONE,
                source_unique=False, target_unique=True,
                match_coverage=100.0, orphan_rate=0.0,
                confidence=95.0, evidence=[], status=RelationshipStatus.ACCEPTED
            )
        ]
    )
    
    gen = ERGenerator()
    dot = gen.generate_dot(model)
    assert "orders" in dot
    assert "customers" in dot
    assert "customer_id" in dot

def test_single_table_empty():
    detector = RelationshipDetector()
    candidates = detector.detect({"single": pd.DataFrame({'a': [1,2,3]})})
    assert len(candidates) == 0

def test_datatype_mismatch():
    df1 = pd.DataFrame({'pk': [1,2,3]})
    df2 = pd.DataFrame({'fk': ["1","2","3"]})
    detector = RelationshipDetector()
    candidates = detector.detect({"t1": df1, "t2": df2})
    assert len(candidates) == 0

def test_null_heavy_columns():
    df1 = pd.DataFrame({'pk': [1, 2, 3, None, None, None]})
    df2 = pd.DataFrame({'fk': [1, None, None, None, None, None]})
    detector = RelationshipDetector()
    candidates = detector.detect({"t1": df1, "t2": df2})
    assert len(candidates) == 1
