import streamlit as st

def apply_theme():
    st.set_page_config(
        page_title="DATAFORGE",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
        <style>
        /* Classic Professional Analytics Theme */
        :root {
            --bg-color: #F8F9FA;
            --card-bg: #FFFFFF;
            --border-color: #E2E8F0;
            --primary-navy: #0F172A;
            --secondary-slate: #64748B;
            --success-green: #10B981;
            --warning-amber: #F59E0B;
            --danger-red: #EF4444;
            --text-main: #334155;
            --text-muted: #94A3B8;
        }

        /* App Background */
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        
        /* Typography overrides */
        h1, h2, h3, h4, h5, h6 {
            color: var(--primary-navy) !important;
            font-weight: 600 !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--card-bg);
            border-right: 1px solid var(--border-color);
        }
        
        /* Cards */
        .df-card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 1rem;
        }
        
        /* Value blocks / Metric replacements */
        .df-metric-label {
            font-size: 0.85rem;
            color: var(--secondary-slate);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }
        .df-metric-value {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--primary-navy);
        }
        
        /* Buttons */
        .stButton>button {
            border-radius: 4px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .stButton>button[kind="primary"] {
            background-color: var(--primary-navy);
            color: white;
            border: none;
        }
        .stButton>button[kind="primary"]:hover {
            background-color: #1E293B;
        }
        
        /* Tables */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--border-color);
            border-radius: 4px;
            overflow: hidden;
        }
        
        /* Badges */
        .df-badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .df-badge-success { background: #DCFCE7; color: #166534; }
        .df-badge-warning { background: #FEF3C7; color: #92400E; }
        .df-badge-error { background: #FEE2E2; color: #991B1B; }
        .df-badge-neutral { background: #F1F5F9; color: #475569; }

        </style>
    """, unsafe_allow_html=True)

def card(content_html: str):
    st.markdown(f"<div class='df-card'>{content_html}</div>", unsafe_allow_html=True)

def metric_card(label: str, value: str, status: str = "neutral"):
    color = "var(--primary-navy)"
    if status == "success": color = "var(--success-green)"
    elif status == "warning": color = "var(--warning-amber)"
    elif status == "error": color = "var(--danger-red)"
    
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
