"""avideo.ui.pages.phase_5_extras — Phase 5: Extras placeholder.

Real content implemented in Phase 13 of the roadmap.
This placeholder establishes the render(workdir) -> bool contract and
provides a "marcar lista" gate toggle so the wizard navigation works
end-to-end before the content is built.

Phase 13 will replace this body with:
- st.toggle for subtitle burning (burn_subs flag)
- st.file_uploader for optional background music (MP3/WAV)
- st.slider for background music volume
- st.selectbox for slide transition style
- Preview: st.video stub area for a short preview clip with subs
"""
from __future__ import annotations

import streamlit as st
from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 5 (Extras) placeholder body.

    Args:
        workdir: Active WorkdirManager for the current run (read-only in placeholder).

    Returns:
        True if the phase gate condition is met (user toggled "marcar lista").
    """
    st.info(
        "**Fase 5 — Extras** (implementado en Phase 13)\n\n"
        "El contenido de esta fase se construye en la siguiente iteración del roadmap. "
        "Por ahora, activa el toggle de abajo para probar la navegación del wizard."
    )

    # Placeholder preview stub — Phase 13 will populate with extras config widgets.
    # st.video(str(workdir.checkpoint_path("preview_clip")), format="video/mp4")

    gate_met: bool = st.toggle(
        "Marcar esta fase como lista (placeholder)",
        key="gate_phase_5",
        value=False,
    )

    if gate_met:
        st.success("Fase marcada como lista. Puedes continuar.")

    return gate_met
