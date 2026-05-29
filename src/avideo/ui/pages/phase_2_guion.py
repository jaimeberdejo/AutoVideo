"""avideo.ui.pages.phase_2_guion — Phase 2: Guion wizard page (SCR-01..04).

Implements the full narration-script review loop:
- SCR-01: On entry, if not done, auto-runs storyboard → timing → scriptwriter
  via bridge with per-stage progress (st.status + @st.fragment polling).
- SCR-02: Per-slide editable st.text_area; "Guardar edición" persists via
  pipeline_ops.persist_edited_script (which invalidates downstream).
- SCR-03: "Pedir variación del guion" button calls pipeline_ops.rerun_scriptwriter
  (only scriptwriter, not the whole pipeline).
- SCR-04: "Aprobar guion" marks done → gate returns True.

Public contract: render(workdir: WorkdirManager) -> bool
"""
from __future__ import annotations

import streamlit as st

from avideo.models.config import RunConfig
from avideo.models.script import ScriptOutput, SlideScript
from avideo.ui.bridge import RunStatus, get_error, run_stage, stage_status
from avideo.utils.workdir import WorkdirManager


def _build_config(workdir: WorkdirManager) -> RunConfig:
    """Construct RunConfig from session_state, injecting bullets path if needed."""
    rc_kwargs = dict(st.session_state.get("run_config", {}))
    if "bullets" not in rc_kwargs:
        rc_kwargs["bullets"] = workdir.root / "bullets.yaml"
    return RunConfig(**rc_kwargs)


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 2 (Guion) wizard page.

    Implements SCR-01..04:
    - Auto-runs storyboard, timing, and scriptwriter stages on entry if not done.
    - Displays per-slide narration editors once the script is ready.
    - Provides "Pedir variación" (scriptwriter-only re-run) and "Aprobar guion" gate.

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        True once the user clicks "Aprobar guion" (scriptwriter done-marker present).
    """
    st.header("Fase 2 — Guion")

    storyboard_done = workdir.is_done("storyboard")
    timing_done = workdir.is_done("timing")
    script_done = workdir.is_done("scriptwriter")

    # ------------------------------------------------------------------
    # SCR-01: Auto-run pipeline stages if not yet done
    # ------------------------------------------------------------------
    if not script_done:
        config = _build_config(workdir)

        # Launch next pending stage (idempotent — bridge skips if running/done)
        if not storyboard_done:
            run_stage(__import__("avideo.stages.storyboard", fromlist=["StoryboardStage"]).StoryboardStage(), workdir, config)
        elif not timing_done:
            run_stage(__import__("avideo.stages.timing", fromlist=["TimingStage"]).TimingStage(), workdir, config)
        else:
            run_stage(__import__("avideo.stages.scriptwriter", fromlist=["ScriptwriterStage"]).ScriptwriterStage(), workdir, config)

        # Show per-stage progress
        _show_pipeline_progress(workdir)

        # Poll until scriptwriter done, then trigger a full rerun
        _poll_script_generation(workdir)

        # Gate not yet met
        return False

    # ------------------------------------------------------------------
    # Script is done — show editor (SCR-02)
    # ------------------------------------------------------------------
    script: ScriptOutput = workdir.read_checkpoint("script", ScriptOutput)  # type: ignore[assignment]

    # Cache per-slide narrations in session_state (survives Streamlit reruns)
    if "scr_edited_narrations" not in st.session_state:
        st.session_state["scr_edited_narrations"] = {
            s.slide_index: s.narration for s in script.slides
        }

    st.subheader("Revisa y edita el guion")

    for slide in script.slides:
        idx = slide.slide_index
        st.markdown(f"**Slide {idx + 1}**")
        edited = st.text_area(
            f"Narración slide {idx + 1}",
            value=st.session_state["scr_edited_narrations"].get(idx, slide.narration),
            key=f"narration_{idx}",
            height=120,
        )
        # Update cache with latest widget value
        st.session_state["scr_edited_narrations"][idx] = edited

        col_save, _ = st.columns([1, 4])
        with col_save:
            if st.button(f"Guardar edición slide {idx + 1}", key=f"save_{idx}"):
                _save_edited_script(workdir, script)
                st.success("Guion guardado. Etapas posteriores invalidadas.")
                st.rerun()

        st.divider()

    # ------------------------------------------------------------------
    # SCR-03: Variation button — re-runs scriptwriter only
    # ------------------------------------------------------------------
    st.markdown("---")
    col_var, col_approve = st.columns([1, 1])

    with col_var:
        if st.button("Pedir variacion del guion", key="btn_variation"):
            from avideo.ui.pipeline_ops import rerun_scriptwriter  # noqa: PLC0415

            # Clear cached edits so editor repopulates from new script
            if "scr_edited_narrations" in st.session_state:
                del st.session_state["scr_edited_narrations"]
            config = _build_config(workdir)
            rerun_scriptwriter(workdir, config)
            st.rerun()

    # ------------------------------------------------------------------
    # SCR-04: Approval gate
    # ------------------------------------------------------------------
    with col_approve:
        if st.button("Aprobar guion", key="btn_approve_script", type="primary"):
            # Persist any in-editor edits as the approved checkpoint
            _save_edited_script(workdir, script)
            # Done-marker already set by bridge; mark again (idempotent)
            workdir.mark_done("scriptwriter")
            st.success("Guion aprobado.")
            st.rerun()

    # Gate is met when scriptwriter done-marker is present (set above or by bridge)
    return workdir.is_done("scriptwriter")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _show_pipeline_progress(workdir: WorkdirManager) -> None:
    """Render a st.status box with the current per-stage status."""
    s_storyboard = stage_status("storyboard", workdir)
    s_timing = stage_status("timing", workdir)
    s_script = stage_status("scriptwriter", workdir)

    all_done = s_script == RunStatus.DONE
    box_state = "complete" if all_done else "running"

    with st.status("Generando guion...", expanded=True, state=box_state):
        for stage_name, label, s in [
            ("storyboard", "Storyboard", s_storyboard),
            ("timing", "Timing", s_timing),
            ("scriptwriter", "Guion", s_script),
        ]:
            if s == RunStatus.DONE:
                st.write(f"Listo: {label}")
            elif s == RunStatus.RUNNING:
                st.write(f"Generando {label}...")
            elif s == RunStatus.ERROR:
                err = get_error(stage_name)
                st.write(f"Error en {label}: {err}")
            else:
                st.write(f"Pendiente: {label}")


@st.fragment(run_every="2s")
def _poll_script_generation(workdir: WorkdirManager) -> None:
    """Poll scriptwriter status every 2 s; trigger full rerun once done or on error."""
    s = stage_status("scriptwriter", workdir)
    if s == RunStatus.DONE:
        st.rerun()
    elif s == RunStatus.ERROR:
        err = get_error("scriptwriter")
        st.error(f"Error generando guion: {err}")


def _save_edited_script(workdir: WorkdirManager, base_script: ScriptOutput) -> None:
    """Persist current session_state edits to workdir and invalidate downstream."""
    from avideo.ui.pipeline_ops import persist_edited_script  # noqa: PLC0415

    narrations: dict[int, str] = st.session_state.get("scr_edited_narrations", {})
    if not narrations:
        return

    updated_slides = [
        SlideScript(slide_index=i, narration=narrations[i])
        for i in sorted(narrations.keys())
    ]
    updated_script = ScriptOutput(
        slides=updated_slides,
        language=base_script.language,
    )
    persist_edited_script(workdir, updated_script)
