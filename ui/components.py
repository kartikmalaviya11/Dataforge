import streamlit as st
from ui.theme import clean_html

def empty_state(title: str, description: str, action_label: str = None, target_page: str = None):
    icon_svg = (
        '<div style="width: 64px; height: 64px; border-radius: 16px; background: rgba(56, 103, 255, 0.1); '
        'border: 1px solid rgba(56, 103, 255, 0.25); display: flex; align-items: center; justify-content: center; '
        'margin: 0 auto 1.25rem auto; color: var(--primary); box-shadow: 0 0 24px rgba(56, 103, 255, 0.15);">'
        '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"></circle>'
        '<line x1="12" y1="8" x2="12" y2="12"></line>'
        '<line x1="12" y1="16" x2="12.01" y2="16"></line>'
        '</svg>'
        '</div>'
    )
    html = f"""
    <div style="text-align: center; padding: 3.5rem 2rem; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; margin: 1.5rem 0; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);">
        {icon_svg}
        <h3 style="margin-bottom: 0.5rem; color: var(--text-primary); font-size: 1.15rem; font-weight: 700;">{title}</h3>
        <p style="color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.875rem; max-width: 440px; margin-left: auto; margin-right: auto; line-height: 1.6;">{description}</p>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)

    if action_label and target_page:
        _, col_btn, _ = st.columns([1.2, 1, 1.2])
        with col_btn:
            if st.button(action_label, type="primary", use_container_width=True, key=f"empty_btn_{title}"):
                st.session_state.current_page = target_page
                st.rerun()

def dataforge_button(label: str, type="primary", key=None, disabled=False, use_container_width=False, container=st):
    if key is None:
        import hashlib
        key = f"btn_{hashlib.md5(label.encode()).hexdigest()}"

    is_running = st.session_state.get("active_operation") is not None
    label_show = "Working..." if is_running and getattr(st.session_state, "last_clicked", None) == key else label

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
            status.update(label="Completed successfully", state="complete", expanded=False)

        t_end = time.time()
        print(f"[{operation_name}] total={t_end - t_start:.4f}s")

        if result_key and hasattr(st.session_state, result_key):
            return True, getattr(st.session_state, result_key)
        return True, res
    except Exception as e:
        err_card = f"""
        <div class="df-card df-card-error">
            <h3 style="margin-top:0; color: var(--danger); font-size: 1.1rem; font-weight: 700;">Operation Failed</h3>
            <p><strong style="color: var(--text-primary);">What happened:</strong> {operation_name} could not be completed.</p>
            <p><strong style="color: var(--text-primary);">Why it happened:</strong> {str(e)}</p>
            <p style="margin-bottom:0;"><strong style="color: var(--text-primary);">Next steps:</strong> Check your inputs or review the technical details below.</p>
        </div>
        """
        st.markdown(clean_html(err_card), unsafe_allow_html=True)
        with st.expander("Technical Details"):
            import traceback
            print(traceback.format_exc())
            st.code(traceback.format_exc(), language="python")
        return False, str(e)
    finally:
        clear_operation()
