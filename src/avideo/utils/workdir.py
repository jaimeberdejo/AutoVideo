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

#: Canonical pipeline stage execution order.
#: Used by ``WorkdirManager.invalidate_downstream`` to determine which
#: done-markers to delete when the user navigates back in the wizard.
STAGE_ORDER: list[str] = [
    "context",
    "storyboard",
    "timing",
    "scriptwriter",
    "slides",
    "verify",
    "voice",
    "align",
    "subs",
    "assemble",
]


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

    def invalidate_downstream(self, from_stage: str) -> list[str]:
        """Delete done-markers for all stages strictly after *from_stage*.

        This is the UI safety mechanism: when the user navigates back and
        edits an upstream stage, all downstream done-markers must be deleted
        so the pipeline does not serve stale results.

        Args:
            from_stage: Stage name boundary (inclusive — this stage's marker
                is NOT deleted; only stages after it in STAGE_ORDER are).

        Returns:
            List of stage names whose done-markers were deleted.

        Raises:
            ValueError: If *from_stage* is not in STAGE_ORDER.
        """
        if from_stage not in STAGE_ORDER:
            raise ValueError(f"Unknown stage: {from_stage!r}")
        boundary = STAGE_ORDER.index(from_stage)
        deleted: list[str] = []
        for stage in STAGE_ORDER[boundary + 1 :]:
            marker = self.done_marker(stage)
            if marker.exists():
                marker.unlink()
                deleted.append(stage)
        return deleted

    # ------------------------------------------------------------------
    # Checkpoint read/write
    # ------------------------------------------------------------------

    def write_checkpoint(self, name: str, model: BaseModel) -> None:
        """Atomically write a Pydantic model as a JSON checkpoint.

        Writes first to a ``.json.tmp`` file in the same directory (same
        filesystem), then calls ``os.replace`` to atomically rename it to
        the final target.  On any ``OSError`` (failed write or failed replace),
        the ``.json.tmp`` file is removed so no stale tmp files accumulate
        across retries or resumes.  The target JSON is never partially written.

        Args:
            name: Checkpoint name, e.g. ``"storyboard"``.
            model: The Pydantic model instance to persist.

        Raises:
            OSError: If the tmp write or the atomic replace fails.
        """
        target = self.checkpoint_path(name)
        tmp = target.with_suffix(".json.tmp")
        try:
            tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
            os.replace(str(tmp), str(target))
        except OSError:
            tmp.unlink(missing_ok=True)
            raise

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

    # ------------------------------------------------------------------
    # Feedback transport (SEED-002: steerable variation)
    # ------------------------------------------------------------------

    def write_feedback(self, stage: str, text: str) -> None:
        """Write (or merge) a feedback entry for *stage* into feedback.json.

        If feedback.json already exists, the new entry is merged (added or
        overwritten); existing entries for other stages are preserved.

        Args:
            stage: Stage name (e.g. ``"scriptwriter"``, ``"storyboard"``, ``"slides"``).
            text:  Free-text instruction from the user.
        """
        from avideo.models.feedback import FeedbackCheckpoint  # noqa: PLC0415

        path = self.root / "feedback.json"
        if path.exists():
            try:
                cp = FeedbackCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                cp = FeedbackCheckpoint()
        else:
            cp = FeedbackCheckpoint()
        cp.entries[stage] = text
        path.write_text(cp.model_dump_json(indent=2), encoding="utf-8")

    def read_feedback(self, stage: str) -> str | None:
        """Return the feedback text for *stage*, or None if absent.

        Returns None (never raises) when feedback.json is missing, malformed,
        or when the stage key is not present — so stage run() methods can call
        this unconditionally without a try/except.

        Args:
            stage: Stage name to look up.

        Returns:
            The stored feedback string, or ``None`` if not present.
        """
        from avideo.models.feedback import FeedbackCheckpoint  # noqa: PLC0415

        path = self.root / "feedback.json"
        if not path.exists():
            return None
        try:
            cp = FeedbackCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            return cp.entries.get(stage)
        except Exception:  # noqa: BLE001
            return None

    def clear_feedback(self, stage: str) -> None:
        """Remove the feedback entry for *stage* (silent no-op if absent).

        Called by each stage at the end of a successful run() so that a future
        resume does not re-apply stale feedback (consumed-once lifecycle).

        Args:
            stage: Stage name whose entry should be removed.
        """
        from avideo.models.feedback import FeedbackCheckpoint  # noqa: PLC0415

        path = self.root / "feedback.json"
        if not path.exists():
            return
        try:
            cp = FeedbackCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            cp.entries.pop(stage, None)
            path.write_text(cp.model_dump_json(indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
