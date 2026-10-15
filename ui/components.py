import streamlit as st

def empty_state(title: str, description: str, action_label: str = None, target_page: str = None):
    icon_svg = '''<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 1rem;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'''
    st.markdown(f"""
    <div style="text-align: center; padding: 4rem 2rem; background: var(--surface); border: 1px dashed var(--border); border-radius: 12px; margin: 1rem 0;">
        {icon_svg}
        <h3 style="margin-bottom: 0.5rem; color: var(--text-primary);">{title}</h3>
        <p style="color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.875rem; max-width: 400px; margin-left: auto; margin-right: auto;">{description}</p>
    </div>
    """, unsafe_allow_html=True)

    if action_label and target_page:
        _, col_btn, _ = st.columns([1, 1, 1])
        with col_btn:
            if st.button(action_label, type="primary", use_container_width=True, key=f"empty_btn_{title}"):
                st.session_state.current_page = target_page
                st.rerun()

def dataforge_button(label: str, type="primary", key=None, disabled=False, use_container_width=False, container=st):
    if key is None:
        import hashlib; key = f"btn_{hashlib.md5(label.encode()).hexdigest()}"

    is_running = st.session_state.get("active_operation") is not None
    label_show = f"Working..." if is_running and getattr(st.session_state, "last_clicked", None) == key else label

    if container.button(label_show, type=type, key=key, disabled=disabled or is_running, use_container_width=use_container_width):
        st.session_state.active_operation = key
        st.session_state.last_clicked = key
        return True
    return False

def clear_operation():
    if "active_operation" in st.session_state:
        del st.session_state.active_operation
    if "last_clicked" in st.session_state:
        del st.session_state.last_clicked

def run_action(operation_name, steps, result_key=None):
    st.session_state.active_operation = operation_name

    import time
    t_start = time.time()
    res = None

    try:
        with st.status(f"{operation_name}...", expanded=True) as status:
            for step_name, step_fn in steps:
                status.update(label=step_name, state="running")
                t_step_start = time.time()
                res = step_fn()
                t_step_end = time.time()
                print(f"[{operation_name}] {step_name}: {t_step_end - t_step_start:.4f}s")
            status.update(label=f"Completed successfully", state="complete", expanded=False)

        t_end = time.time()
        print(f"[{operation_name}] total={t_end - t_start:.4f}s")

        if result_key and hasattr(st.session_state, result_key):
            return True, getattr(st.session_state, result_key)
        return True, res
    except Exception as e:
        st.markdown(f"""
        <div class="df-card df-card-error">
            <h3 style="margin-top:0;">Operation Failed</h3>
            <p><strong>What happened:</strong> {operation_name} could not be completed.</p>
            <p><strong>Why it happened:</strong> {str(e)}</p>
            <p style="margin-bottom:0;"><strong>Next steps:</strong> Check your inputs or review the technical details below.</p>
        </div>
        """, unsafe_allow_html=True)
        with st.expander("Technical Details"):
            import traceback
            print(traceback.format_exc())
            st.code(traceback.format_exc(), language="python")
        return False, str(e)
    finally:
        clear_operation()
