import ast
from pathlib import Path
from unittest.mock import patch, MagicMock
from markdown_it import MarkdownIt

from ui.theme import clean_html, card, metric_card, page_header
from ui.components import empty_state, run_action

md_parser = MarkdownIt('commonmark', {'html': True})


class MockSession(dict):
    def __getattr__(self, name):
        return self.get(name)
    def __setattr__(self, name, value):
        self[name] = value


def test_clean_html_strips_indentation_and_blank_lines():
    """Verify clean_html removes leading spaces and blank lines, preventing CommonMark code block parsing."""
    indented_html = """
        <div style="background: red;">

            <h3 style="color: blue;">Title</h3>
            <p>Description</p>
        </div>
    """
    # Raw indented HTML is parsed as code block by CommonMark
    raw_rendered = md_parser.render(indented_html)
    assert "<pre><code>" in raw_rendered

    # After clean_html, it is parsed purely as HTML elements
    cleaned = clean_html(indented_html)
    cleaned_rendered = md_parser.render(cleaned)
    assert "<pre><code>" not in cleaned_rendered
    assert "<h3 style=\"color: blue;\">Title</h3>" in cleaned_rendered
    assert "<p>Description</p>" in cleaned_rendered


def test_empty_state_rendering_no_code_block():
    """Verify empty_state renders valid HTML headings and paragraphs without raw markup leaks."""
    rendered_markdowns = []

    with patch("streamlit.markdown") as mock_markdown, \
         patch("streamlit.columns", return_value=[MagicMock(), MagicMock(), MagicMock()]):

        empty_state(
            title="No Findings Available",
            description="Record insights in the Analysis page first.",
            action_label="Go to Findings",
            target_page="Findings"
        )
        for call_args in mock_markdown.call_args_list:
            rendered_markdowns.append(call_args[0][0])

    assert len(rendered_markdowns) >= 1
    full_html = rendered_markdowns[0]

    # Verify CommonMark parses it cleanly as HTML
    rendered = md_parser.render(full_html)
    assert "<pre><code>" not in rendered, "empty_state must not leak as <pre><code>"
    assert "<h3" in rendered
    assert "No Findings Available" in rendered
    assert "<p" in rendered
    assert "Record insights in the Analysis page first." in rendered


def test_run_action_error_card_no_code_block():
    """Verify run_action error card renders HTML without code block leaks."""
    rendered_markdowns = []

    def failing_step():
        raise ValueError("Simulated pipeline failure")

    with patch("streamlit.markdown") as mock_markdown, \
         patch("streamlit.status") as mock_status, \
         patch("streamlit.expander"), \
         patch("streamlit.code"):

        mock_status.return_value.__enter__.return_value = MagicMock()
        success, err = run_action("Test Operation", [("Step 1", failing_step)])
        assert success is False

        for call_args in mock_markdown.call_args_list:
            rendered_markdowns.append(call_args[0][0])

    assert len(rendered_markdowns) >= 1
    error_html = rendered_markdowns[0]
    rendered = md_parser.render(error_html)
    assert "<pre><code>" not in rendered
    assert "Operation Failed" in rendered


def test_theme_card_and_headers():
    """Verify card and page_header render clean HTML."""
    rendered_markdowns = []

    with patch("streamlit.markdown") as mock_markdown:
        card("<p>Card Content</p>", status="info", elevated=True)
        page_header("Data Quality Scan", subtitle="Automated inspection")
        metric_card("Total Tables", "5", "info")

        for call_args in mock_markdown.call_args_list:
            rendered_markdowns.append(call_args[0][0])

    for html_snippet in rendered_markdowns:
        rendered = md_parser.render(html_snippet)
        assert "<pre><code>" not in rendered, f"Snippet produced code block: {html_snippet[:80]}"


def test_legitimate_code_blocks_preserved():
    """Verify intentional markdown code blocks still render as code."""
    code_md = "```python\ndef hello():\n    return 'world'\n```"
    rendered = md_parser.render(code_md)
    assert "<pre><code" in rendered
    assert "def hello():" in rendered


def test_clean_html_preserves_pre_formatted_code():
    """Verify clean_html preserves indentation inside <pre> blocks while stripping outer indentation."""
    code_html = """
        <div class="code-container">
            <pre><code>
    def calculate():
        x = 10
        return x * 2
            </code></pre>
        </div>
    """
    cleaned = clean_html(code_html)
    assert "    def calculate():" in cleaned
    assert "        x = 10" in cleaned
    assert "        return x * 2" in cleaned
    # Outer div indentation is removed
    assert cleaned.startswith('<div class="code-container">')


def test_svg_icons_preserved_and_valid():
    """Verify SVG tags, viewBox, and paths are preserved intact by clean_html and not treated as code blocks."""
    svg_markup = """
        <div class="icon-wrap">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                <polyline points="2 17 12 22 22 17"></polyline>
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            </svg>
        </div>
    """
    cleaned = clean_html(svg_markup)
    rendered = md_parser.render(cleaned)

    assert "<pre><code>" not in rendered
    assert "<svg" in rendered
    assert 'viewBox="0 0 24 24"' in rendered
    assert '<polygon points="12 2 2 7 12 12 22 7 12 2">' in rendered or 'points="12 2 2 7 12 12 22 7 12 2"' in rendered
    assert '<polyline points="2 17 12 22 22 17">' in rendered or 'points="2 17 12 22 22 17"' in rendered
    assert "M10 13a5 5" in rendered


def test_sidebar_widgets_and_nav_buttons():
    """Verify sidebar logo, nav buttons, and system status widgets render clean HTML."""
    from ui.layout import logo_html, nav_button

    # 1. Logo HTML
    rendered_logo = md_parser.render(clean_html(logo_html()))
    assert "<pre><code>" not in rendered_logo
    assert "DATAFORGE" in rendered_logo
    assert "<svg" in rendered_logo

    # 2. Active and Disabled Nav Buttons
    mock_state = MockSession({"current_page": "Data Quality"})

    with patch("streamlit.session_state", mock_state), \
         patch("streamlit.sidebar.markdown") as mock_sidebar_md:

        # Active button
        nav_button("Data Quality")
        active_call = mock_sidebar_md.call_args[0][0]
        rendered_active = md_parser.render(active_call)
        assert "<pre><code>" not in rendered_active
        assert "Data Quality" in rendered_active

        # Disabled button
        nav_button("Overview", disabled=True)
        disabled_call = mock_sidebar_md.call_args[0][0]
        rendered_disabled = md_parser.render(disabled_call)
        assert "<pre><code>" not in rendered_disabled
        assert "Overview" in rendered_disabled
        assert "<svg" in rendered_disabled


def test_empty_and_populated_states_rendering():
    """Verify empty and populated state layouts render pure HTML without code block leaks."""
    from ui.layout import render_global_header
    from src.workspace import ProjectWorkspace, TableRegistryEntry
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ws = ProjectWorkspace(tmp_path)

        # 1. Empty workspace header (0 tables)
        mock_state = MockSession({})
        rendered_headers = []
        with patch("streamlit.session_state", mock_state), \
             patch("streamlit.markdown") as mock_markdown:
            render_global_header(ws)
            for call in mock_markdown.call_args_list:
                rendered_headers.append(call[0][0])

        assert len(rendered_headers) >= 1
        rendered = md_parser.render(rendered_headers[0])
        assert "<pre><code>" not in rendered
        assert "Not Initialized" in rendered
        assert "Tables:" in rendered

        # 2. Populated workspace header (2 tables)
        ws.registry["customers"] = TableRegistryEntry(
            table_name="customers",
            file_name="customers.csv",
            file_path=str(tmp_path / "customers.csv"),
            file_type="csv",
            row_count=1500,
            column_count=5,
            status="ANALYZED",
            last_modified=0.0
        )
        ws.registry["orders"] = TableRegistryEntry(
            table_name="orders",
            file_name="orders.csv",
            file_path=str(tmp_path / "orders.csv"),
            file_type="csv",
            row_count=45000,
            column_count=8,
            status="ANALYZED",
            last_modified=0.0
        )
        rendered_headers.clear()
        with patch("streamlit.session_state", mock_state), \
             patch("streamlit.markdown") as mock_markdown:
            render_global_header(ws)
            for call in mock_markdown.call_args_list:
                rendered_headers.append(call[0][0])

        assert len(rendered_headers) >= 1
        rendered_pop = md_parser.render(rendered_headers[0])
        assert "<pre><code>" not in rendered_pop
        assert "Customers &amp; Related" in rendered_pop or "Customers & Related" in rendered_pop
        assert "46,500" in rendered_pop
        assert "Ready" in rendered_pop


def test_entire_ui_directory_has_zero_html_code_block_leaks():
    """Audit every .py file in ui/ to verify no HTML-containing st.markdown call produces <pre><code>."""
    ui_dir = Path("ui")
    py_files = sorted(list(ui_dir.glob("**/*.py")))

    leaking_calls = []

    for py_path in py_files:
        content = py_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                is_md = False
                if isinstance(node.func, ast.Attribute) and node.func.attr == "markdown":
                    is_md = True
                elif isinstance(node.func, ast.Name) and node.func.id == "markdown":
                    is_md = True

                if is_md and node.args:
                    arg0 = node.args[0]
                    raw_text = None
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        raw_text = arg0.value
                    elif isinstance(arg0, ast.JoinedStr):
                        parts = []
                        for v in arg0.values:
                            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                                parts.append(v.value)
                            else:
                                parts.append("SAMPLE")
                        raw_text = "".join(parts)

                    # If string is literal HTML passed to markdown without clean_html
                    if raw_text and ("<" in raw_text and ">" in raw_text):
                        rendered = md_parser.render(raw_text)
                        if "<pre><code>" in rendered:
                            leaking_calls.append(f"{py_path.name}:{node.lineno} -> {raw_text.strip()[:60]}")

    assert len(leaking_calls) == 0, f"Found leaking markdown calls in ui/: {leaking_calls}"
