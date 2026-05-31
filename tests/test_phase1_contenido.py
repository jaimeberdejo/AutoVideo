"""Tests for the Fase 1 (Contenido) page helper logic.

Streamlit rendering itself is manual-verify; this covers the pure
``clean_bullet_rows`` helper that extracts bullets from st.data_editor rows.
Regression: blank/never-edited dynamic rows arrive as {"bullet": None} and
previously crashed with AttributeError on None.strip() (found in UAT).
"""
from __future__ import annotations


def test_clean_bullet_rows_handles_none_cells():
    """None-valued cells (blank dynamic rows) must not raise and are dropped."""
    from avideo.ui.pages.phase_1_contenido import clean_bullet_rows  # noqa: PLC0415

    rows = [
        {"bullet": "Primer punto"},
        {"bullet": None},          # blank dynamic row from st.data_editor
        {"bullet": "  Segundo  "},  # whitespace trimmed
        {"bullet": ""},            # empty string dropped
        {},                         # missing key dropped
    ]
    assert clean_bullet_rows(rows) == ["Primer punto", "Segundo"]


def test_clean_bullet_rows_empty():
    """No rows / all-blank rows yield an empty list (not an error)."""
    from avideo.ui.pages.phase_1_contenido import clean_bullet_rows  # noqa: PLC0415

    assert clean_bullet_rows([]) == []
    assert clean_bullet_rows([{"bullet": None}, {"bullet": "   "}]) == []
