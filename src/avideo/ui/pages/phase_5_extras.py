"""avideo.ui.pages.phase_5_extras — Phase 5: Extras (EXT-01).

Replaces the Phase 9 placeholder with the real Fase 5 wizard page.

Implements EXT-01:
  - st.toggle for subtitle burning (burn_subs flag)
  - st.file_uploader for optional background music (MP3/WAV) + st.audio preview
  - st.slider for background music volume and fade-out duration
  - st.slider for crossfade between slides
  - Immediate approve gate (config-only page, no long stage)
  - Approving with no extras selected is VALID

On approval, all widget values are merged into session_state["run_config"]
via extras_to_run_config so downstream stages see the correct RunConfig kwargs.
"""
from __future__ import annotations

import streamlit as st

from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 5 (Extras) wizard body.

    Implements EXT-01: subtitle burning, background music upload + volume,
    crossfade slider, and an immediate config-approval gate.

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        True when the user has clicked "Aprobar extras y continuar".
    """
    from pathlib import Path  # noqa: PLC0415

    # ------------------------------------------------------------------
    # Build RunConfig dict from session state
    # ------------------------------------------------------------------
    rc_dict = dict(st.session_state.get("run_config", {}))
    if "bullets" not in rc_dict:
        rc_dict["bullets"] = workdir.root / "bullets.yaml"

    # ------------------------------------------------------------------
    # SECTION: Subtítulos
    # ------------------------------------------------------------------
    st.subheader("Subtítulos")
    burn_subs = st.toggle(
        "Quemar subtítulos en el vídeo",
        key="ext_burn_subs",
        value=bool(rc_dict.get("burn_subs", False)),
    )
    if burn_subs:
        st.info("Los subtítulos se quemarán permanentemente en el vídeo.")

    # ------------------------------------------------------------------
    # SECTION: Música de fondo
    # ------------------------------------------------------------------
    st.subheader("Música de fondo")

    uploaded_music = st.file_uploader(
        "Sube una pista de música (MP3/WAV)",
        key="ext_music_upload",
        type=["mp3", "wav"],
    )

    if uploaded_music is not None:
        suffix = Path(uploaded_music.name).suffix or ".mp3"
        filename = f"bg_music{suffix}"
        try:
            from avideo.ui.pipeline_ops import write_uploaded_music  # noqa: PLC0415

            music_path = write_uploaded_music(workdir, filename, uploaded_music.read())
            rc_dict["bg_music_path"] = str(music_path)
            st.success(f"Música subida: {uploaded_music.name}")
        except ValueError as exc:
            st.error(f"Archivo rechazado: {exc}")

    # Show st.audio preview if music file exists on disk
    music_on_disk_str = rc_dict.get("bg_music_path")
    if music_on_disk_str is not None and Path(str(music_on_disk_str)).exists():
        st.audio(str(music_on_disk_str), format="audio/mp3")

    bg_music_volume = st.slider(
        "Volumen de la música",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        value=float(rc_dict.get("bg_music_volume", 0.12)),
        key="ext_music_volume",
        help="0 = silencio, 1 = volumen máximo. 0.12 (~-18 dBFS) recomendado.",
    )

    bg_music_fade_out_s = st.slider(
        "Fundido final de la música (segundos)",
        min_value=0.0,
        max_value=10.0,
        step=0.5,
        value=float(rc_dict.get("bg_music_fade_out_s", 3.0)),
        key="ext_music_fade",
    )

    # ------------------------------------------------------------------
    # SECTION: Transiciones
    # ------------------------------------------------------------------
    st.subheader("Transiciones")

    crossfade_seconds = st.slider(
        "Crossfade entre diapositivas (segundos)",
        min_value=0.0,
        max_value=3.0,
        step=0.1,
        value=float(rc_dict.get("crossfade_seconds", 0.5)),
        key="ext_crossfade",
        help="0 = corte duro, 0.5 = suave por defecto.",
    )

    # ------------------------------------------------------------------
    # Resolve bg_music_path as Optional[Path]
    # ------------------------------------------------------------------
    bg_music_path_val = (
        Path(str(rc_dict["bg_music_path"])) if rc_dict.get("bg_music_path") else None
    )

    # ------------------------------------------------------------------
    # Build extras kwargs and merge into rc_dict
    # ------------------------------------------------------------------
    from avideo.ui.pipeline_ops import extras_to_run_config  # noqa: PLC0415

    extras_kwargs = extras_to_run_config(
        burn_subs=burn_subs,
        bg_music_path=bg_music_path_val,
        bg_music_volume=bg_music_volume,
        bg_music_fade_out_s=bg_music_fade_out_s,
        crossfade_seconds=crossfade_seconds,
    )

    # Serialize Path values to str for safe storage in session_state
    rc_dict.update(
        {k: (str(v) if isinstance(v, Path) else v) for k, v in extras_kwargs.items()}
    )
    st.session_state["run_config"] = rc_dict

    # ------------------------------------------------------------------
    # Gate — immediate (config-only, no stage to run)
    # ------------------------------------------------------------------
    st.divider()
    if not music_on_disk_str and not burn_subs:
        st.info("Los extras son opcionales. Puedes continuar sin seleccionar ninguno.")

    gate_met = st.session_state.get("extras_approved", False)

    if st.button(
        "Aprobar extras y continuar",
        key="btn_approve_extras",
        type="primary",
    ):
        st.session_state["extras_approved"] = True
        gate_met = True
        st.rerun()

    return gate_met
