import streamlit as st
from src.workspace import ProjectWorkspace

def render_domain_templates(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Domain Templates</h2>
    </div>
    ''', unsafe_allow_html=True)
    templates = [
        "E-commerce", "Sales", "Customer Retention", 
        "Delivery", "Seller Performance", "Product Performance", "Reviews"
    ]
    selected = st.selectbox("Select Domain Template", templates)
    
    if st.button("Apply Template", type="primary"):
        try:
            from src.domain_templates import DomainTemplateManager
            mgr = DomainTemplateManager(ws)
            # Try to load if available, or just mock it for UI binding
            tpl = mgr.load_template(selected)
            if tpl:
                st.success(f"Loaded {selected} template.")
                st.write(tpl)
            else:
                st.warning("Template not found.")
        except ImportError:
            st.error("Backend not implemented yet.")
        except Exception as e:
            st.error(f"Error: {e}")

def render_settings(ws: ProjectWorkspace):
    st.markdown('''
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
        <h2 style="margin: 0; font-size: 1.375rem; font-weight: 650; color: var(--text-primary);">Settings</h2>
    </div>
    ''', unsafe_allow_html=True)
    st.info("Global settings.")


