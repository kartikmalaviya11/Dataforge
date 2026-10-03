import streamlit as st

def apply_theme():
    st.set_page_config(
        page_title="DATAFORGE",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
        <style>
        /* DATAFORGE Professional Analytics Theme */
        :root {
            --sidebar-bg: #111827;
            --primary: #1D4ED8;
            --page-bg: #F5F7FA;
            --card-bg: #FFFFFF;
            --text-main: #111827;
            --text-secondary: #64748B;
            --border: #E2E8F0;
            --success: #15803D;
            --warning: #B45309;
            --danger: #B91C1C;
            --muted: #94A3B8;
        }

        /* App Background */
        .stApp {
            background-color: var(--page-bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        
        /* Typography overrides */
        h1 { font-size: 2.25rem !important; font-weight: 700 !important; color: var(--text-main) !important; letter-spacing: -0.02em; }
        h2 { font-size: 1.75rem !important; font-weight: 600 !important; color: var(--text-main) !important; margin-top: 1.5rem !important; }
        h3 { font-size: 1.25rem !important; font-weight: 600 !important; color: var(--text-main) !important; }
        p { line-height: 1.6; color: var(--text-secondary); }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--sidebar-bg);
            border-right: none;
        }
        [data-testid="stSidebar"] * {
            color: #FFFFFF;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        
        /* Sidebar Buttons */
        [data-testid="stSidebar"] .stButton > button {
            background-color: transparent !important;
            color: var(--muted) !important;
            border: none !important;
            box-shadow: none !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.6rem 1rem !important;
            font-weight: 500 !important;
            border-radius: 0 4px 4px 0 !important;
            border-left: 3px solid transparent !important;
            margin: 0 !important;
            transition: all 0.2s ease;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: rgba(255,255,255,0.05) !important;
            color: #FFFFFF !important;
            border-left: 3px solid var(--muted) !important;
        }

        /* Sidebar Section Headers */
        .sidebar-section {
            color: var(--text-secondary);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
            margin-top: 2rem;
            margin-bottom: 0.75rem;
            padding-left: 1rem;
        }

        /* Cards */
        .df-card {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
            margin-bottom: 1rem;
            transition: transform 0.2s ease;
        }
        
        /* Metric block */
        .df-metric-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.02em;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }
        .df-metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-main);
            letter-spacing: -0.01em;
        }
        
        /* Main Buttons */
        .stButton>button {
            border-radius: 6px;
            font-weight: 500;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid var(--border);
            background-color: var(--card-bg);
            color: var(--text-main);
            padding: 0.5rem 1rem;
        }
        .stButton>button:hover {
            border-color: var(--text-secondary);
            color: var(--text-main);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transform: translateY(-1px);
        }
        .stButton>button:active {
            transform: translateY(0);
        }
        .stButton>button[kind="primary"] {
            background-color: var(--primary);
            color: white;
            border: 1px solid var(--primary);
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        .stButton>button[kind="primary"]:hover {
            background-color: #1e40af; /* darker blue */
            border-color: #1e40af;
            color: white;
            box-shadow: 0 4px 6px -1px rgba(29, 78, 216, 0.2), 0 2px 4px -1px rgba(29, 78, 216, 0.1);
        }
        
        /* Tables */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }
        
        /* Badges */
        .df-badge {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        .df-badge-success { background: #DCFCE7; color: var(--success); border: 1px solid #bbf7d0; }
        .df-badge-warning { background: #FEF3C7; color: var(--warning); border: 1px solid #fde68a; }
        .df-badge-error { background: #FEE2E2; color: var(--danger); border: 1px solid #fecaca; }
        .df-badge-neutral { background: #F1F5F9; color: var(--text-secondary); border: 1px solid #e2e8f0; }

        </style>
    """, unsafe_allow_html=True)

def card(content_html: str):
    st.markdown(f"<div class='df-card'>{content_html}</div>", unsafe_allow_html=True)

def metric_card(label: str, value: str, status: str = "neutral"):
    color = "var(--text-main)"
    if status == "success": color = "var(--success)"
    elif status == "warning": color = "var(--warning)"
    elif status == "error": color = "var(--danger)"
    
    st.markdown(f"""
    <div class='df-card' style='padding: 1rem;'>
        <div class='df-metric-label'>{label}</div>
        <div class='df-metric-value' style='color: {color};'>{value}</div>
    </div>
    """, unsafe_allow_html=True)

def badge(text: str, level: str = "neutral"):
    cls_map = {
        "success": "df-badge-success",
        "warning": "df-badge-warning",
        "error": "df-badge-error",
        "neutral": "df-badge-neutral"
    }
    b_cls = cls_map.get(level, "df-badge-neutral")
    return f"<span class='df-badge {b_cls}'>{text}</span>"

def logo_html():
    return '''
    <div style="display: flex; align-items: center; font-weight: 700; font-size: 1.25rem; letter-spacing: 0.05em; color: #FFFFFF; margin-bottom: 1rem; padding-left: 1rem;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D4ED8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 10px;">
            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
            <polyline points="2 17 12 22 22 17"></polyline>
            <polyline points="2 12 12 17 22 12"></polyline>
        </svg>
        DATAFORGE
    </div>
    '''
