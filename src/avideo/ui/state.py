"""avideo.ui.state — Session-state initialisation, phase constants, and workdir-based phase reconstruction.

Design rules:
- st.session_state holds ONLY: "workdir_path" (str|None), "phase" (int 1-6),
  "run_config" (dict of RunConfig kwargs), and ephemeral form inputs.
- All pipeline artifacts are read from workdir/*.json via WorkdirManager on every rerun.
- workdir_phase_from_done_markers() reconstructs the wizard position purely from
  filesystem done-markers so the UI survives browser refresh/close.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.utils.workdir import WorkdirManager

if TYPE_CHECKING:
    pass  # st imported lazily inside functions to allow unit-testing without streamlit

#: Six wizard phases: (phase_number, display_name)
PHASES: list[tuple[int, str]] = [
    (1, "Contenido"),
    (2, "Guion + Slides"),
    (3, "Diapositivas"),
    (4, "Voz"),
    (5, "Extras"),
    (6, "Ensamblaje"),
]

#: Maps each wizard phase to the pipeline stage whose done-marker signals completion.
#: Phase is "complete" when its completion stage's done marker exists on disk.
PHASE_COMPLETION_STAGE: dict[int, str] = {
    1: "context",        # Phase 1 complete when context/bullets ingested
    2: "scriptwriter",   # Phase 2 complete when script is generated
    3: "verify",         # Phase 3 complete when slides are verified
    4: "align",          # Phase 4 complete when audio is aligned (timings.json ready)
    5: "subs",           # Phase 5 complete when subtitles generated
    6: "assemble",       # Phase 6 complete when assembly done
}

_MAX_PHASE = max(PHASES, key=lambda p: p[0])[0]  # 6


def workdir_phase_from_done_markers(workdir: WorkdirManager) -> int:
    """Derive the current wizard phase from workdir done-markers.

    Scans PHASE_COMPLETION_STAGE in ascending phase order and returns the
    first phase whose completion stage is NOT yet done.  If all phases are
    complete, returns the last phase number (6) so the UI stays on Phase 6.

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        int in range [1, 6] — the phase the wizard should display.
    """
    for phase_num, _ in PHASES:
        completion_stage = PHASE_COMPLETION_STAGE[phase_num]
        if not workdir.is_done(completion_stage):
            return phase_num
    return _MAX_PHASE


def init_session_state() -> None:
    """Initialise st.session_state with default keys if not already set.

    Call once at the top of app.py on every rerun.  Safe to call multiple
    times (idempotent: only sets keys that are absent).
    """
    import streamlit as st  # noqa: PLC0415 — lazy import; allows unit tests without streamlit

    if "phase" not in st.session_state:
        st.session_state["phase"] = 1
    if "workdir_path" not in st.session_state:
        st.session_state["workdir_path"] = None
    if "run_config" not in st.session_state:
        st.session_state["run_config"] = {}


def advance_phase() -> None:
    """Increment session_state["phase"] by 1 (max 6) and trigger a rerun.

    Must only be called from the main Streamlit script thread (not from a
    background thread).  Reads and writes st.session_state directly.
    """
    import streamlit as st  # noqa: PLC0415

    current = st.session_state.get("phase", 1)
    if current < _MAX_PHASE:
        st.session_state["phase"] = current + 1
    st.rerun()
