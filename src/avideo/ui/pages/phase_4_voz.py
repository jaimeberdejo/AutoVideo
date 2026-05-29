"""avideo.ui.pages.phase_4_voz — Phase 4: Voz placeholder.

Real content implemented in Phase 12 of the roadmap.
This placeholder establishes the render(workdir) -> bool contract and
provides a "marcar lista" gate toggle so the wizard navigation works
end-to-end before the content is built.

Phase 12 will replace this body with:
- st.selectbox for voice provider (elevenlabs / record)
- st.selectbox for ElevenLabs voice ID
- Per-slide audio preview: st.audio(workdir.root / "audio" / "slide_01.mp3")
- st.button to trigger voice synthesis via PipelineBridge
- @st.fragment(run_every="2s") for live TTS progress
"""
from __future__ import annotations

import streamlit as st
from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 4 (Voz) placeholder body.

    Args:
        workdir: Active WorkdirManager for the current run (read-only in placeholder).

    Returns:
        True if the phase gate condition is met (user toggled "marcar lista").
    """
    st.info(
        "**Fase 4 — Voz** (implementado en Phase 12)\n\n"
        "El contenido de esta fase se construye en la siguiente iteración del roadmap. "
        "Por ahora, activa el toggle de abajo para probar la navegación del wizard."
    )

    # Placeholder preview stub — Phase 12 will populate with audio previews.
    # for audio_path in sorted((workdir.root / "audio").glob("slide_*.mp3")):
    #     st.audio(str(audio_path), format="audio/mp3")

    gate_met: bool = st.toggle(
        "Marcar esta fase como lista (placeholder)",
        key="gate_phase_4",
        value=False,
    )

    if gate_met:
        st.success("Fase marcada como lista. Puedes continuar.")

    return gate_met
