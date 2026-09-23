from typing import Dict, List
from src.data_model import DataModel, RelationshipStatus

class ERGenerator:
    def generate_dot(self, model: DataModel) -> str:
        """
        Generates a deterministic DOT string (Graphviz) from the DataModel.
        Used for st.graphviz_chart()
        """
        lines = []
        lines.append('digraph ER {')
        lines.append('    rankdir=LR;')
        lines.append('    node [shape=none, fontname="Helvetica"];')
        lines.append('    edge [fontname="Helvetica", fontsize=10];')
        lines.append('')
        
        # Draw tables
        sorted_tables = sorted(model.tables.keys())
        for tname in sorted_tables:
            schema = model.tables[tname]
            lines.append(f'    {tname} [label=<')
            lines.append('      <table border="0" cellborder="1" cellspacing="0" cellpadding="4">')
            lines.append(f'        <tr><td bgcolor="lightblue"><b>{tname}</b></td></tr>')
            
            # Sort columns
            sorted_cols = sorted(schema.columns.values(), key=lambda c: c.name)
            for col in sorted_cols:
                pk_marker = " (PK)" if col.is_unique else ""
                lines.append(f'        <tr><td align="left" port="{col.name}">{col.name}{pk_marker}</td></tr>')
            
            lines.append('      </table>')
            lines.append('    >];')
        
        lines.append('')
        
        # Draw relationships (only ACCEPTED ones)
        # Sort relationships for determinism
        sorted_rels = sorted(model.relationships, key=lambda r: (r.source_table, r.source_column, r.target_table, r.target_column))
        
        for rel in sorted_rels:
            if rel.status == RelationshipStatus.ACCEPTED.value:
                # e.g., orders:customer_id -> customers:customer_id
                # Cardinaility label
                card = rel.cardinality
                lines.append(f'    {rel.source_table}:{rel.source_column} -> {rel.target_table}:{rel.target_column} [label="{card}"];')
                
        lines.append('}')
        
        return '\n'.join(lines)
