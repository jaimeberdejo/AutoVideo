"""Shared loader for bullets.yaml input files.

Provides a single entry point — load_bullets() — used by:
- stages/storyboard.py (consumes title + bullets list for LLM prompt)
- utils/cost_estimator.py (uses bullet count for dry-run token heuristic)
"""
from __future__ import annotations

from pathlib import Path

import yaml

from avideo.models.bullets import BulletsInput


def load_bullets(path: Path) -> BulletsInput:
    """Read a bullets.yaml file and return a validated BulletsInput model.

    Uses yaml.safe_load (no arbitrary object construction) and validates the
    resulting dict with Pydantic, surfacing missing/invalid fields as a clear
    ValidationError.

    Args:
        path: Path to a YAML file with 'title' and 'bullets' keys.

    Returns:
        A validated BulletsInput instance.

    Raises:
        pydantic.ValidationError: If required keys are missing or have wrong types.
        yaml.YAMLError: If the file is not valid YAML.
        OSError: If the file cannot be read.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return BulletsInput.model_validate(raw)
