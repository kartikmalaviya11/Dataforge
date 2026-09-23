import duckdb
import pandas as pd
from pathlib import Path
import sqlparse
import re
import uuid
import os
import tempfile

from src.workspace import ProjectWorkspace

class SecurityError(Exception):
    pass

class DuckDBEngine:
    def __init__(self, workspace: ProjectWorkspace, preview_limit: int = 500):
        self.workspace = workspace
        self.preview_limit = preview_limit
        self.conn = duckdb.connect(':memory:')
        self._register_tables()
        
    def _register_tables(self):
        for entry in self.workspace.registry.values():
            if entry.status == 'MISSING':
                continue
                
            table_name = entry.table_name
            file_path = Path(entry.file_path)
            
            if file_path.suffix.lower() == '.csv':
                # Direct DuckDB CSV view
                safe_path = str(file_path).replace("'", "''")
                self.conn.execute(f"""
                    CREATE VIEW "{table_name}" AS 
                    SELECT * FROM read_csv_auto('{safe_path}', header=True)
                """)
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                # Cache to parquet to avoid full Pandas load on every query
                cache_dir = self.workspace.project_root / ".dataforge" / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                cache_path = cache_dir / f"{table_name}.parquet"
                
                # Check invalidation (size and mtime)
                current_mtime = file_path.stat().st_mtime
                current_size = file_path.stat().st_size
                
                # Need to update if missing or if metadata diverges
                needs_update = True
                if cache_path.exists():
                    try:
                        # Stored metadata could be managed better, but for simplicity we rely on file's own mtime
                        # and we'll check if the cache is older than the original file
                        if cache_path.stat().st_mtime >= current_mtime:
                            needs_update = False
                    except:
                        pass
                
                if needs_update:
                    # Read via pandas once
                    df = pd.read_excel(file_path)
                    # Convert object columns to string to avoid DuckDB parquet issues
                    for col in df.columns:
                        if df[col].dtype == 'object':
                            df[col] = df[col].astype(str)
                    
                    df.to_parquet(cache_path)
                    
                safe_cache_path = str(cache_path).replace("'", "''")
                self.conn.execute(f"""
                    CREATE VIEW "{table_name}" AS 
                    SELECT * FROM read_parquet('{safe_cache_path}')
                """)

    def _validate_sql(self, sql: str):
        # 1. Parse using sqlparse
        statements = sqlparse.parse(sql)
        
        # Filter out empty statements (e.g. trailing semicolons)
        valid_statements = [s for s in statements if s.value.strip()]
        
        if len(valid_statements) > 1:
            raise SecurityError("Multiple statements are not allowed in user queries.")
            
        if not valid_statements:
            raise ValueError("Empty query.")
            
        stmt = valid_statements[0]
        
        # Get the first significant token to determine statement type
        stmt_type = stmt.get_type()
        
        allowed_types = ['SELECT', 'UNKNOWN']  # UNKNOWN can be WITH CTEs in some sqlparse versions
        
        # Specifically check for WITH (CTE)
        first_token = stmt.token_first(skip_ws=True, skip_cm=True)
        first_keyword = first_token.value.upper() if first_token else ""
        
        if stmt_type not in allowed_types and first_keyword not in ['SELECT', 'WITH', 'CREATE']:
            raise SecurityError(f"Statement type '{stmt_type}' or '{first_keyword}' is not allowed.")
            
        # If it's a CREATE statement, it MUST be CREATE TEMP VIEW or CREATE TEMP TABLE
        if first_keyword == 'CREATE':
            # Check the tokens following CREATE
            tokens = [t for t in stmt.tokens if not t.is_whitespace and not isinstance(t, sqlparse.sql.Comment)]
            if len(tokens) < 3:
                raise SecurityError("Invalid CREATE statement.")
            
            # The structure should be CREATE TEMP VIEW or CREATE TEMP TABLE
            # sqlparse groups things, so we stringify the first few tokens
            raw_upper = stmt.value.upper()
            # Normalize whitespace
            normalized = re.sub(r'\s+', ' ', raw_upper)
            if not (normalized.startswith("CREATE TEMP VIEW") or normalized.startswith("CREATE TEMP TABLE")):
                raise SecurityError("Only CREATE TEMP VIEW and CREATE TEMP TABLE are allowed.")
                
        # Blocked keywords check (fallback AST inspection)
        # Flatten all tokens to check for malicious keywords anywhere in the AST
        def check_tokens(token_list):
            for t in token_list:
                if t.is_group:
                    check_tokens(t.tokens)
                elif t.ttype in sqlparse.tokens.Keyword or t.ttype in sqlparse.tokens.Keyword.DML or t.ttype in sqlparse.tokens.Keyword.DDL:
                    val = t.value.upper()
                    if val in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'TRUNCATE', 'ATTACH', 'DETACH', 'COPY']:
                        raise SecurityError(f"Blocked keyword detected: {val}")
                        
        check_tokens(stmt.tokens)

    def execute_query(self, sql: str) -> pd.DataFrame:
        """Executes a query and returns a bounded preview."""
        self._validate_sql(sql)
        
        # If it's a CREATE TEMP VIEW/TABLE, we execute and return empty DF
        first_token = sqlparse.parse(sql)[0].token_first(skip_ws=True, skip_cm=True)
        if first_token and first_token.value.upper() == 'CREATE':
            self.conn.execute(sql)
            return pd.DataFrame()
            
        # For SELECT/WITH, apply preview limit using DuckDB's fetchdf capability
        # By wrapping the query
        sql_with_limit = f"SELECT * FROM ({sql}) AS _limited_preview LIMIT {self.preview_limit}"
        df = self.conn.execute(sql_with_limit).fetchdf()
        return df

    def export_query(self, sql: str) -> str:
        """Executes a query and exports the full result to a secure temporary CSV using DuckDB COPY."""
        self._validate_sql(sql)
        
        exports_dir = self.workspace.project_root / ".dataforge" / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate safe filename
        export_id = str(uuid.uuid4())
        export_file = exports_dir / f"export_{export_id}.csv"
        
        # Use DuckDB native COPY
        safe_path = str(export_file).replace("'", "''")
        copy_sql = f"COPY ({sql}) TO '{safe_path}' (HEADER, DELIMITER ',')"
        
        self.conn.execute(copy_sql)
        return str(export_file)

    def close(self):
        if self.conn:
            self.conn.close()
