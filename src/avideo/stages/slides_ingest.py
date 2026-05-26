"""slides_ingest — shared ingest helper for hybrid and manual slide modes (SLIDE-05).

Normalizes user-supplied PNG/PDF/PPTX files from workdir/slides_user/ into
1920-wide PNG files in workdir/slides/, so downstream stages (voice, assemble)
receive a uniform list of PNG paths regardless of the source format.

Design decisions:
- PNG: copied verbatim with shutil.copy2 — no rasterization.
- PDF: rasterized via PyMuPDF (fitz) at 1920px width target using zoom matrix.
- PPTX: not supported for offline rasterization — raises RuntimeError with
  export hint (user must export to PDF or PNG manually).
- Unknown extensions: raises ValueError listing SUPPORTED_EXTS.

Security (T-06-01, T-06-03):
- All input paths are expected to already be resolved under workdir.root/slides_user/
  by the caller (SlidesHybridStage, SlidesManualStage) — never accept arbitrary
  absolute paths from user input.
- Suffix validation against SUPPORTED_EXTS happens before any file open/rasterize.
- PPTX rejected fast with RuntimeError before any heavy dependency is invoked.

Mock point: `fitz` is imported at MODULE scope so tests can patch
`avideo.stages.slides_ingest.fitz` without touching the PyMuPDF library.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import fitz  # PyMuPDF — imported at module scope for test patching

logger = logging.getLogger(__name__)

TARGET_WIDTH_PX: int = 1920
"""Target pixel width for PDF rasterization (maintains aspect ratio)."""

SUPPORTED_EXTS: frozenset[str] = frozenset({".png", ".pdf", ".pptx"})
"""File extensions accepted by ingest_slide (suffix validation, T-06-01/T-06-03)."""


def ingest_slide(src: Path, out_png: Path) -> None:
    """Normalize a user-supplied slide file to a PNG at *out_png*.

    Dispatches on file extension:
    - ``.png``: bytes are copied verbatim via :func:`shutil.copy2`.
    - ``.pdf``: page 0 is rasterized to *TARGET_WIDTH_PX* pixels wide using
      PyMuPDF's zoom-matrix approach (``fitz.Page.get_pixmap``).
    - ``.pptx``: offline rasterization is not supported; raises
      :exc:`RuntimeError` with an export hint.
    - Any other extension: raises :exc:`ValueError` listing the supported set.

    Security note (T-06-01, T-06-03):
      The caller is responsible for resolving *src* under the workdir boundary
      (e.g. ``workdir.root / "slides_user" / filename``). This helper only
      validates the file extension before any I/O.

    Args:
        src: Absolute or relative path to the source slide file.
        out_png: Destination path where the output PNG will be written.

    Raises:
        RuntimeError: If *src* is a ``.pptx`` file (not supported offline).
        ValueError: If *src* has an extension not in *SUPPORTED_EXTS*.
    """
    ext = src.suffix.lower()

    if ext == ".png":
        shutil.copy2(src, out_png)

    elif ext == ".pdf":
        # Context manager guarantees the document is closed even if rasterization
        # raises (file-descriptor leak otherwise). Guard against zero-width pages
        # (degenerate/corrupt PDFs) which would raise ZeroDivisionError on zoom.
        with fitz.open(str(src)) as doc:
            page = doc[0]
            if page.rect.width <= 0:
                raise ValueError(
                    f"PDF page has non-positive width ({page.rect.width}): {src!r} "
                    f"— file may be corrupt."
                )
            zoom = TARGET_WIDTH_PX / page.rect.width
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            pix.save(str(out_png))

    elif ext == ".pptx":
        raise RuntimeError(
            f"PPTX rasterization is not supported offline. "
            f"Export '{src.name}' to PDF or PNG and place it in slides_user/. "
            f"(LibreOffice: File > Export as PDF; PowerPoint: Save As > PNG)"
        )

    else:
        raise ValueError(
            f"Unsupported file type: {ext!r}. "
            f"Supported: {sorted(SUPPORTED_EXTS)}"
        )
