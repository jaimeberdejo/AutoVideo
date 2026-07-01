"""avideo.ui.app — Streamlit entry point for the Studio Guiado wizard.

Structural overview:
- st.set_page_config must be the FIRST Streamlit call (required by Streamlit).
- main() is called unconditionally at module level — Streamlit re-runs the
  whole script on every interaction, so calling main() once per run is correct.
- Session state holds ONLY: workdir_path (str|None), phase (int 1-6),
  run_config (dict).  All pipeline artifacts are read from workdir on each rerun.
- workdir is derived from AVIDEO_STUDIO_WORKDIR env var (--workdir flag) or
  auto-created under ./runs/ on first load.
- Phase is reconstructed from workdir done-markers on every (re)load so the
  wizard survives browser refresh/close.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from avideo.ui.state import (
    PHASE_COMPLETION_STAGE,
    PHASES,
    advance_phase,
    init_session_state,
    rehydrate_run_config,
    workdir_phase_from_done_markers,
)
from avideo.utils.workdir import WorkdirManager

# ---------------------------------------------------------------------------
# Phase metadata
# ---------------------------------------------------------------------------

#: One-line description shown under each phase header in the main area.
_PHASE_DESCRIPTIONS: dict[int, str] = {
    1: "Introduce el tema, la duración y los bullets del vídeo.",
    2: "Genera y revisa el guion slide a slide.",
    3: "Genera o sube las diapositivas y verifica su calidad.",
    4: "Elige el proveedor de voz y escucha los previews.",
    5: "Configura los extras: subtítulos, música de fondo, transiciones.",
    6: "Monta el vídeo final y descárgalo.",
}

# ---------------------------------------------------------------------------
# Page config — must execute before any other st.* call.
# Streamlit runs this at import time, before main() is called.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Auto Video Narrado — Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Streamlit entry point for avideo studio.

    Called unconditionally at module level (see bottom of file). Streamlit
    re-runs the entire script on each interaction, so this pattern is correct.
    """
    from dotenv import load_dotenv  # noqa: PLC0415

    load_dotenv(override=False)  # ensure .env API keys reach SDKs inside the st session

    # ------------------------------------------------------------------
    # 1. Initialise session state (idempotent — only sets missing keys)
    # ------------------------------------------------------------------
    init_session_state()

    # ------------------------------------------------------------------
    # 2. Workdir setup — run once per new session
    # ------------------------------------------------------------------
    if st.session_state["workdir_path"] is None:
        # Honour the env var set by `avideo studio --workdir <path>`; otherwise
        # create a fresh timestamped run directory under ./runs/.
        env_workdir = os.environ.get("AVIDEO_STUDIO_WORKDIR")
        if env_workdir:
            workdir_path = Path(env_workdir)
        else:
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            workdir_path = Path("runs") / f"run_{ts}" / "workdir"
        st.session_state["workdir_path"] = str(workdir_path)

    workdir = WorkdirManager(Path(st.session_state["workdir_path"]))

    # Reconstruct phase from done-markers on first load (or after a page refresh).
    # We use a sentinel key "_phase_initialised" so this only fires once per session
    # (not on every rerun), allowing user navigation to take precedence thereafter.
    if not st.session_state.get("_phase_initialised"):
        st.session_state["phase"] = workdir_phase_from_done_markers(workdir)
        # Rehydrate run_config (topic/duration) from workdir — session_state
        # itself doesn't survive a browser refresh or app restart, only the
        # workdir does. Without this, RunConfig(**run_config) raises a
        # pydantic ValidationError ("duration Field required") on any phase
        # past Phase 1 after a refresh.
        st.session_state["run_config"] = {
            **rehydrate_run_config(workdir),
            **st.session_state.get("run_config", {}),
        }
        st.session_state["_phase_initialised"] = True

    # ------------------------------------------------------------------
    # 3. Sidebar — stepper + workdir info + "New project" button
    # ------------------------------------------------------------------
    with st.sidebar:
        st.title("Studio Guiado")
        st.caption(f"Workdir: {st.session_state['workdir_path']}")
        st.divider()

        current_phase = st.session_state["phase"]
        for phase_num, phase_name in PHASES:
            completion_stage = PHASE_COMPLETION_STAGE[phase_num]
            if workdir.is_done(completion_stage):
                marker = "✅"
            elif phase_num == current_phase:
                marker = "▶"
            elif phase_num < current_phase:
                # Phase was visited but done-marker may be absent (placeholder mode)
                marker = "✅"
            else:
                marker = "○"
            st.write(f"{marker} Fase {phase_num}: {phase_name}")

        st.divider()
        if st.button("Nuevo proyecto", key="new_project"):
            # Clear session state to start fresh; workdir_path set to None
            # will trigger a new timestamped run on the next rerun.
            for key in ["phase", "workdir_path", "run_config", "_phase_initialised", "_confirm_back"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # ------------------------------------------------------------------
    # 4. Main area — phase header + body (via phase module router)
    # ------------------------------------------------------------------
    from avideo.ui.pages import (  # noqa: PLC0415 — lazy import; avoids circular issues
        phase_1_contenido,
        phase_2_guion,
        phase_3_slides,
        phase_4_voz,
        phase_5_extras,
        phase_6_ensamble,
    )

    _PHASE_MODULES = {
        1: phase_1_contenido,
        2: phase_2_guion,
        3: phase_3_slides,
        4: phase_4_voz,
        5: phase_5_extras,
        6: phase_6_ensamble,
    }

    current_phase = st.session_state["phase"]
    phase_name = dict(PHASES)[current_phase]
    st.header(f"Fase {current_phase}: {phase_name}")
    st.caption(_PHASE_DESCRIPTIONS[current_phase])

    # Delegate rendering to the current phase module; gate_met gates navigation.
    gate_met: bool = _PHASE_MODULES[current_phase].render(workdir)

    # ------------------------------------------------------------------
    # 5. Navigation footer
    # ------------------------------------------------------------------
    st.divider()
    col_back, col_spacer, col_next = st.columns([1, 4, 1])

    with col_back:
        back_disabled = current_phase == 1
        if st.button("← Atrás", disabled=back_disabled, key="nav_back"):
            st.session_state["_confirm_back"] = True

    # Back-navigation confirmation dialog (shown inline below the footer row)
    if st.session_state.get("_confirm_back"):
        with st.container(border=True):
            prev_phase = current_phase - 1
            invalidation_stage = PHASE_COMPLETION_STAGE.get(prev_phase, "context")
            st.warning(
                f"Volver a la Fase {prev_phase} invalidará el trabajo posterior "
                f"(a partir de la etapa '{invalidation_stage}'). ¿Continuar?"
            )
            c1, c2 = st.columns(2)
            if c1.button("Sí, volver atrás", key="confirm_back_yes"):
                workdir.invalidate_downstream(invalidation_stage)
                st.session_state["phase"] = max(1, prev_phase)
                st.session_state["_confirm_back"] = False
                st.rerun()
            if c2.button("Cancelar", key="confirm_back_no"):
                st.session_state["_confirm_back"] = False
                st.rerun()

    # On the last phase, "Aprobar y continuar" has nothing to advance to
    # (advance_phase() is a no-op once phase == max phase) — Fase 6's own
    # "Finalizar" button is the terminal action instead.
    if current_phase < len(PHASES):
        with col_next:
            if st.button(
                "Aprobar y continuar →",
                disabled=not gate_met,
                type="primary",
                key="nav_next",
            ):
                advance_phase()


# ---------------------------------------------------------------------------
# ----- BRIDGE POLLING EXAMPLE (used by Phases 10–13 for long-running stages) -----
# @st.fragment(run_every="2s")
# def _poll_stage_status(stage_name: str, workdir: WorkdirManager) -> None:
#     """Poll workdir done-marker every 2 s and re-render status."""
#     from avideo.ui.bridge import stage_status, RunStatus
#     status = stage_status(stage_name, workdir)
#     if status == RunStatus.RUNNING:
#         st.spinner(f"Running {stage_name}...")
#     elif status == RunStatus.DONE:
#         st.success(f"{stage_name} complete.")
#         st.rerun()  # exit the auto-rerun fragment loop
#     elif status == RunStatus.ERROR:
#         st.error(f"{stage_name} failed.")
# ---------------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Streamlit runs this script directly on every interaction; calling main() here
# (unconditionally) is the correct Streamlit pattern for a single-file app.
# ---------------------------------------------------------------------------
main()
