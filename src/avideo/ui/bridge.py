"""avideo.ui.bridge — PipelineBridge: background-thread stage execution.

Design invariants (enforced by this module):
1. Background threads NEVER call st.* APIs — all output goes to workdir/.
2. run_stage() is idempotent: calling it when a stage is already running or
   done is a no-op.
3. _threads and _errors are module-level dicts that persist across Streamlit
   reruns (Streamlit re-imports don't clear module state).
4. Threads are daemon=True so they die when the Streamlit process exits.
"""
from __future__ import annotations

import threading
import time
from enum import Enum
from typing import TYPE_CHECKING

from avideo.utils.workdir import WorkdirManager

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.stages.base import StageProtocol


class RunStatus(Enum):
    """Lifecycle state of a pipeline stage managed by the bridge."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# Module-level state — persists across Streamlit reruns (same Python process).
_threads: dict[str, threading.Thread] = {}
_errors: dict[str, Exception] = {}
_started_at: dict[str, float] = {}  # stage_name -> time.monotonic() at launch


def run_stage(
    stage: "StageProtocol",
    workdir: WorkdirManager,
    config: "RunConfig",
) -> None:
    """Launch *stage* in a background daemon thread.

    Idempotent: if the stage is already running or its done marker exists,
    this function returns immediately without creating a new thread.

    The thread writes only to ``workdir/`` via WorkdirManager; it never
    calls any Streamlit API.

    Args:
        stage: A stage implementing StageProtocol (has .run(workdir, config)).
        workdir: Active WorkdirManager for the current run.
        config: RunConfig for the current run.
    """
    key = stage.stage_name
    if workdir.is_done(key):
        return  # already complete
    if key in _threads and _threads[key].is_alive():
        return  # already running

    # Fresh launch: clear any stale error from a previous failed attempt so
    # stage_status reflects RUNNING (not the old ERROR) once the thread starts.
    _errors.pop(key, None)
    _started_at[key] = time.monotonic()

    def _target() -> None:
        try:
            output = stage.run(workdir, config)
            workdir.write_checkpoint(stage.checkpoint_name, output)
            workdir.mark_done(key)
        except Exception as exc:  # noqa: BLE001
            _errors[key] = exc

    t = threading.Thread(target=_target, daemon=True, name=f"bridge-{key}")
    _threads[key] = t
    t.start()


def stage_status(stage_name: str, workdir: WorkdirManager) -> RunStatus:
    """Return the current RunStatus for a named stage.

    Args:
        stage_name: The stage's ``stage_name`` attribute (e.g. ``"slides"``).
        workdir: Active WorkdirManager (used to check the done marker).

    Returns:
        RunStatus.DONE if done marker present;
        RunStatus.ERROR if the thread raised an exception;
        RunStatus.RUNNING if thread is alive;
        RunStatus.IDLE otherwise.
    """
    if workdir.is_done(stage_name):
        return RunStatus.DONE
    if stage_name in _errors:
        return RunStatus.ERROR
    if stage_name in _threads and _threads[stage_name].is_alive():
        return RunStatus.RUNNING
    return RunStatus.IDLE


def get_error(stage_name: str) -> Exception | None:
    """Return the exception stored for *stage_name*, or None if no error.

    Args:
        stage_name: Stage name to look up.

    Returns:
        The stored Exception, or None.
    """
    return _errors.get(stage_name)


def stage_elapsed(stage_name: str) -> float | None:
    """Return seconds elapsed since *stage_name* was launched, or None.

    Returns the live elapsed time (monotonic) since the stage's thread started.
    Used by the UI to show progress feedback. None if the stage never launched.
    """
    start = _started_at.get(stage_name)
    if start is None:
        return None
    return max(0.0, time.monotonic() - start)


def _reset_state() -> None:
    """Clear module-level thread and error dicts.

    TEST UTILITY ONLY — do not call this in production code.
    Allows tests to isolate bridge state between test cases.
    """
    _threads.clear()
    _errors.clear()
    _started_at.clear()
