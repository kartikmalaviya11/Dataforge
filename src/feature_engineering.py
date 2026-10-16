import json
import uuid
import time
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any

from src.workspace import ProjectWorkspace
from src.sql_engine import DuckDBEngine

class FeatureGenerationError(Exception):
    pass

class DuplicateFeatureError(Exception):
    pass

@dataclass
class FeatureDefinition:
    feature_id: str
    feature_name: str
    feature_type: str
    source_table: str
    source_columns: List[str]
    expression: str
    created_at: float
    status: str = "ACTIVE"

class FeatureBuilder:
    """Safely builds SQL expressions for feature generation. No arbitrary user SQL."""
    
    @staticmethod
    def _quote(col_name: str) -> str:
        """Safely quote column name"""
        # Basic protection, strip existing quotes and wrap
        clean = col_name.replace('"', '').replace("'", "")
        # Also reject spaces if it's supposed to be a constant number, but this function is for columns
        return f'"{clean}"'
        
    @staticmethod
    def _is_safe_col_or_val(val: str) -> bool:
        if not isinstance(val, str):
            return True
        # Allow numbers, quoted strings, basic column names
        # Reject semicolons, sql comments, etc
        if re.search(r'[;]', val) or '--' in val or '/*' in val:
            return False
        # Reject DML/DDL keywords loosely
        upper = val.upper()
        for kw in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'COPY', 'ATTACH']:
            if kw in upper:
                return False
        return True

    @staticmethod
    def _is_numeric_literal(val: Any) -> bool:
        if isinstance(val, (int, float)):
            return True
        try:
            float(str(val).strip())
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def build_date_difference(feature_name: str, source_table: str, start_col: str, end_col: str, unit: str) -> FeatureDefinition:
        if unit.lower() not in ['day', 'month', 'year']:
            raise ValueError("Unsupported date unit.")
        
        expr = f"date_diff('{unit.lower()}', {FeatureBuilder._quote(start_col)}, {FeatureBuilder._quote(end_col)})"
        return FeatureDefinition(
            feature_id=str(uuid.uuid4()),
            feature_name=feature_name,
            feature_type="DATE_DIFFERENCE",
            source_table=source_table,
            source_columns=[start_col, end_col],
            expression=expr,
            created_at=time.time()
        )

    @staticmethod
    def build_date_part(feature_name: str, source_table: str, col: str, unit: str) -> FeatureDefinition:
        allowed_units = ['year', 'month', 'quarter', 'week']
        if unit.lower() not in allowed_units:
            raise ValueError(f"Unsupported date part: {unit}")
            
        expr = f"date_part('{unit.lower()}', {FeatureBuilder._quote(col)})"
        return FeatureDefinition(
            feature_id=str(uuid.uuid4()),
            feature_name=feature_name,
            feature_type="DATE_PART",
            source_table=source_table,
            source_columns=[col],
            expression=expr,
            created_at=time.time()
        )

    @staticmethod
    def build_boolean_flag(feature_name: str, source_table: str, col: str, operator: str, value: str) -> FeatureDefinition:
        if operator not in ['>', '<', '>=', '<=', '==', '=', '!=', '<>']:
            raise ValueError("Unsupported operator.")
            
        if not FeatureBuilder._is_safe_col_or_val(value):
            raise ValueError("Malicious or invalid value detected.")
            
        op = "=" if operator == "==" else operator
        expr = f"({FeatureBuilder._quote(col)} {op} {value})::BOOLEAN"
        return FeatureDefinition(
            feature_id=str(uuid.uuid4()),
            feature_name=feature_name,
            feature_type="BOOLEAN_FLAG",
            source_table=source_table,
            source_columns=[col],
            expression=expr,
            created_at=time.time()
        )

    @staticmethod
    def build_conditional_column(feature_name: str, source_table: str, conditions: List[Dict[str, str]], default_val: str) -> FeatureDefinition:
        if not FeatureBuilder._is_safe_col_or_val(default_val):
            raise ValueError("Invalid default value.")
            
        source_cols = []
        cases = []
        for cond in conditions:
            col = cond['col']
            op = "=" if cond['op'] == "==" else cond['op']
            val = cond['val']
            res = cond['result']
            
            if op not in ['>', '<', '>=', '<=', '=', '!=', '<>'] or not FeatureBuilder._is_safe_col_or_val(val) or not FeatureBuilder._is_safe_col_or_val(res):
                raise ValueError("Invalid condition configuration.")
                
            cases.append(f"WHEN {FeatureBuilder._quote(col)} {op} {val} THEN {res}")
            if col not in source_cols:
                source_cols.append(col)
                
        expr = "CASE " + " ".join(cases) + f" ELSE {default_val} END"
        
        return FeatureDefinition(
            feature_id=str(uuid.uuid4()),
            feature_name=feature_name,
            feature_type="CONDITIONAL_COLUMN",
            source_table=source_table,
            source_columns=source_cols,
            expression=expr,
            created_at=time.time()
        )

    @staticmethod
    def build_arithmetic(feature_name: str, source_table: str, col1: str, op: str, col2: str) -> FeatureDefinition:
        if op not in ['+', '-', '*', '/']:
            raise ValueError("Unsupported arithmetic operator.")
        if not FeatureBuilder._is_safe_col_or_val(col1) or not FeatureBuilder._is_safe_col_or_val(col2):
            raise ValueError("Malicious or invalid operands.")
            
        is_num1 = FeatureBuilder._is_numeric_literal(col1)
        is_num2 = FeatureBuilder._is_numeric_literal(col2)

        c1 = str(col1).strip() if is_num1 else FeatureBuilder._quote(col1)
        c2 = str(col2).strip() if is_num2 else FeatureBuilder._quote(col2)
        
        if op == '/':
            # Safe division
            expr = f"({c1} / NULLIF({c2}, 0))"
        else:
            expr = f"({c1} {op} {c2})"
            
        cols = []
        if not is_num1:
            cols.append(col1)
        if not is_num2:
            cols.append(col2)
            
        return FeatureDefinition(
            feature_id=str(uuid.uuid4()),
            feature_name=feature_name,
            feature_type="ARITHMETIC_FORMULA",
            source_table=source_table,
            source_columns=cols,
            expression=expr,
            created_at=time.time()
        )

    @staticmethod
    def build_bucket_category(feature_name: str, source_table: str, col: str, buckets: List[Dict[str, Any]], default_label: str) -> FeatureDefinition:
        if not FeatureBuilder._is_safe_col_or_val(default_label):
            raise ValueError("Invalid default label.")
            
        cases = []
        
        # Check overlaps
        parsed_intervals = []
        for b in buckets:
            bmin = b.get('min')
            bmax = b.get('max')
            lbl = b['label']
            if not FeatureBuilder._is_safe_col_or_val(lbl):
                raise ValueError("Invalid bucket label.")
                
            try:
                min_val = float(bmin) if bmin is not None and str(bmin).strip() != "" else float('-inf')
                max_val = float(bmax) if bmax is not None and str(bmax).strip() != "" else float('inf')
                if min_val >= max_val:
                    raise ValueError(f"Bucket min {min_val} must be less than max {max_val}")
                parsed_intervals.append((min_val, max_val))
            except ValueError as e:
                raise ValueError(f"Invalid numeric bounds for bucket: {e}")
                
            conds = []
            if min_val != float('-inf'):
                conds.append(f"{FeatureBuilder._quote(col)} >= {min_val}")
            if max_val != float('inf'):
                conds.append(f"{FeatureBuilder._quote(col)} < {max_val}")
                
            if conds:
                cases.append(f"WHEN {' AND '.join(conds)} THEN {lbl}")
                
        # Validate overlap
        for i in range(len(parsed_intervals)):
            for j in range(i + 1, len(parsed_intervals)):
                min_i, max_i = parsed_intervals[i]
                min_j, max_j = parsed_intervals[j]
                if not (max_i <= min_j or max_j <= min_i):
                    raise ValueError(f"Overlapping buckets detected: ({min_i}-{max_i}) overlaps with ({min_j}-{max_j})")
                
        expr = "CASE " + " ".join(cases) + f" ELSE {default_label} END"
        
        return FeatureDefinition(
            feature_id=str(uuid.uuid4()),
            feature_name=feature_name,
            feature_type="BUCKET_CATEGORY",
            source_table=source_table,
            source_columns=[col],
            expression=expr,
            created_at=time.time()
        )


class FeatureEngine:
    def __init__(self, sql_engine: DuckDBEngine, workspace: ProjectWorkspace):
        self.sql_engine = sql_engine
        self.workspace = workspace
        self.features_file = self.workspace.project_root / ".dataforge" / "features.json"
        self._ensure_file()
        self.features = self._load_features()
        self._apply_all_features()
        
    def _ensure_file(self):
        self.features_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.features_file.exists():
            with open(self.features_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
                
    def _load_features(self) -> List[FeatureDefinition]:
        try:
            with open(self.features_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [FeatureDefinition(**d) for d in data]
        except Exception:
            return []
            
    def _save_features(self):
        with open(self.features_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(fd) for fd in self.features], f, indent=2)

    def get_features(self, table_name: str) -> List[FeatureDefinition]:
        return [f for f in self.features if f.source_table == table_name]
        
    def _get_base_columns(self, table_name: str) -> List[str]:
        # We need to know base columns to prevent collision. 
        # By querying the raw view (T_raw) which is established in DuckDBEngine.
        try:
            res = self.sql_engine.conn.execute(f"DESCRIBE \"{table_name}_raw\"").fetchall()
            return [row[0] for row in res]
        except Exception:
            return []

    def _get_column_types(self, table_name: str) -> Dict[str, str]:
        try:
            res = self.sql_engine.conn.execute(f"DESCRIBE \"{table_name}_raw\"").fetchall()
            return {row[0]: row[1] for row in res}
        except Exception:
            return {}

    def _apply_all_features(self):
        # We group by table and recreate the views.
        tables = set([f.source_table for f in self.features])
        for t in self.workspace.registry.keys():
            tables.add(t)
            
        for t in tables:
            self._apply_features_to_table(t)
            
    def _apply_features_to_table(self, table_name: str):
        # Check if table exists in DuckDB
        try:
            views = self.sql_engine.conn.execute("SELECT table_name FROM information_schema.tables WHERE table_type='VIEW'").df()
            existing_views = views['table_name'].tolist()
        except:
            return
            
        if table_name not in existing_views and f"{table_name}_raw" not in existing_views:
            return # Table not mounted
            
        # If _raw doesn't exist, we rename the existing view to _raw
        if f"{table_name}_raw" not in existing_views and table_name in existing_views:
            self.sql_engine.conn.execute(f"ALTER VIEW \"{table_name}\" RENAME TO \"{table_name}_raw\"")
            
        features = self.get_features(table_name)
        
        select_parts = ["*"]
        for f in features:
            select_parts.append(f"{f.expression} AS \"{f.feature_name}\"")
            
        select_clause = ", ".join(select_parts)
        
        sql = f"CREATE OR REPLACE VIEW \"{table_name}\" AS SELECT {select_clause} FROM \"{table_name}_raw\""
        self.sql_engine.conn.execute(sql)

    def check_chaining(self, feature: FeatureDefinition):
        # Feature chaining is forbidden in Phase 4.
        existing_feature_names = [f.feature_name for f in self.get_features(feature.source_table)]
        for col in feature.source_columns:
            if col in existing_feature_names:
                raise ValueError(f"Feature chaining is not allowed in Phase 4. Column '{col}' is a derived feature.")

    def create_feature(self, feature: FeatureDefinition):
        # 1. Check for duplicates
        base_cols = self._get_base_columns(feature.source_table)
        if feature.feature_name in base_cols:
            raise DuplicateFeatureError(f"Feature name '{feature.feature_name}' conflicts with a base column.")
            
        existing = [f.feature_name for f in self.get_features(feature.source_table)]
        if feature.feature_name in existing:
            raise DuplicateFeatureError(f"Feature name '{feature.feature_name}' already exists.")
            
        # 2. Check scope locks (chaining)
        self.check_chaining(feature)
        
        # 3. Datatype validation
        col_types = self._get_column_types(feature.source_table)
        for col in feature.source_columns:
            # col might be a literal in some builders, we check if it is in col_types
            if col not in col_types:
                continue 
            ctype = col_types[col].upper()
            
            if feature.feature_type in ["DATE_DIFFERENCE", "DATE_PART"]:
                if "DATE" not in ctype and "TIME" not in ctype:
                    raise FeatureGenerationError(f"Column '{col}' must be a DATE/TIMESTAMP type, got {ctype}")
                    
            if feature.feature_type == "ARITHMETIC_FORMULA":
                if "INT" not in ctype and "DECIMAL" not in ctype and "FLOAT" not in ctype and "DOUBLE" not in ctype and "NUMERIC" not in ctype:
                    raise FeatureGenerationError(f"Column '{col}' must be a numeric type, got {ctype}")
        
        # 4. Add to list and persist
        self.features.append(feature)
        self._save_features()
        
        # 5. Apply
        self._apply_features_to_table(feature.source_table)
