import streamlit as st

def empty_state(title: str, description: str, action_label: str, target_page: str):
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.markdown(description)
        if st.button(action_label, type="primary"):
            st.session_state.current_page = target_page
            st.rerun()

def dataforge_button(label: str, type="primary", key=None, disabled=False, use_container_width=False, container=st):
    if key is None:
        import hashlib; key = f"btn_{hashlib.md5(label.encode()).hexdigest()}"
        
    is_running = st.session_state.get("active_operation") is not None
    label_show = f"Generating..." if is_running and getattr(st.session_state, "last_clicked", None) == key else label
    
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
        with st.status(f"Running {operation_name}...") as status:
            for step_name, step_fn in steps:
                status.update(label=step_name)
                t_step_start = time.time()
                res = step_fn()
                t_step_end = time.time()
                print(f"[{operation_name}] {step_name}: {t_step_end - t_step_start:.4f}s")
            status.update(label=f"SUCCESS: {operation_name}", state="complete")
            
        t_end = time.time()
        print(f"[{operation_name}] total={t_end - t_start:.4f}s")
        
        if result_key and hasattr(st.session_state, result_key):
            return True, getattr(st.session_state, result_key)
        return True, res
    except Exception as e:
        st.error(f"**Operation Failed:** {str(e)}")
        with st.expander("Show Technical Details"):
            import traceback
            st.code(traceback.format_exc(), language="python")
        return False, str(e)
    finally:
        clear_operation()
