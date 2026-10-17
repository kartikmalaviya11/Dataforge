import streamlit as st

def clean_html(html_str: str) -> str:
    """Strips leading and trailing whitespace from each line and removes empty lines
    to prevent CommonMark from interpreting indented HTML as code blocks.
    Preserves indentation inside <pre> blocks if present."""
    if not html_str:
        return ""
    if "<pre" not in html_str:
        lines = [line.strip() for line in html_str.splitlines() if line.strip()]
        return "\n".join(lines)

    cleaned_lines = []
    in_pre = False
    for line in html_str.splitlines():
        if "<pre" in line:
            in_pre = True
            cleaned_lines.append(line.strip())
            if "</pre>" in line:
                in_pre = False
            continue
        if "</pre>" in line:
            in_pre = False
            cleaned_lines.append(line.rstrip())
            continue

        if in_pre:
            cleaned_lines.append(line)
        else:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)

def apply_theme():
    st.set_page_config(
        page_title="DATAFORGE — Professional Analytics Workspace",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown(clean_html("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        /* DATAFORGE Premium Dark Navy Design System */
        :root {
            --page-bg: #071426;
            --sidebar-bg: #061020;
            --sidebar-hover: #0F1D33;
            --sidebar-border: #0E1E38;
            --surface: #0C1B31;
            --surface-secondary: #10233D;
            --surface-elevated: #132744;
            --surface-hover: #152A4A;
            --border: #162C4C;
            --border-subtle: rgba(255, 255, 255, 0.07);
            --border-accent: rgba(56, 103, 255, 0.35);
            --primary: #3867FF;
            --primary-hover: #2F5AE5;
            --primary-gradient: linear-gradient(135deg, #3867FF 0%, #7857FF 100%);
            --accent-cyan: #27C9FF;
            --accent-violet: #7857FF;
            --text-primary: #F4F7FF;
            --text-secondary: #9AAAC2;
            --text-muted: #5D718D;
            --success: #10B981;
            --success-bg: rgba(16, 185, 129, 0.12);
            --warning: #F59E0B;
            --warning-bg: rgba(245, 158, 11, 0.12);
            --danger: #F43F5E;
            --danger-bg: rgba(244, 63, 94, 0.12);
            --info: #3867FF;
            --info-bg: rgba(56, 103, 255, 0.12);
        }

        /* App Base */
        .stApp {
            background-color: var(--page-bg) !important;
            color: var(--text-primary) !important;
            font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }

        /* Top padding and width */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
            max-width: 1400px !important;
        }

        /* Streamlit Header & Top Navigation Bar */
        header[data-testid="stHeader"], [data-testid="stHeader"] {
            background-color: var(--page-bg) !important;
            background: var(--page-bg) !important;
            color: var(--text-primary) !important;
            border-bottom: 1px solid var(--border-subtle) !important;
        }
        header[data-testid="stHeader"] * {
            color: var(--text-primary) !important;
        }
        [data-testid="stToolbar"] {
            color: var(--text-primary) !important;
            right: 1.5rem !important;
        }
        [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Typography */
        h1 {
            font-size: 1.75rem !important;
            font-weight: 750 !important;
            color: var(--text-primary) !important;
            letter-spacing: -0.025em !important;
            margin-bottom: 0.75rem !important;
        }
        h2 {
            font-size: 1.35rem !important;
            font-weight: 700 !important;
            color: var(--text-primary) !important;
            letter-spacing: -0.02em !important;
            margin-top: 1rem !important;
            margin-bottom: 0.75rem !important;
        }
        h3 {
            font-size: 1.05rem !important;
            font-weight: 650 !important;
            color: var(--text-primary) !important;
            letter-spacing: -0.01em !important;
            margin-bottom: 0.5rem !important;
        }
        h4 {
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            color: var(--text-secondary) !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-bottom: 0.5rem !important;
        }
        p, .stMarkdown p {
            font-size: 0.875rem !important;
            font-weight: 400 !important;
            line-height: 1.6 !important;
            color: var(--text-secondary) !important;
        }
        code {
            font-family: 'JetBrains Mono', monospace !important;
            background-color: rgba(255, 255, 255, 0.06) !important;
            color: var(--accent-cyan) !important;
            padding: 0.15rem 0.4rem !important;
            border-radius: 4px !important;
            font-size: 0.825rem !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--sidebar-bg) !important;
            border-right: 1px solid var(--sidebar-border) !important;
        }
        [data-testid="stSidebar"] * {
            color: var(--text-primary);
        }
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        /* Sidebar Buttons */
        [data-testid="stSidebar"] .stButton > button {
            background-color: transparent !important;
            color: var(--text-secondary) !important;
            border: 1px solid transparent !important;
            box-shadow: none !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.5rem 0.875rem !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            border-radius: 8px !important;
            margin: 0 0.5rem 0.2rem 0.5rem !important;
            width: calc(100% - 1rem) !important;
            transition: all 0.15s ease !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: var(--sidebar-hover) !important;
            color: #FFFFFF !important;
            border-color: rgba(255, 255, 255, 0.05) !important;
            transform: translateX(2px) !important;
        }
        [data-testid="stSidebar"] .stButton > button:active {
            transform: translateX(0) !important;
        }

        /* Sidebar Section Headers */
        .sidebar-section {
            color: var(--text-muted) !important;
            font-size: 0.7rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            font-weight: 700 !important;
            margin-top: 1.25rem !important;
            margin-bottom: 0.35rem !important;
            padding-left: 1rem !important;
        }

        /* Custom Cards */
        .df-card {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            margin-bottom: 1rem;
            transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
        }
        .df-card:hover {
            border-color: var(--border-accent);
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35), 0 0 15px rgba(56, 103, 255, 0.1);
        }

        /* Elevated Cards */
        .df-card-elevated {
            background-color: var(--surface-secondary);
            border: 1px solid #1A3459;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
            margin-bottom: 1rem;
        }

        /* Card Status Variants */
        .df-card-success {
            background-color: var(--surface);
            border-left: 3px solid var(--success);
        }
        .df-card-warning {
            background-color: var(--surface);
            border-left: 3px solid var(--warning);
        }
        .df-card-error {
            background-color: var(--surface);
            border-left: 3px solid var(--danger);
        }
        .df-card-info {
            background-color: var(--surface);
            border-left: 3px solid var(--primary);
        }

        /* Metric Block Styling */
        .df-metric-box {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.15rem 1.25rem;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 110px;
        }
        .df-metric-box:hover {
            border-color: var(--border-accent);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3), 0 0 16px rgba(56, 103, 255, 0.12);
        }
        .df-metric-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        .df-metric-icon-wrap {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: rgba(56, 103, 255, 0.12);
            border: 1px solid rgba(56, 103, 255, 0.25);
            color: var(--primary);
        }
        .df-metric-label {
            font-size: 0.72rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 600;
        }
        .df-metric-value {
            font-size: 1.75rem;
            font-weight: 750;
            color: var(--text-primary);
            letter-spacing: -0.03em;
            line-height: 1.1;
            margin-bottom: 0.25rem;
        }
        .df-metric-context {
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        /* Quick Action Cards */
        .df-quick-action {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem 1.15rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.65rem;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }
        .df-quick-action:hover {
            border-color: var(--primary);
            background-color: var(--surface-hover);
            transform: translateX(3px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25), 0 0 12px rgba(56, 103, 255, 0.15);
        }
        .df-quick-action-primary {
            background: linear-gradient(135deg, rgba(56, 103, 255, 0.9) 0%, rgba(120, 87, 255, 0.9) 100%);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 6px 20px rgba(56, 103, 255, 0.35);
        }
        .df-quick-action-primary:hover {
            background: linear-gradient(135deg, #3867FF 0%, #7857FF 100%);
            transform: translateX(3px);
            box-shadow: 0 8px 24px rgba(56, 103, 255, 0.5);
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            transition: all 0.18s ease !important;
            border: 1px solid var(--border) !important;
            background-color: var(--surface-secondary) !important;
            color: var(--text-primary) !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2) !important;
        }
        .stButton > button p,
        .stButton > button span,
        .stButton > button div {
            color: inherit !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
        }
        .stButton > button:hover {
            border-color: var(--border-accent) !important;
            background-color: var(--surface-hover) !important;
            color: #FFFFFF !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        }
        .stButton > button:active {
            transform: translateY(0) !important;
        }

        /* Primary Button */
        .stButton > button[kind="primary"] {
            background: var(--primary-gradient) !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            box-shadow: 0 4px 14px rgba(56, 103, 255, 0.35) !important;
        }
        .stButton > button[kind="primary"] p,
        .stButton > button[kind="primary"] span,
        .stButton > button[kind="primary"] div {
            color: #FFFFFF !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #4371FF 0%, #8364FF 100%) !important;
            border-color: rgba(255, 255, 255, 0.3) !important;
            box-shadow: 0 6px 20px rgba(56, 103, 255, 0.5) !important;
            transform: translateY(-1px) !important;
        }
        .stButton > button:disabled,
        .stButton > button[disabled] {
            background-color: #122238 !important;
            border-color: #162C4C !important;
            color: var(--text-muted) !important;
            cursor: not-allowed !important;
            transform: none !important;
            box-shadow: none !important;
            opacity: 0.7 !important;
        }
        .stButton > button:disabled p,
        .stButton > button:disabled span,
        .stButton > button:disabled div,
        .stButton > button[disabled] p,
        .stButton > button[disabled] span,
        .stButton > button[disabled] div {
            color: var(--text-muted) !important;
        }

        /* Form Inputs & Controls */
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div,
        .stTextInput input,
        .stTextArea textarea {
            border-radius: 8px !important;
            border-color: var(--border) !important;
            font-size: 0.875rem !important;
            background-color: var(--surface) !important;
            color: var(--text-primary) !important;
        }
        div[data-baseweb="input"]:focus-within > div,
        div[data-baseweb="select"]:focus-within > div,
        div[data-baseweb="textarea"]:focus-within > div,
        .stTextInput input:focus,
        .stTextArea textarea:focus {
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 2px rgba(56, 103, 255, 0.25) !important;
            background-color: var(--surface-secondary) !important;
        }

        /* Streamlit Selectbox Overrides */
        div[data-baseweb="select"] * {
            color: var(--text-primary) !important;
        }
        ul[data-baseweb="menu"] {
            background-color: var(--surface-secondary) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }
        li[data-baseweb="menu-item"]:hover {
            background-color: var(--surface-hover) !important;
            color: #FFFFFF !important;
        }

        /* Streamlit Alerts */
        div[data-testid="stAlert"] {
            border-radius: 10px !important;
            padding: 0.75rem 1rem !important;
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
        }

        /* HTML & Markdown Tables */
        table, .stTable table, [data-testid="stTable"] {
            width: 100% !important;
            border-collapse: collapse !important;
            background-color: var(--surface) !important;
            color: var(--text-primary) !important;
            border-radius: 8px !important;
            border: 1px solid var(--border) !important;
        }
        th, .stTable th, [data-testid="stTable"] th {
            background-color: var(--surface-secondary) !important;
            color: var(--text-primary) !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
            padding: 0.65rem 0.85rem !important;
            border-bottom: 1px solid var(--border) !important;
            border-right: 1px solid var(--border-subtle) !important;
        }
        td, .stTable td, [data-testid="stTable"] td {
            background-color: var(--surface) !important;
            color: var(--text-primary) !important;
            font-size: 0.85rem !important;
            padding: 0.6rem 0.85rem !important;
            border-bottom: 1px solid var(--border) !important;
            border-right: 1px solid var(--border-subtle) !important;
        }
        tr:hover td, .stTable tr:hover td {
            background-color: var(--surface-hover) !important;
        }

        /* Streamlit DataFrames & Data Editors */
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            font-size: 0.85rem !important;
            background-color: var(--surface) !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
        }
        [data-testid="stDataFrame"] > div, [data-testid="stDataEditor"] > div {
            background-color: var(--surface) !important;
        }

        /* Badges */
        .df-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            line-height: 1;
        }
        .df-badge-success {
            background: var(--success-bg);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .df-badge-warning {
            background: var(--warning-bg);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .df-badge-error {
            background: var(--danger-bg);
            color: var(--danger);
            border: 1px solid rgba(244, 63, 94, 0.3);
        }
        .df-badge-info {
            background: var(--info-bg);
            color: var(--primary);
            border: 1px solid rgba(56, 103, 255, 0.3);
        }
        .df-badge-purple {
            background: rgba(120, 87, 255, 0.15);
            color: #A78BFA;
            border: 1px solid rgba(120, 87, 255, 0.35);
        }
        .df-badge-neutral {
            background: var(--surface-secondary);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.75rem !important;
            border-bottom: 1px solid var(--border) !important;
            padding-bottom: 0.25rem !important;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 0.5rem 1rem !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            color: var(--text-secondary) !important;
            border-radius: 6px 6px 0 0 !important;
            transition: all 0.15s ease !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: var(--text-primary) !important;
            background-color: rgba(255, 255, 255, 0.03) !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--primary) !important;
            font-weight: 600 !important;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background: var(--primary-gradient) !important;
            height: 3px !important;
            border-radius: 3px 3px 0 0 !important;
        }

        /* Progress Bar */
        .stProgress > div > div > div > div {
            background: var(--primary-gradient) !important;
            box-shadow: 0 0 12px rgba(56, 103, 255, 0.5) !important;
            border-radius: 9999px !important;
        }
        .stProgress > div > div > div {
            background-color: var(--surface-secondary) !important;
            border-radius: 9999px !important;
        }

        /* Expanders */
        .streamlit-expanderHeader {
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            color: var(--text-primary) !important;
            font-weight: 600 !important;
            font-size: 0.875rem !important;
        }
        .streamlit-expanderContent {
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-top: none !important;
            border-radius: 0 0 8px 8px !important;
            padding: 1rem !important;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--sidebar-bg);
        }
        ::-webkit-scrollbar-thumb {
            background: #182C48;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #25446E;
        }

        /* Responsive Media Queries */
        @media (max-width: 992px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 1rem !important;
            }
            .df-card, .df-metric-box {
                padding: 1rem !important;
            }
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.75rem !important;
            }
        }
        </style>
    """), unsafe_allow_html=True)

def card(content_html: str, status: str = "neutral", elevated: bool = False):
    cls_map = {
        "success": "df-card-success",
        "warning": "df-card-warning",
        "error": "df-card-error",
        "info": "df-card-info",
        "neutral": ""
    }
    b_cls = cls_map.get(status, "")
    elev_cls = "df-card-elevated" if elevated else "df-card"
    st.markdown(clean_html(f"<div class='{elev_cls} {b_cls}'>{content_html}</div>"), unsafe_allow_html=True)

def metric_card(label: str, value: str, status: str = "neutral", context: str = "", icon_svg: str = None, delta: str = None):
    color = "var(--text-primary)"
    icon_bg = "rgba(56, 103, 255, 0.12)"
    icon_border = "rgba(56, 103, 255, 0.25)"
    icon_color = "var(--primary)"

    if status == "success":
        color = "var(--success)"
        icon_bg = "rgba(16, 185, 129, 0.12)"
        icon_border = "rgba(16, 185, 129, 0.25)"
        icon_color = "var(--success)"
    elif status == "warning":
        color = "var(--warning)"
        icon_bg = "rgba(245, 158, 11, 0.12)"
        icon_border = "rgba(245, 158, 11, 0.25)"
        icon_color = "var(--warning)"
    elif status == "error":
        color = "var(--danger)"
        icon_bg = "rgba(244, 63, 94, 0.12)"
        icon_border = "rgba(244, 63, 94, 0.25)"
        icon_color = "var(--danger)"
    elif status == "purple":
        color = "#A78BFA"
        icon_bg = "rgba(120, 87, 255, 0.15)"
        icon_border = "rgba(120, 87, 255, 0.35)"
        icon_color = "#A78BFA"

    # Default icons if none passed
    if not icon_svg:
        lbl = label.lower()
        if "table" in lbl:
            icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>'
        elif "row" in lbl or "record" in lbl:
            icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>'
        elif "relation" in lbl:
            icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'
        elif "issue" in lbl or "error" in lbl:
            icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
        elif "quality" in lbl or "score" in lbl or "readiness" in lbl:
            icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
        else:
            icon_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'

    delta_span = f"<span style='font-size: 0.72rem; color: {icon_color}; font-weight: 600;'>{delta}</span>" if delta else ""
    ctx_span = f"<span class='df-metric-context'>{context}</span>" if context else ""

    html = (
        f"<div class='df-metric-box'>"
        f"<div class='df-metric-top'>"
        f"<div class='df-metric-label'>{label}</div>"
        f"<div class='df-metric-icon-wrap' style='background: {icon_bg}; border-color: {icon_border}; color: {icon_color};'>{icon_svg}</div>"
        f"</div>"
        f"<div>"
        f"<div class='df-metric-value' style='color: {color};'>{value}</div>"
        f"<div style='display: flex; justify-content: space-between; align-items: center; min-height: 1.15rem;'>"
        f"{ctx_span}{delta_span}"
        f"</div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(clean_html(html), unsafe_allow_html=True)

def badge(text: str, level: str = "neutral"):
    cls_map = {
        "success": "df-badge-success",
        "warning": "df-badge-warning",
        "error": "df-badge-error",
        "info": "df-badge-info",
        "purple": "df-badge-purple",
        "neutral": "df-badge-neutral"
    }
    b_cls = cls_map.get(level, "df-badge-neutral")
    return f"<span class='df-badge {b_cls}'>{text}</span>"

def logo_html():
    return (
        '<div style="display: flex; align-items: center; padding: 0.75rem 0.75rem 1.25rem 0.75rem; border-bottom: 1px solid var(--sidebar-border); margin-bottom: 0.75rem;">'
        '<div style="width: 36px; height: 36px; border-radius: 10px; background: linear-gradient(135deg, #3867FF 0%, #7857FF 100%); display: flex; align-items: center; justify-content: center; margin-right: 10px; box-shadow: 0 4px 14px rgba(56, 103, 255, 0.4);">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>'
        '<polyline points="2 17 12 22 22 17"></polyline>'
        '<polyline points="2 12 12 17 22 12"></polyline>'
        '</svg>'
        '</div>'
        '<div>'
        '<div style="font-weight: 800; font-size: 1.05rem; letter-spacing: 0.04em; color: #FFFFFF; line-height: 1.1;">DATAFORGE</div>'
        '<div style="font-size: 0.7rem; color: #9AAAC2; font-weight: 500; letter-spacing: 0.02em;">Data. Analyze. Create.</div>'
        '</div>'
        '</div>'
    )

def page_header(title: str, subtitle: str = None, badge_text: str = None, badge_level: str = "neutral"):
    sub_html = f"<div style='color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;'>{subtitle}</div>" if subtitle else ""
    badge_html = f"<div>{badge(badge_text, badge_level)}</div>" if badge_text else ""
    html = (
        f"<div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem;'>"
        f"<div>"
        f"<h2 style='margin: 0; font-size: 1.35rem; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em;'>{title}</h2>"
        f"{sub_html}"
        f"</div>"
        f"{badge_html}"
        f"</div>"
    )
    st.markdown(clean_html(html), unsafe_allow_html=True)
