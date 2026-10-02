import pytest
from unittest.mock import patch
from ui.components import dataforge_button, run_action, clear_operation
import streamlit as st

def test_dataforge_button_locking_regression():
    st.session_state.active_operation = "some_other_action"
    with patch("ui.components.st.button") as mock_btn:
        dataforge_button("Test")
        kwargs = mock_btn.call_args[1]
        assert kwargs.get("disabled") == True
    del st.session_state.active_operation

def test_run_action_clears_state_on_success():
    st.session_state.active_operation = "my_action"
    def step():
        pass
    
    with patch("ui.components.st.status"):
        run_action("my_action", [("Step 1", step)])
            
    assert "active_operation" not in st.session_state

def test_run_action_clears_state_on_failure():
    st.session_state.active_operation = "my_action"
    def step():
        raise ValueError("Simulated crash")
    
    with patch("ui.components.st.status"):
        with patch("ui.components.st.error"):
            with patch("ui.components.st.expander"):
                with patch("ui.components.st.code"):
                    run_action("my_action", [("Step 1", step)])
                
    assert "active_operation" not in st.session_state
