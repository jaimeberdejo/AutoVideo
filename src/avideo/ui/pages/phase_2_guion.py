"""avideo.ui.pages.phase_2_guion — Phase 2: Guion + Slides placeholder.

Real content implemented in Phase 11 of the roadmap.
This placeholder establishes the render(workdir) -> bool contract and
provides a "marcar lista" gate toggle so the wizard navigation works
end-to-end before the content is built.

Phase 11 will replace this body with:
- st.button to trigger scriptwriter stage via PipelineBridge
- st.status + @st.fragment(run_every="2s") for live stage progress
- Per-slide script editor (st.text_area for each slide's narration)
- st.image stub preview area for slide thumbnails alongside the script
"""
from __future__ import annotations

import streamlit as st
from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 2 (Guion + Slides) placeholder body.

    Args:
        workdir: Active WorkdirManager for the current run (read-only in placeholder).

    Returns:
        True if the phase gate condition is met (user toggled "marcar lista").
    """
    st.info(
        "**Fase 2 — Guion + Slides** (implementado en Phase 11)\n\n"
        "El contenido de esta fase se construye en la siguiente iteración del roadmap. "
        "Por ahora, activa el toggle de abajo para probar la navegación del wizard."
    )

    # Placeholder preview stub — Phase 11 will populate with real script editor.
    # st.image(workdir.checkpoint_path("slides") / "slide_01.png", caption="Slide 1 preview")

    gate_met: bool = st.toggle(
        "Marcar esta fase como lista (placeholder)",
        key="gate_phase_2",
        value=False,
    )

    if gate_met:
        st.success("Fase marcada como lista. Puedes continuar.")

    return gate_met
