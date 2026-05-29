"""avideo.ui.pages.phase_1_contenido — Phase 1: Contenido placeholder.

Real content implemented in Phase 10 of the roadmap.
This placeholder establishes the render(workdir) -> bool contract and
provides a "marcar lista" gate toggle so the wizard navigation works
end-to-end before the content is built.

Phase 10 will replace this body with:
- st.file_uploader for bullets.yaml upload (written to workdir immediately)
- st.text_input for topic / st.number_input for duration
- st.expander for optional context document upload (.pptx/.pdf/.md)
- st.image stub preview area for the context document thumbnail
"""
from __future__ import annotations

import streamlit as st
from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 1 (Contenido) placeholder body.

    Args:
        workdir: Active WorkdirManager for the current run (read-only in placeholder).

    Returns:
        True if the phase gate condition is met (user toggled "marcar lista").
    """
    st.info(
        "**Fase 1 — Contenido** (implementado en Phase 10)\n\n"
        "El contenido de esta fase se construye en la siguiente iteración del roadmap. "
        "Por ahora, activa el toggle de abajo para probar la navegación del wizard."
    )

    # Placeholder preview stub — Phase 10 will populate with real content.
    # st.image(workdir.checkpoint_path("context_thumbnail"), caption="Context preview")

    gate_met: bool = st.toggle(
        "Marcar esta fase como lista (placeholder)",
        key="gate_phase_1",
        value=False,
    )

    if gate_met:
        st.success("Fase marcada como lista. Puedes continuar.")

    return gate_met
