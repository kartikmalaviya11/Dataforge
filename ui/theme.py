import streamlit as st

def apply_theme():
    st.set_page_config(
        page_title="DATAFORGE",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* DATAFORGE Professional Analytics Theme */
        :root {
            --primary: #2563EB;
            --primary-hover: var(--primary);
            --primary-soft: #EFF6FF;
            --page-bg: #F8FAFC;
            --surface: #FFFFFF;
            --surface-secondary: #F1F5F9;
            --sidebar-bg: #0F172A;
            --sidebar-hover: #1E293B;
            --text-primary: #0F172A;
            --text-secondary: #475569;
            --text-muted: #64748B;
            --border: #E2E8F0;
            --success: #16A34A;
            --success-bg: #F0FDF4;
            --warning: #D97706;
            --warning-bg: #FFFBEB;
            --danger: #DC2626;
            --danger-bg: #FEF2F2;
            --info: #2563EB;
            --info-bg: #EFF6FF;
        }

        /* App Background */
        .stApp {
            background-color: var(--page-bg);
            color: var(--text-primary);
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }

        /* Typography */
        h1 { font-size: 1.875rem !important; font-weight: 700 !important; color: var(--text-primary) !important; letter-spacing: -0.02em; margin-bottom: 1rem !important; }
        h2 { font-size: 1.375rem !important; font-weight: 650 !important; color: var(--text-primary) !important; margin-top: 1.25rem !important; margin-bottom: 0.75rem !important; }
        h3 { font-size: 1.0625rem !important; font-weight: 600 !important; color: var(--text-primary) !important; margin-bottom: 0.5rem !important; }
        p, .stMarkdown p { font-size: 0.875rem; font-weight: 400; line-height: 1.6; color: var(--text-secondary); }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--sidebar-bg) !important;
            border-right: 1px solid var(--sidebar-hover) !important;
        }
        [data-testid="stSidebar"] * {
            color: #F8FAFC;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }

        /* Sidebar Buttons */
        [data-testid="stSidebar"] .stButton > button {
            background-color: transparent !important;
            color: #94A3B8 !important;
            border: none !important;
            box-shadow: none !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
            font-size: 0.875rem !important;
            border-radius: 4px !important;
            border-left: 3px solid transparent !important;
            margin: 0 0.5rem 0.25rem 0.5rem !important;
            width: calc(100% - 1rem) !important;
            transition: all 0.15s ease;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: var(--sidebar-hover) !important;
            color: #FFFFFF !important;
        }

        /* Sidebar Section Headers */
        .sidebar-section {
            color: #64748B !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700 !important;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
            padding-left: 1rem;
        }

        /* Cards */
        .df-card {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
            margin-bottom: 1rem;
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }
        .df-card:hover {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        }

        /* Card Status Variants */
        .df-card-success { background-color: var(--success-bg); border-color: #bbf7d0; }
        .df-card-success .df-card-title, .df-card-success .df-card-body { color: var(--success) !important; }

        .df-card-warning { background-color: var(--warning-bg); border-color: #fde68a; }
        .df-card-warning .df-card-title, .df-card-warning .df-card-body { color: var(--warning) !important; }

        .df-card-error { background-color: var(--danger-bg); border-color: #fecaca; }
        .df-card-error .df-card-title, .df-card-error .df-card-body { color: var(--danger) !important; }

        .df-card-info { background-color: var(--info-bg); border-color: #bfdbfe; }
        .df-card-info .df-card-title, .df-card-info .df-card-body { color: var(--info) !important; }

        /* Metric block */
        .df-metric-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }
        .df-metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.02em;
            line-height: 1;
            margin-bottom: 0.25rem;
        }
        .df-metric-context {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        /* Main Buttons */
        .stButton > button {
            border-radius: 6px !important;
            font-weight: 600 !important;
            font-size: 0.875rem !important;
            transition: all 0.15s ease !important;
            border: 1px solid var(--border) !important;
            background-color: var(--surface) !important;
            color: var(--text-primary) !important;
            padding: 0.5rem 1rem !important;
        }
        .stButton > button p,
        .stButton > button span,
        .stButton > button div {
            color: inherit !important;
            font-weight: 600 !important;
            font-size: 0.875rem !important;
        }
        .stButton > button:hover {
            border-color: var(--text-secondary) !important;
            background-color: var(--surface-secondary) !important;
            transform: translateY(-1px);
        }
        .stButton > button:active {
            transform: translateY(0);
        }

        .stButton > button[kind="primary"] {
            background-color: var(--primary) !important;
            color: #FFFFFF !important;
            border: 1px solid var(--primary) !important;
        }
        .stButton > button[kind="primary"] p,
        .stButton > button[kind="primary"] span,
        .stButton > button[kind="primary"] div {
            color: #FFFFFF !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #1D4ED8 !important;
            border-color: #1D4ED8 !important;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.25) !important;
        }
        .stButton > button:disabled,
        .stButton > button[disabled] {
            background-color: #E2E8F0 !important;
            border-color: #CBD5E1 !important;
            cursor: not-allowed !important;
            transform: none !important;
            box-shadow: none !important;
            opacity: 0.85 !important;
        }
        .stButton > button:disabled p,
        .stButton > button:disabled span,
        .stButton > button:disabled div,
        .stButton > button[disabled] p,
        .stButton > button[disabled] span,
        .stButton > button[disabled] div {
            color: #64748B !important;
        }

        /* Form Inputs & Controls */
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div,
        .stTextInput input,
        .stTextArea textarea {
            border-radius: 6px !important;
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
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
        }

        /* Streamlit Alerts */
        div[data-testid="stAlert"] {
            border-radius: 8px !important;
            padding: 0.75rem 1rem !important;
            border: 1px solid !important;
        }

        /* Tables */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            font-size: 0.875rem !important;
            background-color: var(--surface);
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02);
        }

        /* Badges */
        .df-badge {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 9999px; /* full rounded */
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .df-badge-success { background: var(--success-bg); color: var(--success); border: 1px solid #bbf7d0; }
        .df-badge-warning { background: var(--warning-bg); color: var(--warning); border: 1px solid #fde68a; }
        .df-badge-error { background: var(--danger-bg); color: var(--danger); border: 1px solid #fecaca; }
        .df-badge-info { background: var(--info-bg); color: var(--info); border: 1px solid #bfdbfe; }
        .df-badge-neutral { background: var(--surface-secondary); color: var(--text-secondary); border: 1px solid var(--border); }

        /* Data Tabs Overrides */
        .stTabs [data-baseweb="tab-list"] {
            gap: 1rem;
            border-bottom: 1px solid var(--border);
        }
        .stTabs [data-baseweb="tab"] {
            padding-top: 0.5rem;
            padding-bottom: 0.5rem;
            font-size: 0.875rem;
            font-weight: 500;
        }

        /* Status/Spinner Overrides */
        .stSpinner > div > div {
            border-color: var(--primary) transparent var(--primary) transparent !important;
        }

        /* Responsive Media Queries */
        @media (max-width: 992px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 1.5rem !important;
            }
            .df-card {
                padding: 1rem !important;
            }
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.75rem !important;
            }
        }

        </style>
    """, unsafe_allow_html=True)

def card(content_html: str, status: str = "neutral"):
    cls_map = {
        "success": "df-card-success",
        "warning": "df-card-warning",
        "error": "df-card-error",
        "info": "df-card-info",
        "neutral": ""
    }
    b_cls = cls_map.get(status, "")
    st.markdown(f"<div class='df-card {b_cls}'>{content_html}</div>", unsafe_allow_html=True)

def metric_card(label: str, value: str, status: str = "neutral", context: str = ""):
    color = "var(--text-primary)"
    if status == "success": color = "var(--success)"
    elif status == "warning": color = "var(--warning)"
    elif status == "error": color = "var(--danger)"

    ctx_html = f"<div class='df-metric-context'>{context}</div>" if context else ""

    st.markdown(f"""
    <div class='df-card'>
        <div class='df-metric-label'>{label}</div>
        <div class='df-metric-value' style='color: {color};'>{value}</div>
        {ctx_html}
    </div>
    """, unsafe_allow_html=True)

def badge(text: str, level: str = "neutral"):
    cls_map = {
        "success": "df-badge-success",
        "warning": "df-badge-warning",
        "error": "df-badge-error",
        "info": "df-badge-info",
        "neutral": "df-badge-neutral"
    }
    b_cls = cls_map.get(level, "df-badge-neutral")
    return f"<span class='df-badge {b_cls}'>{text}</span>"

def logo_html():
    return '''
    <div style="display: flex; align-items: center; font-weight: 700; font-size: 1.125rem; letter-spacing: 0.05em; color: #FFFFFF; margin-bottom: 1.5rem; padding-left: 1rem; padding-top: 0.5rem;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;">
            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
            <polyline points="2 17 12 22 22 17"></polyline>
            <polyline points="2 12 12 17 22 12"></polyline>
        </svg>
        DATAFORGE
    </div>
    '''

def page_header(title: str, subtitle: str = None):
    sub_html = f"<div style='color: var(--text-secondary); font-size: 0.875rem; margin-top: 0.25rem;'>{subtitle}</div>" if subtitle else ""
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">{title}</h2>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)
