import pytest
from src.sql_templates import SQLTemplateLibrary

def test_sql_templates():
    library = SQLTemplateLibrary()
    templates = library.get_all_templates()
    assert len(templates) > 0
    
    # Render a template
    agg_template = library.get_template("Basic Aggregation")
    assert agg_template is not None
    
    sql = agg_template.render(table_name="my_table", group_col="category", agg_col="sales")
    assert '"my_table"' in sql
    assert "category" in sql
    assert "sales" in sql
