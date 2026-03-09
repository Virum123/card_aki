"""Session state helpers."""

from __future__ import annotations

import streamlit as st

SESSION_DEFAULTS = {
    "survey_step": 0,
    "survey_answers": {},
    "visible_results": 10,
    "survey_phase": "questions",
    "animation_started_at": 0.0,
    "explore_mode": "quick",
    "tie_break_pair": None,
    "tie_break_choice": None,
}


def init_session_state() -> None:
    for k, v in SESSION_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_session_state(mode: str | None = None) -> None:
    st.session_state.survey_step = 0
    st.session_state.survey_answers = {}
    st.session_state.visible_results = 10
    st.session_state.survey_phase = "questions"
    st.session_state.animation_started_at = 0.0
    st.session_state.tie_break_pair = None
    st.session_state.tie_break_choice = None
    if mode is not None:
        st.session_state.explore_mode = mode
