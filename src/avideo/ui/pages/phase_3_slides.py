"""avideo.ui.pages.phase_3_slides — Phase 3: Diapositivas placeholder.

Real content implemented in Phase 11 of the roadmap.
This placeholder establishes the render(workdir) -> bool contract and
provides a "marcar lista" gate toggle so the wizard navigation works
end-to-end before the content is built.

Phase 11 will replace this body with:
- st.button to trigger slides generation stage via PipelineBridge
- @st.fragment(run_every="2s") for live slide-render progress
- Slide gallery: st.image per generated slide PNG (workdir/slides/)
- Visual verifier results summary (Claude vision output)
- st.file_uploader stub for manual slide upload (hybrid/manual modes)
"""
from __future__ import annotations

import streamlit as st
from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 3 (Diapositivas) placeholder body.

    Args:
        workdir: Active WorkdirManager for the current run (read-only in placeholder).

    Returns:
        True if the phase gate condition is met (user toggled "marcar lista").
    """
    st.info(
        "**Fase 3 — Diapositivas** (implementado en Phase 11)\n\n"
        "El contenido de esta fase se construye en la siguiente iteración del roadmap. "
        "Por ahora, activa el toggle de abajo para probar la navegación del wizard."
    )

    # Placeholder preview stub — Phase 11 will populate with slide gallery.
    # for slide_path in sorted((workdir.root / "slides").glob("slide_*.png")):
    #     st.image(str(slide_path), caption=slide_path.name)

    gate_met: bool = st.toggle(
        "Marcar esta fase como lista (placeholder)",
        key="gate_phase_3",
        value=False,
    )

    if gate_met:
        st.success("Fase marcada como lista. Puedes continuar.")

    return gate_met
