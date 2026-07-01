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
from avideo.ui.bridge import (
    RunStatus,
    get_error,
    run_stage,
    stage_elapsed,
    stage_status,
)
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

        # Live per-stage progress + stage chaining in one polling fragment.
        _pipeline_progress_and_poll(workdir)

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
        st.markdown("**Pedir variación del guion**")
        variation_target = st.radio(
            "¿Qué quieres cambiar?",
            options=["Afinar tono / redacción", "Cambiar nº de slides / estructura"],
            key="scr_variation_target",
            horizontal=True,
        )
        variation_text = st.text_area(
            "Instrucción (opcional — qué cambiar exactamente)",
            key="scr_variation_text",
            placeholder='Ej: "tono más cercano y sin tecnicismos" / "cambia el número de slides a 4"',
            height=80,
        )
        if st.button("Aplicar variación", key="btn_variation"):
            from avideo.ui.pipeline_ops import rerun_with_feedback  # noqa: PLC0415

            # Clear cached edits so editor repopulates from new script
            if "scr_edited_narrations" in st.session_state:
                del st.session_state["scr_edited_narrations"]

            target_stage = (
                "storyboard"
                if variation_target == "Cambiar nº de slides / estructura"
                else "scriptwriter"
            )
            config = _build_config(workdir)
            rerun_with_feedback(workdir, config, target_stage, variation_text.strip())
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


_PIPELINE_STAGES = [
    ("storyboard", "Storyboard"),
    ("timing", "Timing"),
    ("scriptwriter", "Guion"),
]


@st.fragment(run_every="2s")
def _pipeline_progress_and_poll(workdir: WorkdirManager) -> None:
    """Render live per-stage progress AND drive stage chaining.

    Runs every 2 s. Shows each stage with elapsed time, then triggers a FULL
    app rerun (st.rerun) whenever the pipeline advances — i.e. when no stage is
    currently running but the script is not done yet (so render() launches the
    next pending stage), or when the script is done (so render() shows the
    editor). On any stage error it surfaces the message and stops (no rerun, so
    render() does not re-launch the failed stage in a loop).
    """
    statuses = {name: stage_status(name, workdir) for name, _ in _PIPELINE_STAGES}
    has_error = any(s == RunStatus.ERROR for s in statuses.values())
    all_done = statuses["scriptwriter"] == RunStatus.DONE
    box_state = "error" if has_error else ("complete" if all_done else "running")

    with st.status("Generando guion...", expanded=True, state=box_state):
        for stage_name, label in _PIPELINE_STAGES:
            s = statuses[stage_name]
            if s == RunStatus.DONE:
                st.write(f"✅ {label}")
            elif s == RunStatus.RUNNING:
                elapsed = stage_elapsed(stage_name)
                suffix = f" ({elapsed:.0f}s)" if elapsed is not None else ""
                st.write(f"⏳ Generando {label}...{suffix}")
            elif s == RunStatus.ERROR:
                st.write(f"❌ Error en {label}: {get_error(stage_name)}")
            else:
                st.write(f"⏸ Pendiente: {label}")

    if has_error:
        return  # stop polling; do not re-launch the failed stage
    if all_done:
        st.rerun()  # full app rerun → render() shows the editor
        return
    # Chain still advancing: if nothing is running, the previous stage finished
    # and the next pending one must be launched by a full page rerun.
    running = any(s == RunStatus.RUNNING for s in statuses.values())
    if not running:
        st.rerun()  # full app rerun → render() launches the next pending stage


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
