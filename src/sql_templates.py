from dataclasses import dataclass
from typing import Dict, List

@dataclass
class QueryTemplate:
    name: str
    description: str
    template: str
    
    def render(self, **kwargs) -> str:
        sql = self.template
        for k, v in kwargs.items():
            # If it's a table name or column, we might want to quote it. 
            # For simplicity, we just do string replacement.
            # The caller should ensure it's safely quoted if needed.
            if k == "table_name":
                sql = sql.replace(f"{{{k}}}", f'"{v}"')
            else:
                sql = sql.replace(f"{{{k}}}", str(v))
        return sql

class SQLTemplateLibrary:
    def __init__(self):
        self.templates: Dict[str, QueryTemplate] = {}
        self._register_defaults()
        
    def _register_defaults(self):
        self.templates["Basic Aggregation"] = QueryTemplate(
            name="Basic Aggregation",
            description="Groups by a column and sums/counts another.",
            template='''SELECT {group_col}, COUNT(*) as count, SUM({agg_col}) as total
FROM {table_name}
GROUP BY {group_col}
ORDER BY total DESC;'''
        )
        
        self.templates["Row Number"] = QueryTemplate(
            name="Row Number",
            description="Assigns a row number partitioned by a column.",
            template='''SELECT *,
       ROW_NUMBER() OVER (PARTITION BY {partition_col} ORDER BY {order_col} DESC) as rn
FROM {table_name};'''
        )
        
        self.templates["Duplicate Check"] = QueryTemplate(
            name="Duplicate Check",
            description="Finds duplicate records based on a unique key.",
            template='''SELECT {key_col}, COUNT(*) as num_occurrences
FROM {table_name}
GROUP BY {key_col}
HAVING COUNT(*) > 1
ORDER BY num_occurrences DESC;'''
        )

    def get_all_templates(self) -> List[QueryTemplate]:
        return list(self.templates.values())
        
    def get_template(self, name: str) -> QueryTemplate:
        return self.templates.get(name)
