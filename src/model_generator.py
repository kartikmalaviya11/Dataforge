import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from src.data_model import DataModel, RelationshipCandidate
from src.kpi_engine import KPIDefinition
from src.date_analysis_engine import DateDimensionConfig

class ModelTableRole(Enum):
    FACT = "FACT"
    DIMENSION = "DIMENSION"
    BRIDGE = "BRIDGE"
    UNKNOWN = "UNKNOWN"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class ModelStatus(Enum):
    VALID = "VALID"
    UNRESOLVED = "UNRESOLVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INVALID = "INVALID"
    ORPHANED = "ORPHANED"

@dataclass
class ModelTable:
    table_name: str
    role: ModelTableRole
    primary_key: Optional[str]
    columns: List[str]
    source_reference: str
    reasoning: str

@dataclass
class ModelRelationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    cardinality: str
    filter_direction: str
    relationship_status: ModelStatus
    source_relationship_id: str
    validation_warnings: List[str]

@dataclass
class DateTableSpecification:
    date_table_name: str
    date_column: str
    min_date: Optional[str]
    max_date: Optional[str]
    grain: str
    has_date: bool = True
    has_year: bool = True
    has_month_number: bool = True
    has_month_name: bool = True
    has_quarter: bool = True
    has_iso_week: bool = True
    has_iso_year: bool = True
    has_year_month: bool = True
    is_contiguous: bool = True
    source_date_column_reference: str = ""
    selection_evidence: str = ""

@dataclass
class SuggestedMeasure:
    measure_id: str
    kpi_id: str
    measure_name: str
    business_definition: str
    source_table: str
    source_columns: List[str]
    aggregation: str
    unit: str
    formula: str
    status: ModelStatus
    warnings: List[str]

@dataclass
class ModelDocumentation:
    description: str
    assumptions: List[str]
    metadata: Dict[str, str]

@dataclass
class ModelSpecification:
    model_id: str
    project_context: str
    generated_at: float
    tables: List[ModelTable]
    relationships: List[ModelRelationship]
    date_table: Optional[DateTableSpecification]
    suggested_measures: List[SuggestedMeasure]
    status: ModelStatus
    warnings: List[str]
    assumptions: List[str]
    documentation: ModelDocumentation


class ModelGenerator:
    def __init__(self, data_model: DataModel, date_configs: List[DateDimensionConfig] = None, kpis: List[KPIDefinition] = None):
        self.data_model = data_model
        self.date_configs = date_configs or []
        self.kpis = kpis or []

    def generate(self) -> ModelSpecification:
        status = ModelStatus.VALID
        warnings = []
        
        tables = []
        for t_name, table in self.data_model.tables.items():
            tables.append(self._classify_table(t_name, table))
            
        rels = []
        for r_idx, r in enumerate(self.data_model.relationships):
            if r.status != "ACCEPTED":
                continue
            rel = self._map_relationship(r, r_idx)
            rels.append(rel)
            if rel.relationship_status in (ModelStatus.INVALID, ModelStatus.UNRESOLVED):
                status = ModelStatus.INVALID
            elif rel.relationship_status == ModelStatus.NEEDS_REVIEW and status != ModelStatus.INVALID:
                status = ModelStatus.NEEDS_REVIEW

        date_table = self._build_date_table()
        if date_table and "multiple" in date_table.selection_evidence.lower():
            if status != ModelStatus.INVALID:
                status = ModelStatus.NEEDS_REVIEW

        measures = self._build_measures()
        
        spec = ModelSpecification(
            model_id="gen_model_1",
            project_context="DATAFORGE",
            generated_at=time.time(),
            tables=tables,
            relationships=rels,
            date_table=date_table,
            suggested_measures=measures,
            status=status,
            warnings=warnings,
            assumptions=[],
            documentation=ModelDocumentation("Generated Model", [], {})
        )
        return spec
        
    def save_specification(self, spec: ModelSpecification, base_path: str = ".dataforge"):
        import os, json, dataclasses
        os.makedirs(base_path, exist_ok=True)
        path = os.path.join(base_path, "model_specification.json")
        with open(path, "w") as f:
            json.dump(dataclasses.asdict(spec), f, indent=2, default=lambda x: x.value if isinstance(x, Enum) else x)

    @staticmethod
    def load_specification(base_path: str = ".dataforge") -> Optional[Dict]:
        import os, json
        path = os.path.join(base_path, "model_specification.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
            
    def _classify_table(self, t_name: str, table) -> ModelTable:
        # Check uniqueness > 0.99
        is_dim_signal = False
        pk = None
        for c_name, c in table.columns.items():
            if c.is_unique: # Simplification for >= 0.99
                is_dim_signal = True
                pk = c_name
                break
                
        if not pk and hasattr(self, "data_model") and self.data_model and hasattr(self.data_model, "relationships"):
            for r in self.data_model.relationships:
                status = getattr(r.status, "value", str(r.status)).upper()
                if status != "ACCEPTED":
                    continue
                if r.target_table == t_name and r.cardinality in ("N:1", "1:1"):
                    pk = r.target_column
                    is_dim_signal = True
                    break
                elif r.source_table == t_name and r.cardinality in ("1:N", "1:1"):
                    pk = r.source_column
                    is_dim_signal = True
                    break

        # Check numeric measures
        has_numeric_metrics = False
        numeric_count = sum(1 for c_name, c in table.columns.items() if c.type in ('int', 'float', 'integer', 'double', 'numeric', 'decimal') and c_name != pk and not c_name.endswith('ID'))
        if numeric_count >= 1:
            has_numeric_metrics = True
            
        # Check relationships
        many_side_count = 0
        dim_targets = 0
        for r in self.data_model.relationships:
            if r.status != "ACCEPTED":
                continue
            if r.source_table == t_name and r.cardinality in ("N:1", "N:M"):
                many_side_count += 1
                dim_targets += 1
                
        # Determine Role
        if is_dim_signal and many_side_count > 1 and has_numeric_metrics:
            role = ModelTableRole.NEEDS_REVIEW
            reason = "Conflicting signals: uniqueness >= 0.99 but also MANY side of multiple relationships and has numeric metrics."
        elif many_side_count >= 2 and numeric_count == 0:
            role = ModelTableRole.BRIDGE
            reason = f"Bridge table candidate: 0 non-key numeric metrics, source of {many_side_count} relationships."
        elif has_numeric_metrics or many_side_count >= 1:
            role = ModelTableRole.FACT
            reason = f"Fact table candidate: {numeric_count} numeric metrics, {many_side_count} MANY-side relationships."
        elif is_dim_signal:
            role = ModelTableRole.DIMENSION
            reason = "Dimension table candidate: Contains column with uniqueness >= 0.99 serving as primary key."
        else:
            role = ModelTableRole.UNKNOWN
            reason = "No definitive signals found."
            
        return ModelTable(
            table_name=t_name,
            role=role,
            primary_key=pk,
            columns=list(table.columns.keys()),
            source_reference=t_name,
            reasoning=reason
        )

    def _map_relationship(self, r: RelationshipCandidate, idx: int) -> ModelRelationship:
        status = ModelStatus.VALID
        warnings = []
        filter_dir = "SINGLE"
        
        if r.source_table not in self.data_model.tables or r.target_table not in self.data_model.tables:
            status = ModelStatus.UNRESOLVED
            warnings.append(f"Missing source or target table for relationship {r.source_table}->{r.target_table}")
        else:
            if r.source_column not in self.data_model.tables[r.source_table].columns:
                status = ModelStatus.UNRESOLVED
                warnings.append(f"Missing source column {r.source_column} in table {r.source_table}")
            if r.target_column not in self.data_model.tables[r.target_table].columns:
                status = ModelStatus.UNRESOLVED
                warnings.append(f"Missing target column {r.target_column} in table {r.target_table}")
            
        if r.cardinality == "1:N":
            filter_dir = "SINGLE"
        elif r.cardinality == "N:1":
            filter_dir = "SINGLE"
        elif r.cardinality == "1:1":
            filter_dir = "BOTH"
        elif r.cardinality == "N:M":
            filter_dir = "NEEDS_REVIEW"
            status = ModelStatus.NEEDS_REVIEW
            warnings.append("Bridge table is missing for MANY_TO_MANY relationship.")
            
        return ModelRelationship(
            source_table=r.source_table,
            source_column=r.source_column,
            target_table=r.target_table,
            target_column=r.target_column,
            cardinality=r.cardinality,
            filter_direction=filter_dir,
            relationship_status=status,
            source_relationship_id=f"rel_{idx}",
            validation_warnings=warnings
        )
        
    def _build_date_table(self) -> Optional[DateTableSpecification]:
        if not self.date_configs:
            return None
            
        if len(self.date_configs) == 1:
            c = self.date_configs[0]
            return DateTableSpecification(
                date_table_name=f"{c.source_table}_Date",
                date_column=c.date_column,
                min_date=c.user_min_date,
                max_date=c.user_max_date,
                grain="day",
                source_date_column_reference=f"{c.source_table}.{c.date_column}",
                selection_evidence="Exactly 1 valid date column exists project-wide."
            )
        else:
            return DateTableSpecification(
                date_table_name="Unknown_Date",
                date_column="",
                min_date=None,
                max_date=None,
                grain="day",
                selection_evidence="Multiple valid date columns exist. Needs Review."
            )
            
    def _build_measures(self) -> List[SuggestedMeasure]:
        measures = []
        for kpi in self.kpis:
            status = ModelStatus.VALID
            warnings = []
            
            # Check if tables/columns exist
            for t in kpi.source_tables:
                if t not in self.data_model.tables:
                    status = ModelStatus.ORPHANED
                    warnings.append(f"Source table {t} is missing.")
                    break
                    
            if status == ModelStatus.VALID:
                for c in kpi.source_columns:
                    # check first table
                    if kpi.source_tables and kpi.source_tables[0] in self.data_model.tables:
                        t_cols = self.data_model.tables[kpi.source_tables[0]].columns
                        if c not in t_cols:
                            status = ModelStatus.ORPHANED
                            warnings.append(f"Source column {c} is missing in {kpi.source_tables[0]}.")
                            
            measures.append(SuggestedMeasure(
                measure_id=f"measure_{kpi.kpi_id}",
                kpi_id=kpi.kpi_id,
                measure_name=kpi.kpi_name,
                business_definition=kpi.business_definition,
                source_table=kpi.source_tables[0] if kpi.source_tables else "",
                source_columns=kpi.source_columns,
                aggregation="SUM" if "SUM" in kpi.formula else "UNKNOWN",
                unit=kpi.unit,
                formula=kpi.formula,
                status=status,
                warnings=warnings
            ))
        return measures

    def generate_dax_measures(self, kpis: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Generates production Power BI DAX measures from real KPI definitions
        and project DataModel metadata.
        """
        import re
        target_kpis = kpis if kpis is not None else self.kpis
        measures = []
        if not target_kpis:
            return measures

        for k in target_kpis:
            if isinstance(k, dict):
                kpi_name = k.get("kpi_name") or k.get("name") or "Measure"
                formula = k.get("formula") or k.get("calculation_logic") or ""
                src_tables = k.get("source_tables") or []
                src_cols = k.get("source_columns") or []
                unit = k.get("unit") or ""
            else:
                kpi_name = getattr(k, "kpi_name", getattr(k, "name", "Measure"))
                formula = getattr(k, "formula", getattr(k, "calculation_logic", ""))
                src_tables = getattr(k, "source_tables", [])
                src_cols = getattr(k, "source_columns", [])
                unit = getattr(k, "unit", "")

            # Resolve table from data_model
            table_name = None
            if src_tables and src_tables[0] in self.data_model.tables:
                table_name = src_tables[0]
            elif src_cols and self.data_model.tables:
                for t_name, t_schema in self.data_model.tables.items():
                    if any(c in t_schema.columns for c in src_cols):
                        table_name = t_name
                        break

            if not table_name:
                if self.data_model.tables:
                    table_name = list(self.data_model.tables.keys())[0]
                elif src_tables:
                    table_name = src_tables[0]
                else:
                    table_name = "Dataset"

            # Build DAX expression
            def format_part(expr: str) -> str:
                expr = expr.strip()
                m = re.match(r"^([A-Za-z_]+)\((?:\[?([^\]\)]+)\]?)\)$", expr)
                if m:
                    func = m.group(1).upper()
                    if func == "COUNT_DISTINCT":
                        func = "DISTINCTCOUNT"
                    col = m.group(2).strip()
                    return f"{func}('{table_name}'[{col}])"
                elif src_cols:
                    return f"SUM('{table_name}'[{src_cols[0]}])"
                return expr

            if " / " in formula or ("/" in formula and not formula.startswith("/")):
                parts = formula.split("/") if " / " not in formula else formula.split(" / ")
                if len(parts) == 2:
                    num = format_part(parts[0])
                    den = format_part(parts[1])
                    dax_expr = f"DIVIDE({num}, {den})"
                else:
                    dax_expr = format_part(formula)
            elif formula:
                dax_expr = format_part(formula)
            elif src_cols:
                dax_expr = f"SUM('{table_name}'[{src_cols[0]}])"
            else:
                dax_expr = f"COUNTROWS('{table_name}')"

            # Format string
            k_lower = kpi_name.lower()
            u_lower = unit.lower() if unit else ""
            if u_lower in ("percent", "%", "ratio") or any(w in k_lower for w in ("margin", "rate", "ratio", "percentage", "pct")) or "DIVIDE" in dax_expr:
                format_str = "0.0%"
            elif u_lower in ("currency", "usd", "$") or any(w in k_lower for w in ("sales", "revenue", "amount", "price", "cost", "profit")):
                format_str = "$#,##0.00"
            elif any(w in k_lower for w in ("count", "orders", "customers", "quantity", "qty")):
                format_str = "#,##0"
            else:
                format_str = "#,##0.00"

            ref_cols = [f"'{table_name}'[{c}]" for c in src_cols] if src_cols else []
            measures.append({
                "measure_name": kpi_name,
                "kpi_name": kpi_name,
                "table": table_name,
                "dax_expression": dax_expr,
                "format_string": format_str,
                "status": "VALID",
                "referenced_columns": ref_cols
            })

        return measures

    @staticmethod
    def save_dax_measures(measures: List[Dict[str, Any]], base_path: str = ".dataforge"):
        import os, json
        os.makedirs(base_path, exist_ok=True)
        path = os.path.join(base_path, "dax_measures.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(measures, f, indent=2)

    @staticmethod
    def load_dax_measures(base_path: str = ".dataforge") -> List[Dict[str, Any]]:
        import os, json
        path = os.path.join(base_path, "dax_measures.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
