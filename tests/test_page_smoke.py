"""Smoke tests: import all 6 wizard pages without exceptions.

These tests do NOT call render() or any Streamlit API. They only verify that
the module-level code in each page (imports, constants) does not raise when
loaded. Streamlit itself is not exercised — the pages use lazy st.* imports
inside render(), so importlib.import_module succeeds without a running Streamlit
server.

Covered:
  - avideo.ui.pages.phase_1_contenido
  - avideo.ui.pages.phase_2_guion
  - avideo.ui.pages.phase_3_slides
  - avideo.ui.pages.phase_4_voz
  - avideo.ui.pages.phase_5_extras
  - avideo.ui.pages.phase_6_ensamble

NOTE on app.py: st.set_page_config() is called at module scope in app.py,
which raises StreamlitAPIException outside a running Streamlit server.
The smoke test verifies render() exists on each page module; app.py is
verified by the avideo studio CLI smoke test (manual/human verification step).
"""
from __future__ import annotations

import importlib

import pytest

_PAGE_MODULES = [
    "avideo.ui.pages.phase_1_contenido",
    "avideo.ui.pages.phase_2_guion",
    "avideo.ui.pages.phase_3_slides",
    "avideo.ui.pages.phase_4_voz",
    "avideo.ui.pages.phase_5_extras",
    "avideo.ui.pages.phase_6_ensamble",
]


@pytest.mark.parametrize("module_name", _PAGE_MODULES)
def test_page_module_imports_without_exception(module_name: str) -> None:
    """Each page module must be importable without raising any exception.

    render() must be a callable attribute on the module.
    """
    mod = importlib.import_module(module_name)
    assert callable(getattr(mod, "render", None)), (
        f"{module_name} must export a callable render()"
    )


def test_all_six_pages_listed() -> None:
    """Sanity-check: the parametrize list covers exactly 6 pages."""
    assert len(_PAGE_MODULES) == 6
