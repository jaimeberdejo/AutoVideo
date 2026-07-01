"""avideo.ui.pages.phase_6_ensamble — Phase 6: Ensamblaje (ASM-01 / ASM-02).

Implements the final wizard page:
- ASM-01: "Montar vídeo" button launches SubtitlesStage (if burn_subs) + AssembleStage
  via PipelineBridge in a background thread; @st.fragment(run_every="2s") polls
  done-markers without blocking the UI.
- ASM-02: On completion, st.video(output.mp4) player + st.download_button for the
  final MP4 + QA report rendered as st.metric widgets (duration deviation + LUFS).
- Gate "Finalizar" is the terminal phase gate — enabled only when assemble.done exists.

render(workdir) -> bool returns True when and only when workdir.is_done("assemble").
"""
from __future__ import annotations

import streamlit as st

from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 6 (Ensamblaje) wizard body.

    Implements ASM-01 (non-blocking assembly via PipelineBridge with live progress)
    and ASM-02 (video player + download button + QA report metrics).

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        True when and only when the assemble done-marker exists.
    """
    # ------------------------------------------------------------------
    # Build RunConfig from session state (mirrors phase_4_voz.py pattern)
    # ------------------------------------------------------------------
    rc_dict = dict(st.session_state.get("run_config", {}))
    if "bullets" not in rc_dict:
        rc_dict["bullets"] = workdir.root / "bullets.yaml"

    from avideo.models.config import RunConfig  # noqa: PLC0415

    try:
        config = RunConfig(**rc_dict)
    except Exception as exc:  # noqa: BLE001
        # No silent fallback here: assembling against a made-up duration would
        # produce a wrong-length video with no indication anything was off.
        st.error(
            f"Error de configuración: {exc}\n\n"
            "Vuelve a la Fase 1 y aprueba de nuevo el tema/duración."
        )
        return False

    # ------------------------------------------------------------------
    # Check assembly done marker
    # ------------------------------------------------------------------
    assemble_done = workdir.is_done("assemble")

    # ------------------------------------------------------------------
    # SECTION: Montar vídeo (ASM-01)
    # ------------------------------------------------------------------
    from avideo.ui.bridge import RunStatus, stage_status  # noqa: PLC0415

    s_assemble = stage_status("assemble", workdir)
    btn_disabled = s_assemble == RunStatus.RUNNING

    if st.button(
        "Montar vídeo",
        key="btn_assemble",
        disabled=btn_disabled,
        type="primary",
    ):
        # If burn_subs is enabled, launch SubtitlesStage first (idempotent).
        # run_stage checks done-markers so duplicate calls are safe.
        if config.burn_subs:
            from avideo.stages.subtitles import SubtitlesStage  # noqa: PLC0415
            from avideo.ui.bridge import run_stage  # noqa: PLC0415

            workdir.done_marker("subs").unlink(missing_ok=True)
            workdir.invalidate_downstream("subs")
            run_stage(SubtitlesStage(), workdir, config)

        from avideo.stages.assemble import AssembleStage  # noqa: PLC0415
        from avideo.ui.bridge import run_stage as _run_stage  # noqa: PLC0415

        workdir.done_marker("assemble").unlink(missing_ok=True)
        workdir.invalidate_downstream("assemble")
        st.session_state.pop("_assemble_error_rerun_done", None)
        _run_stage(AssembleStage(), workdir, config)
        st.rerun()

    # ------------------------------------------------------------------
    # SECTION: Progress polling (ASM-01 — non-blocking)
    # ------------------------------------------------------------------
    if not assemble_done:

        @st.fragment(run_every="2s")
        def _poll_assemble() -> None:
            from avideo.ui.bridge import RunStatus, format_stage_error, stage_status  # noqa: PLC0415

            sa = stage_status("assemble", workdir)
            if sa == RunStatus.ERROR:
                st.error(f"Error en el montaje: {format_stage_error('assemble')}")
                # Same fix as phase_4_voz.py: "Montar vídeo"'s disabled= value
                # was frozen at the last full rerun (while RUNNING) — force one
                # more full rerun so the button re-enables for a retry.
                if not st.session_state.get("_assemble_error_rerun_done"):
                    st.session_state["_assemble_error_rerun_done"] = True
                    st.rerun()
            elif sa == RunStatus.RUNNING:
                with st.status("Montando vídeo...", expanded=True):
                    st.info("FFmpeg está procesando. La UI seguirá respondiendo.")
            elif sa == RunStatus.IDLE:
                st.info("Pulsa 'Montar vídeo' para comenzar el ensamblaje.")
            elif sa == RunStatus.DONE:
                st.rerun()

        _poll_assemble()
        return False

    # ------------------------------------------------------------------
    # SECTION: Video player + download (ASM-02)
    # ------------------------------------------------------------------
    output_mp4 = workdir.root / "output.mp4"
    if output_mp4.exists():
        st.subheader("Vídeo final")
        st.video(str(output_mp4))
        with open(output_mp4, "rb") as f:
            st.download_button(
                label="Descargar output.mp4",
                data=f,
                file_name="output.mp4",
                mime="video/mp4",
                key="btn_download_video",
                type="primary",
            )
    else:
        st.warning(
            "output.mp4 no encontrado. Pulsa 'Montar vídeo' para generar el vídeo."
        )

    # ------------------------------------------------------------------
    # SECTION: Informe QA (ASM-02)
    # ------------------------------------------------------------------
    from avideo.ui.pipeline_ops import read_qa_report  # noqa: PLC0415

    qa = read_qa_report(workdir)
    if qa is not None:
        st.subheader("Informe QA")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Duración real (s)", f"{qa.actual_seconds:.1f}")
        with col2:
            delta_sign = "+" if qa.duration_deviation >= 0 else ""
            st.metric(
                "Desviación (s)",
                f"{delta_sign}{qa.duration_deviation:.1f}",
                delta=f"{delta_sign}{qa.duration_deviation:.1f}",
            )
        with col3:
            if qa.normalized_lufs is not None:
                st.metric("LUFS normalizados", f"{qa.normalized_lufs:.1f} LUFS")
            elif qa.measured_lufs is not None:
                st.metric("LUFS medidos", f"{qa.measured_lufs:.1f} LUFS")
    elif assemble_done:
        st.info("qa_report.json no disponible.")

    # ------------------------------------------------------------------
    # Gate — Finalizar (terminal phase)
    # ------------------------------------------------------------------
    st.divider()
    if st.button(
        "Finalizar",
        key="btn_finalizar",
        type="primary",
        disabled=not assemble_done,
    ):
        st.success("Proyecto completado. El vídeo está listo.")
        st.balloons()

    return assemble_done
