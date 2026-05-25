"""WorkdirManager — single path authority for all filesystem operations.

Responsibilities:
- Construct all paths (checkpoint JSON, done markers, subdirectories)
- Atomic checkpoint writes via tmp → os.replace (same filesystem, no partial JSON)
- Done-marker lifecycle: is_done / mark_done
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class WorkdirManager:
    """Manages all filesystem state for a pipeline run.

    All components (orchestrator, stages) must obtain paths through this
    manager — never by constructing ``workdir / "something.json"`` directly.

    Atomic write guarantee:
        The tmp file lives in the same directory as the target so that
        ``os.replace(tmp, target)`` is always a same-filesystem rename,
        which is atomic on both POSIX and Windows NTFS.
    """

    def __init__(self, root: Path) -> None:
        """Create workdir root and all required subdirectories.

        Args:
            root: Root directory for this pipeline run (e.g. Path("workdir")).
        """
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        for subdir in ("slides", "audio", "subs", "design_proposal", "slides_user"):
            (root / subdir).mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Path construction
    # ------------------------------------------------------------------

    def checkpoint_path(self, name: str) -> Path:
        """Return the canonical JSON path for a named checkpoint.

        Args:
            name: Stage/checkpoint name, e.g. ``"storyboard"``.

        Returns:
            ``<root>/<name>.json``
        """
        return self.root / f"{name}.json"

    def done_marker(self, stage: str) -> Path:
        """Return the path to the hidden done-marker file for a stage.

        Args:
            stage: Stage name, e.g. ``"storyboard"``.

        Returns:
            ``<root>/.<stage>.done``
        """
        return self.root / f".{stage}.done"

    # ------------------------------------------------------------------
    # Done-marker API
    # ------------------------------------------------------------------

    def is_done(self, stage: str) -> bool:
        """Return True if the done marker for *stage* exists.

        Args:
            stage: Stage name to check.
        """
        return self.done_marker(stage).exists()

    def mark_done(self, stage: str) -> None:
        """Touch the done marker for *stage*.

        Must only be called after ``write_checkpoint`` succeeds.  If the
        checkpoint write fails, this method must NOT be called — doing so
        would incorrectly mark the stage as complete with no valid output.

        Args:
            stage: Stage name to mark as complete.
        """
        self.done_marker(stage).touch()

    # ------------------------------------------------------------------
    # Checkpoint read/write
    # ------------------------------------------------------------------

    def write_checkpoint(self, name: str, model: BaseModel) -> None:
        """Atomically write a Pydantic model as a JSON checkpoint.

        Writes first to a ``.json.tmp`` file in the same directory (same
        filesystem), then calls ``os.replace`` to atomically rename it to
        the final target.  If ``os.replace`` raises, no target file exists
        and no done marker is left.

        Args:
            name: Checkpoint name, e.g. ``"storyboard"``.
            model: The Pydantic model instance to persist.

        Raises:
            OSError: If the tmp write or the atomic replace fails.
        """
        target = self.checkpoint_path(name)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        os.replace(str(tmp), str(target))

    def read_checkpoint(self, name: str, model_class: type[BaseModel]) -> BaseModel:
        """Read and deserialise a JSON checkpoint into a Pydantic model.

        Args:
            name: Checkpoint name, e.g. ``"storyboard"``.
            model_class: The Pydantic ``BaseModel`` subclass to validate against.

        Returns:
            A validated model instance.

        Raises:
            FileNotFoundError: If the checkpoint JSON does not exist.
            pydantic.ValidationError: If the JSON does not match the model.
        """
        path = self.checkpoint_path(name)
        return model_class.model_validate_json(path.read_text(encoding="utf-8"))
