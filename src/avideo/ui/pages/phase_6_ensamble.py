"""avideo.ui.pages.phase_6_ensamble — Phase 6: Ensamblaje placeholder.

Real content implemented in Phase 13 of the roadmap.
This placeholder establishes the render(workdir) -> bool contract and
provides a "marcar lista" gate toggle so the wizard navigation works
end-to-end before the content is built.

Phase 13 will replace this body with:
- st.button to trigger assembly stage via PipelineBridge
- @st.fragment(run_every="2s") for live FFmpeg assembly progress
- Final video preview: st.video(str(workdir.root / "output.mp4"))
- st.download_button for the final MP4 download
- Summary card: duration, slide count, voice provider, file size
"""
from __future__ import annotations

import streamlit as st
from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 6 (Ensamblaje) placeholder body.

    Args:
        workdir: Active WorkdirManager for the current run (read-only in placeholder).

    Returns:
        True if the phase gate condition is met (user toggled "marcar lista").
    """
    st.info(
        "**Fase 6 — Ensamblaje** (implementado en Phase 13)\n\n"
        "El contenido de esta fase se construye en la siguiente iteración del roadmap. "
        "Por ahora, activa el toggle de abajo para probar la navegación del wizard."
    )

    # Placeholder preview stub — Phase 13 will populate with final video + download.
    # st.video(str(workdir.root / "output.mp4"), format="video/mp4")
    # st.download_button("Descargar vídeo", data=open(workdir.root / "output.mp4", "rb"), ...)

    gate_met: bool = st.toggle(
        "Marcar esta fase como lista (placeholder)",
        key="gate_phase_6",
        value=False,
    )

    if gate_met:
        st.success("Fase marcada como lista. Puedes continuar.")

    return gate_met
