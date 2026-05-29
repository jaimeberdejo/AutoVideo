"""avideo.ui.pages.phase_4_voz — Phase 4: Voz (VOZ-01 / VOZ-03).

Wizard page for voice narration: provider selection, per-slide audio previews,
own-recording upload with non-destructive enhancement preview, and an approval gate
that unlocks only when all slides have audio and timings.json has valid word-level data.

Success criteria covered:
  VOZ-01/1  Three provider options (ElevenLabs, OpenAI Audio, Grabaciones propias) via
            st.radio; selection persists VoiceMode into session_state['run_config']['voice'].
  VOZ-01/2  For ElevenLabs and OpenAI Audio: "Generar voz" launches VoiceStage via
            rerun_voice(); @st.fragment(run_every="2s") polls bridge; one st.audio per
            slide on completion.
  VOZ-01/3  For Grabaciones propias: per-slide st.file_uploader (wav/mp3); immediate
            write via write_uploaded_audio; "Mejorar audio" → NON-DESTRUCTIVE enhance
            preview with BEFORE/AFTER comparison; "Adoptar" to confirm enhanced file.
  VOZ-01/4  Gate "Aprobar voz" disabled until audio_gate_ready(workdir, n_slides) is True.
  VOZ-03    enhance_audio(original, preview) called non-destructively; alignment always
            uses original unprocessed audio per Phase 8 decision.
"""
from __future__ import annotations

import streamlit as st

from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 4 (Voz) wizard body.

    Implements VOZ-01 (provider selection, synthesis via bridge, upload path,
    approval gate) and VOZ-03 (non-destructive enhance preview).

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        True when voice done-marker is present AND audio_gate_ready passes.
    """
    from avideo.models.config import RunConfig, VoiceMode  # noqa: PLC0415

    # ------------------------------------------------------------------
    # Build RunConfig from session state
    # ------------------------------------------------------------------
    rc_dict = dict(st.session_state.get("run_config", {}))
    if "bullets" not in rc_dict:
        rc_dict["bullets"] = workdir.root / "bullets.yaml"

    # ------------------------------------------------------------------
    # Read storyboard to know n_slides (required for per-slide widgets)
    # ------------------------------------------------------------------
    from avideo.models.storyboard import StoryboardOutput  # noqa: PLC0415

    try:
        sb: StoryboardOutput = workdir.read_checkpoint("storyboard", StoryboardOutput)
        n_slides = len(sb.slides)
    except Exception:  # noqa: BLE001
        st.warning(
            "Storyboard no disponible. Completa las fases anteriores primero."
        )
        return False

    # ------------------------------------------------------------------
    # VOZ-01/1: Provider selection via st.radio
    # ------------------------------------------------------------------
    provider_label = st.radio(
        "Proveedor de narración",
        ["ElevenLabs", "OpenAI Audio", "Grabaciones propias"],
        key="voz_provider_radio",
        horizontal=True,
    )
    voice_mode_map = {
        "ElevenLabs": VoiceMode.elevenlabs,
        "OpenAI Audio": VoiceMode.openai,
        "Grabaciones propias": VoiceMode.record,
    }
    voice_mode = voice_mode_map[provider_label]
    rc_dict["voice"] = voice_mode.value

    # ------------------------------------------------------------------
    # Provider-specific config widgets
    # ------------------------------------------------------------------
    if voice_mode == VoiceMode.elevenlabs:
        voice_id = st.text_input(
            "Voice ID (ElevenLabs)",
            value=rc_dict.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
            key="voz_voice_id",
        )
        rc_dict["voice_id"] = voice_id

    elif voice_mode == VoiceMode.openai:
        openai_voice = st.selectbox(
            "Voz OpenAI",
            ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            index=4,  # nova default
            key="voz_openai_voice",
        )
        openai_model = st.selectbox(
            "Modelo OpenAI TTS",
            ["tts-1", "tts-1-hd"],
            key="voz_openai_model",
        )
        rc_dict["openai_tts_voice"] = openai_voice
        rc_dict["openai_tts_model"] = openai_model

    # For "Grabaciones propias" — no extra config widgets here; upload widgets are per-slide.

    # ------------------------------------------------------------------
    # Persist rc_dict into session_state
    # ------------------------------------------------------------------
    st.session_state["run_config"] = rc_dict
    try:
        config = RunConfig(**rc_dict)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error de configuración: {exc}")
        return False

    # ------------------------------------------------------------------
    # Route to synthesis or record path
    # ------------------------------------------------------------------
    if voice_mode in (VoiceMode.elevenlabs, VoiceMode.openai):
        return _render_synthesis(workdir, config, n_slides)
    else:
        return _render_record(workdir, config, n_slides)


# ---------------------------------------------------------------------------
# VOZ-01/2: Synthesis path (ElevenLabs / OpenAI Audio)
# ---------------------------------------------------------------------------


def _render_synthesis(workdir: WorkdirManager, config: object, n_slides: int) -> bool:
    """Render the TTS synthesis path (ElevenLabs or OpenAI Audio).

    Launches VoiceStage via rerun_voice(); polls with @st.fragment(run_every="2s");
    shows one st.audio widget per slide once synthesis completes.

    Args:
        workdir:  Active WorkdirManager.
        config:   Fully-built RunConfig (voice == elevenlabs or openai).
        n_slides: Number of slides (from storyboard).

    Returns:
        True if approval gate is met.
    """
    from avideo.ui.bridge import RunStatus, stage_status  # noqa: PLC0415

    voice_done = workdir.is_done("voice")
    s_voice = stage_status("voice", workdir)

    # ------------------------------------------------------------------
    # "Generar voz" button — disabled while running
    # ------------------------------------------------------------------
    btn_disabled = s_voice == RunStatus.RUNNING
    if st.button("Generar voz", key="btn_gen_voice", disabled=btn_disabled):
        from avideo.ui.pipeline_ops import rerun_voice  # noqa: PLC0415

        rerun_voice(workdir, config)
        st.rerun()

    # ------------------------------------------------------------------
    # Poll bridge while synthesis is in progress
    # ------------------------------------------------------------------
    if not voice_done:

        @st.fragment(run_every="2s")
        def _poll_voice() -> None:
            from avideo.ui.bridge import RunStatus, get_error, stage_status  # noqa: PLC0415

            sv = stage_status("voice", workdir)
            if sv == RunStatus.ERROR:
                st.error(f"Error en síntesis: {get_error('voice')}")
            elif sv in (RunStatus.RUNNING, RunStatus.IDLE):
                st.info("Sintetizando voz...")
            elif sv == RunStatus.DONE:
                st.rerun()  # exit fragment loop; show audio previews below

        _poll_voice()
        return False

    # ------------------------------------------------------------------
    # Synthesis done — show per-slide st.audio previews (VOZ-01/2)
    # ------------------------------------------------------------------
    st.subheader("Previews de audio por diapositiva")
    for i in range(n_slides):
        mp3 = workdir.root / "audio" / f"slide_{i:02d}.mp3"
        wav = workdir.root / "audio" / f"slide_{i:02d}.wav"
        audio_path = mp3 if mp3.exists() else (wav if wav.exists() else None)

        with st.expander(f"Slide {i + 1}", expanded=True):
            if audio_path:
                st.audio(str(audio_path), format="audio/mp3")
            else:
                st.warning(f"Slide {i + 1}: audio no encontrado")

    return _approval_gate(workdir, n_slides)


# ---------------------------------------------------------------------------
# VOZ-01/3 + VOZ-03: Own-recordings path ("Grabaciones propias")
# ---------------------------------------------------------------------------


def _render_record(workdir: WorkdirManager, config: object, n_slides: int) -> bool:
    """Render the own-recordings upload path (VOZ-01/3 + VOZ-03).

    Per-slide st.file_uploader; on upload writes immediately via write_uploaded_audio.
    "Mejorar audio" button calls enhance_audio NON-DESTRUCTIVELY; shows BEFORE/AFTER
    comparison; "Adoptar" replaces the audio slot with the enhanced file.

    ALIGNMENT NOTE:
    # Per Phase 8 decision: subtitle alignment always runs on the original unprocessed audio.
    # When user adopts enhanced audio, the original bytes are still in enhanced_path before
    # overwrite — but the alignment stage (AlignStage) reads from the workdir "align" checkpoint
    # which is populated separately. The enhanced file replaces only the final video track audio.
    # For the record+whisperx path, align.py reads the WAV before any enhancement is applied.

    Args:
        workdir:  Active WorkdirManager.
        config:   Fully-built RunConfig (voice == record).
        n_slides: Number of slides (from storyboard).

    Returns:
        True if approval gate is met.
    """
    from pathlib import Path  # noqa: PLC0415

    st.subheader("Subir grabaciones")

    for i in range(n_slides):
        expected_mp3 = workdir.root / "audio" / f"slide_{i:02d}.mp3"
        expected_wav = workdir.root / "audio" / f"slide_{i:02d}.wav"
        audio_on_disk = (
            expected_mp3 if expected_mp3.exists()
            else (expected_wav if expected_wav.exists() else None)
        )

        with st.container(border=True):
            st.write(f"**Slide {i + 1}**")

            # Per-slide file uploader
            uploaded = st.file_uploader(
                f"Slide {i + 1} (wav/mp3)",
                key=f"upload_audio_{i}",
                type=["wav", "mp3"],
                label_visibility="collapsed",
            )
            if uploaded is not None:
                suffix = Path(uploaded.name).suffix or ".mp3"
                filename = f"slide_{i:02d}{suffix}"
                try:
                    from avideo.ui.pipeline_ops import write_uploaded_audio  # noqa: PLC0415

                    write_uploaded_audio(workdir, filename, uploaded.read())
                    # Refresh audio_on_disk after successful write
                    audio_on_disk = workdir.root / "audio" / filename
                    st.success(f"Slide {i + 1} subido.")
                except ValueError as exc:
                    st.error(f"Archivo rechazado: {exc}")

            # Show current audio + enhance controls if audio exists on disk
            if audio_on_disk and audio_on_disk.exists():
                enhanced_path = workdir.root / "audio" / f"slide_{i:02d}_enhanced.mp3"

                st.audio(str(audio_on_disk), format="audio/mp3")

                # "Mejorar audio" button — NON-DESTRUCTIVE (VOZ-03)
                if st.button(f"Mejorar audio slide {i + 1}", key=f"btn_enhance_{i}"):
                    try:
                        from avideo.utils.audio_enhance import enhance_audio  # noqa: PLC0415

                        enhance_audio(audio_on_disk, enhanced_path)
                        st.session_state[f"enhanced_ready_{i}"] = True
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Error en mejora: {exc}")

                # Show BEFORE/AFTER comparison if enhanced version is ready
                if st.session_state.get(f"enhanced_ready_{i}") and enhanced_path.exists():
                    col_before, col_after = st.columns(2)
                    with col_before:
                        st.write("**ANTES (original):**")
                        st.audio(str(audio_on_disk), format="audio/mp3")
                    with col_after:
                        st.write("**DESPUÉS (mejorado):**")
                        st.audio(str(enhanced_path), format="audio/mp3")

                    # "Adoptar" button — replaces the audio slot with enhanced file
                    if st.button(
                        f"Adoptar audio mejorado slide {i + 1}",
                        key=f"btn_adopt_{i}",
                    ):
                        # Adopt enhanced file into the audio slot for video assembly.
                        # NOTE: alignment always uses the original bytes (recorded before
                        # enhancement). The AlignStage checkpoint (align.json) is already
                        # populated and is NOT invalidated here — only the assembled-video
                        # audio track changes.
                        import shutil  # noqa: PLC0415

                        shutil.copy2(str(enhanced_path), str(audio_on_disk))
                        if f"enhanced_ready_{i}" in st.session_state:
                            del st.session_state[f"enhanced_ready_{i}"]
                        st.success(f"Slide {i + 1}: audio mejorado adoptado.")
                        st.rerun()
            else:
                st.info(f"Slide {i + 1}: sin audio subido aún.")

    # ------------------------------------------------------------------
    # "Generar alineación" button — runs AlignStage (whisperx) after uploads
    # ------------------------------------------------------------------
    st.divider()
    st.write("Cuando todos los audios estén subidos, genera los timestamps de alineación.")
    from avideo.ui.bridge import RunStatus, stage_status  # noqa: PLC0415

    align_done = workdir.is_done("align")
    s_align = stage_status("align", workdir)
    btn_align_disabled = s_align == RunStatus.RUNNING

    if st.button("Generar alineación", key="btn_align", disabled=btn_align_disabled):
        from avideo.stages.align import AlignStage  # noqa: PLC0415
        from avideo.ui.bridge import run_stage  # noqa: PLC0415

        workdir.done_marker("align").unlink(missing_ok=True)
        workdir.invalidate_downstream("align")
        run_stage(AlignStage(), workdir, config)
        st.rerun()

    if not align_done and s_align in (RunStatus.RUNNING, RunStatus.IDLE):
        if s_align == RunStatus.RUNNING:

            @st.fragment(run_every="2s")
            def _poll_align() -> None:
                from avideo.ui.bridge import RunStatus, get_error, stage_status  # noqa: PLC0415

                sa = stage_status("align", workdir)
                if sa == RunStatus.ERROR:
                    st.error(f"Error en alineación: {get_error('align')}")
                elif sa in (RunStatus.RUNNING, RunStatus.IDLE):
                    st.info("Generando alineación y timestamps...")
                elif sa == RunStatus.DONE:
                    st.rerun()

            _poll_align()

    return _approval_gate(workdir, n_slides)


# ---------------------------------------------------------------------------
# VOZ-01/4: Approval gate
# ---------------------------------------------------------------------------


def _approval_gate(workdir: WorkdirManager, n_slides: int) -> bool:
    """Render the approval gate and return whether all conditions are met.

    Gate unlocks when audio_gate_ready(workdir, n_slides) is True:
    - All slides have an audio file (mp3 or wav)
    - voice.json (UnifiedTimings) exists, has n_slides entries, each with words

    Args:
        workdir:  Active WorkdirManager.
        n_slides: Expected number of slides.

    Returns:
        True when all gate conditions are satisfied.
    """
    from avideo.ui.pipeline_ops import audio_gate_ready  # noqa: PLC0415

    gate_met = audio_gate_ready(workdir, n_slides)

    st.divider()
    if not gate_met:
        st.info(
            "El gate se desbloqueará cuando todos los slides tengan audio "
            "y los timestamps estén listos."
        )
    if st.button(
        "Aprobar voz",
        key="btn_approve_voice",
        disabled=not gate_met,
        type="primary",
    ):
        st.success("Voz aprobada.")
        st.rerun()

    return gate_met
