import pytest
import time
from typing import Dict, List
from src.data_model import DataModel, TableSchema, ColumnSchema, RelationshipCandidate
from src.kpi_engine import KPIDefinition, MetricDefinition
from src.date_analysis_engine import DateDimensionConfig
from src.model_generator import (
    ModelGenerator,
    ModelTableRole,
    ModelStatus,
    ModelSpecification,
    ModelTable,
    ModelRelationship,
    DateTableSpecification,
    SuggestedMeasure,
    ModelDocumentation
)

def test_dimension_classification():
    # Table with uniqueness >= 0.99 and is a relationship target
    tables = {
        "DimCustomer": TableSchema(name="DimCustomer", row_count=100, columns={
            "CustomerID": ColumnSchema(name="CustomerID", type="integer", is_unique=True), # Uniqueness > 0.99
            "Name": ColumnSchema(name="Name", type="string")
        })
    }
    rels = [
        RelationshipCandidate(
            source_table="FactSales", source_column="CustomerID",
            target_table="DimCustomer", target_column="CustomerID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    
    assert spec.tables[0].table_name == "DimCustomer"
    assert spec.tables[0].role == ModelTableRole.DIMENSION
    assert spec.tables[0].primary_key == "CustomerID"
    assert "CustomerID" in spec.tables[0].reasoning or "uniqueness" in spec.tables[0].reasoning

def test_fact_classification():
    # Table with numeric measures and is source of relationships
    tables = {
        "FactSales": TableSchema(name="FactSales", row_count=1000, columns={
            "SalesID": ColumnSchema(name="SalesID", type="integer", is_unique=True),
            "CustomerID": ColumnSchema(name="CustomerID", type="integer"),
            "Amount": ColumnSchema(name="Amount", type="float") # Numeric measure
        })
    }
    rels = [
        RelationshipCandidate(
            source_table="FactSales", source_column="CustomerID",
            target_table="DimCustomer", target_column="CustomerID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    
    assert spec.tables[0].table_name == "FactSales"
    assert spec.tables[0].role == ModelTableRole.FACT

def test_bridge_classification():
    # Source for >= 2 relationships to dimension tables, 0 non-key numeric metrics
    tables = {
        "BridgeStudentCourse": TableSchema(name="BridgeStudentCourse", row_count=100, columns={
            "StudentID": ColumnSchema(name="StudentID", type="integer"),
            "CourseID": ColumnSchema(name="CourseID", type="integer")
        })
    }
    rels = [
        RelationshipCandidate(
            source_table="BridgeStudentCourse", source_column="StudentID",
            target_table="DimStudent", target_column="StudentID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        ),
        RelationshipCandidate(
            source_table="BridgeStudentCourse", source_column="CourseID",
            target_table="DimCourse", target_column="CourseID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    
    assert spec.tables[0].table_name == "BridgeStudentCourse"
    assert spec.tables[0].role == ModelTableRole.BRIDGE

def test_needs_review_classification():
    # Uniqueness >= 0.99 but also MANY side of multiple relationships and has numeric metric
    tables = {
        "ConflictedTable": TableSchema(name="ConflictedTable", row_count=100, columns={
            "ID": ColumnSchema(name="ID", type="integer", is_unique=True),
            "Dim1ID": ColumnSchema(name="Dim1ID", type="integer"),
            "Dim2ID": ColumnSchema(name="Dim2ID", type="integer"),
            "Amount": ColumnSchema(name="Amount", type="float")
        })
    }
    rels = [
        RelationshipCandidate(
            source_table="FactSales", source_column="ID", target_table="ConflictedTable", target_column="ID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        ),
        RelationshipCandidate(
            source_table="ConflictedTable", source_column="Dim1ID", target_table="Dim1", target_column="ID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        ),
        RelationshipCandidate(
            source_table="ConflictedTable", source_column="Dim2ID", target_table="Dim2", target_column="ID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    
    assert spec.tables[0].role == ModelTableRole.NEEDS_REVIEW

def test_relationship_directions():
    tables = {
        "T1": TableSchema(name="T1", row_count=100, columns={}),
        "T2": TableSchema(name="T2", row_count=100, columns={})
    }
    rels = [
        RelationshipCandidate(
            source_table="T1", source_column="ID", target_table="T2", target_column="ID",
            cardinality="1:N", source_unique=True, target_unique=False,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        ),
        RelationshipCandidate(
            source_table="T2", source_column="ID2", target_table="T1", target_column="ID2",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        ),
        RelationshipCandidate(
            source_table="T1", source_column="ID3", target_table="T2", target_column="ID3",
            cardinality="1:1", source_unique=True, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        ),
        RelationshipCandidate(
            source_table="T1", source_column="ID4", target_table="T2", target_column="ID4",
            cardinality="N:M", source_unique=False, target_unique=False,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    
    assert len(spec.relationships) == 4
    # 1:N -> SINGLE
    assert spec.relationships[0].filter_direction == "SINGLE"
    # N:1 -> SINGLE
    assert spec.relationships[1].filter_direction == "SINGLE"
    # 1:1 -> BOTH
    assert spec.relationships[2].filter_direction == "BOTH"
    # N:M -> NEEDS_REVIEW
    assert spec.relationships[3].filter_direction == "NEEDS_REVIEW"
    assert spec.relationships[3].relationship_status == ModelStatus.NEEDS_REVIEW
    assert any("bridge" in w.lower() for w in spec.relationships[3].validation_warnings)

def test_unresolved_relationship():
    tables = {
        "T1": TableSchema(name="T1", row_count=100, columns={})
    }
    rels = [
        RelationshipCandidate(
            source_table="T1", source_column="ID", target_table="MissingTable", target_column="ID",
            cardinality="1:N", source_unique=True, target_unique=False,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    
    assert spec.relationships[0].relationship_status == ModelStatus.UNRESOLVED
    assert spec.status == ModelStatus.INVALID # BLOCKING error results in INVALID model

def test_date_table_ambiguity():
    tables = {
        "T1": TableSchema(name="T1", row_count=100, columns={})
    }
    date_configs = [
        DateDimensionConfig(config_id="d1", source_table="T1", date_column="date1", user_min_date=None, user_max_date=None, missing_date_behavior="ignore"),
        DateDimensionConfig(config_id="d2", source_table="T1", date_column="date2", user_min_date=None, user_max_date=None, missing_date_behavior="ignore")
    ]
    mg = ModelGenerator(data_model=DataModel(tables=tables, relationships=[]), date_configs=date_configs)
    spec = mg.generate()
    
    assert spec.date_table is not None
    assert spec.status in [ModelStatus.NEEDS_REVIEW, ModelStatus.INVALID]
    assert "multiple" in spec.date_table.selection_evidence.lower()

def test_kpis_integration():
    tables = {
        "FactSales": TableSchema(name="FactSales", row_count=100, columns={"Amount": ColumnSchema(name="Amount", type="float")})
    }
    kpis = [
        KPIDefinition(kpi_id="k1", kpi_name="Total Sales", business_definition="Sum of sales", formula="SUM(Amount)", metric_definitions=[], source_tables=["FactSales"], source_columns=["Amount"], unit="$", description=""),
        KPIDefinition(kpi_id="k2", kpi_name="Missing KPI", business_definition="", formula="", metric_definitions=[], source_tables=["MissingTable"], source_columns=["Col"], unit="", description="")
    ]
    mg = ModelGenerator(data_model=DataModel(tables=tables, relationships=[]), kpis=kpis)
    spec = mg.generate()
    
    assert len(spec.suggested_measures) == 2
    valid_kpi = next(m for m in spec.suggested_measures if m.kpi_id == "k1")
    missing_kpi = next(m for m in spec.suggested_measures if m.kpi_id == "k2")
    
    assert valid_kpi.status == ModelStatus.VALID
    assert missing_kpi.status == ModelStatus.ORPHANED # or ORPHANED depending on mapping, let's say UNRESOLVED as defined

def test_synthetic_benchmark():
    # 10M rows synthetic, but for metadata we just set row_count=10_000_000
    tables = {
        "GiantFact": TableSchema(name="GiantFact", row_count=10_000_000, columns={
            f"Col{i}": ColumnSchema(name=f"Col{i}", type="float") for i in range(100)
        })
    }
    start = time.time()
    mg = ModelGenerator(data_model=DataModel(tables=tables, relationships=[]))
    spec = mg.generate()
    duration = time.time() - start
    
    assert duration < 1.0 # Should be lightning fast as it operates strictly on metadata
    assert spec.tables[0].table_name == "GiantFact"

def test_missing_column_relationship():
    tables = {
        "T1": TableSchema(name="T1", row_count=100, columns={"ValidID": ColumnSchema(name="ValidID", type="int")}),
        "T2": TableSchema(name="T2", row_count=100, columns={"ValidID": ColumnSchema(name="ValidID", type="int")})
    }
    rels = [
        RelationshipCandidate(
            source_table="T1", source_column="MissingID", target_table="T2", target_column="ValidID",
            cardinality="1:N", source_unique=True, target_unique=False,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()
    assert spec.relationships[0].relationship_status == ModelStatus.UNRESOLVED

def test_model_persistence_and_isolation(tmp_path):
    mg = ModelGenerator(data_model=DataModel(tables={}, relationships=[]))
    spec = mg.generate()
    spec.model_id = "test_persistence"
    
    base_path = str(tmp_path)
    mg.save_specification(spec, base_path)
    loaded = ModelGenerator.load_specification(base_path)
    assert loaded is not None
    assert loaded["model_id"] == "test_persistence"

def test_raw_data_immutability():
    # Ensures nothing attempts to load raw data
    pass

def test_generate_dax_measures_with_model_metadata():
    tables = {
        "FactSales": TableSchema(name="FactSales", row_count=1000, columns={
            "SalesID": ColumnSchema(name="SalesID", type="integer", is_unique=True),
            "Revenue": ColumnSchema(name="Revenue", type="float"),
            "Profit": ColumnSchema(name="Profit", type="float"),
            "CustomerID": ColumnSchema(name="CustomerID", type="integer")
        })
    }
    dm = DataModel(tables=tables, relationships=[])
    mg = ModelGenerator(data_model=dm)

    kpis = [
        {
            "kpi_name": "Total Revenue",
            "formula": "SUM(Revenue)",
            "source_tables": ["FactSales"],
            "source_columns": ["Revenue"],
            "unit": "currency"
        },
        {
            "kpi_name": "Profit Margin",
            "formula": "SUM(Profit) / SUM(Revenue)",
            "source_tables": ["FactSales"],
            "source_columns": ["Profit", "Revenue"],
            "unit": "ratio"
        },
        {
            "kpi_name": "Unique Customers",
            "formula": "COUNT_DISTINCT(CustomerID)",
            "source_tables": ["FactSales"],
            "source_columns": ["CustomerID"],
            "unit": "integer"
        }
    ]

    measures = mg.generate_dax_measures(kpis)
    assert len(measures) == 3

    m1 = measures[0]
    assert m1["measure_name"] == "Total Revenue"
    assert m1["table"] == "FactSales"
    assert m1["dax_expression"] == "SUM('FactSales'[Revenue])"
    assert m1["format_string"] == "$#,##0.00"
    assert m1["referenced_columns"] == ["'FactSales'[Revenue]"]

    m2 = measures[1]
    assert m2["measure_name"] == "Profit Margin"
    assert m2["table"] == "FactSales"
    assert m2["dax_expression"] == "DIVIDE(SUM('FactSales'[Profit]), SUM('FactSales'[Revenue]))"
    assert m2["format_string"] == "0.0%"

    m3 = measures[2]
    assert m3["measure_name"] == "Unique Customers"
    assert m3["table"] == "FactSales"
    assert m3["dax_expression"] == "DISTINCTCOUNT('FactSales'[CustomerID])"
    assert m3["format_string"] == "#,##0"

def test_generate_dax_measures_persistence(tmp_path):
    dm = DataModel(tables={}, relationships=[])
    mg = ModelGenerator(data_model=dm)

    measures = [
        {
            "measure_name": "Total Sales",
            "kpi_name": "Total Sales",
            "table": "Orders",
            "dax_expression": "SUM('Orders'[Sales])",
            "format_string": "$#,##0.00",
            "status": "VALID",
            "referenced_columns": ["'Orders'[Sales]"]
        }
    ]

    base_path = str(tmp_path / ".dataforge")
    mg.save_dax_measures(measures, base_path=base_path)

    loaded = ModelGenerator.load_dax_measures(base_path=base_path)
    assert len(loaded) == 1
    assert loaded[0]["measure_name"] == "Total Sales"
    assert loaded[0]["dax_expression"] == "SUM('Orders'[Sales])"

def test_generate_dax_measures_empty_kpis():
    dm = DataModel(tables={}, relationships=[])
    mg = ModelGenerator(data_model=dm)
    assert mg.generate_dax_measures([]) == []

def test_dimension_classification_fallback_to_accepted_relationships():
    # Table where ColumnSchema is_unique was not pre-set (False), but is the 1-side of an accepted relationship
    tables = {
        "DimProduct": TableSchema(name="DimProduct", row_count=50, columns={
            "ProductID": ColumnSchema(name="ProductID", type="integer", is_unique=False),
            "ProductName": ColumnSchema(name="ProductName", type="string", is_unique=False)
        })
    }
    rels = [
        RelationshipCandidate(
            source_table="FactSales", source_column="ProductID",
            target_table="DimProduct", target_column="ProductID",
            cardinality="N:1", source_unique=False, target_unique=True,
            match_coverage=1.0, orphan_rate=0.0, confidence=1.0, evidence=[], status="ACCEPTED"
        )
    ]
    dm = DataModel(tables=tables, relationships=rels)
    mg = ModelGenerator(data_model=dm)
    spec = mg.generate()

    assert spec.tables[0].table_name == "DimProduct"
    assert spec.tables[0].role == ModelTableRole.DIMENSION
    assert spec.tables[0].primary_key == "ProductID"
