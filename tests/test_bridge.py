"""RED tests for PipelineBridge thread lifecycle.

These tests FAIL with ModuleNotFoundError until Plan 03 creates
src/avideo/ui/bridge.py.  They are written before the implementation
exists and define the contract Plan 03 must satisfy.

No Streamlit APIs are called or imported in this file.
"""
import time
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Module-level import — fails with ModuleNotFoundError until bridge.py exists
# ---------------------------------------------------------------------------
from avideo.ui.bridge import (  # noqa: E402
    run_stage,
    stage_status,
    RunStatus,
    get_error,
    format_stage_error,
    _reset_state,
)


# ---------------------------------------------------------------------------
# Fake stages for testing — no Streamlit, no real pipeline dependencies
# ---------------------------------------------------------------------------


class FakeStage:
    """Minimal stage that returns immediately (success path)."""

    stage_name = "fake"
    checkpoint_name = "fake"

    def run(self, workdir, config):
        from pydantic import BaseModel

        class Out(BaseModel):
            ok: bool = True

        return Out()


class FakeErrorStage:
    """Stage that always raises RuntimeError (error path)."""

    stage_name = "fake_err"
    checkpoint_name = "fake_err"

    def run(self, workdir, config):
        raise RuntimeError("intentional test failure")


# ---------------------------------------------------------------------------
# Helper: build a minimal RunConfig without reading files or env vars
# ---------------------------------------------------------------------------


def _minimal_config(tmp_path: Path):
    """Construct a RunConfig via model_construct to avoid env/file validation."""
    from avideo.models.config import RunConfig

    bullets = tmp_path / "b.yaml"
    bullets.write_text("title: T\nbullets:\n  - B\n", encoding="utf-8")
    # model_construct skips validators — safe for test-only objects
    return RunConfig.model_construct(
        bullets=bullets,
        duration=60,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_stage_launches_thread(tmp_workdir: Path, tmp_path: Path) -> None:
    """run_stage transitions status from IDLE to RUNNING or DONE (not IDLE)."""
    from avideo.utils.workdir import WorkdirManager

    _reset_state()
    wm = WorkdirManager(tmp_workdir)
    config = _minimal_config(tmp_path)

    run_stage(FakeStage(), wm, config)

    status = stage_status("fake", wm)
    assert status in (RunStatus.RUNNING, RunStatus.DONE), (
        f"expected RUNNING or DONE immediately after launch, got {status}"
    )


def test_run_stage_idempotent_when_already_done(tmp_workdir: Path, tmp_path: Path) -> None:
    """run_stage is a no-op when the stage is already marked done."""
    from avideo.utils.workdir import WorkdirManager

    _reset_state()
    wm = WorkdirManager(tmp_workdir)
    config = _minimal_config(tmp_path)

    # Pre-mark the stage as done (simulates resume scenario)
    wm.mark_done("fake")

    # Both calls must be no-ops — no new thread should be created
    run_stage(FakeStage(), wm, config)
    run_stage(FakeStage(), wm, config)

    assert stage_status("fake", wm) == RunStatus.DONE


def test_stage_status_done_after_completion(tmp_workdir: Path, tmp_path: Path) -> None:
    """stage_status returns DONE once the background thread completes."""
    from avideo.utils.workdir import WorkdirManager

    _reset_state()
    wm = WorkdirManager(tmp_workdir)
    config = _minimal_config(tmp_path)

    run_stage(FakeStage(), wm, config)

    # Poll until DONE or timeout (FakeStage is near-instant, but give 3 s headroom)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if stage_status("fake", wm) == RunStatus.DONE:
            break
        time.sleep(0.1)

    assert stage_status("fake", wm) == RunStatus.DONE, (
        "stage_status must be DONE within 3 s of FakeStage completing"
    )


def test_get_error_returns_none_on_success(tmp_workdir: Path, tmp_path: Path) -> None:
    """get_error returns None after a successful stage run."""
    from avideo.utils.workdir import WorkdirManager

    _reset_state()
    wm = WorkdirManager(tmp_workdir)
    config = _minimal_config(tmp_path)

    run_stage(FakeStage(), wm, config)

    # Wait for completion
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if stage_status("fake", wm) == RunStatus.DONE:
            break
        time.sleep(0.1)

    assert get_error("fake") is None


def test_run_stage_stores_error_on_failure(tmp_workdir: Path, tmp_path: Path) -> None:
    """stage_status is ERROR and get_error is not None after stage raises."""
    from avideo.utils.workdir import WorkdirManager

    _reset_state()
    wm = WorkdirManager(tmp_workdir)
    config = _minimal_config(tmp_path)

    run_stage(FakeErrorStage(), wm, config)

    # Poll until ERROR or timeout
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if stage_status("fake_err", wm) == RunStatus.ERROR:
            break
        time.sleep(0.1)

    assert stage_status("fake_err", wm) == RunStatus.ERROR
    assert get_error("fake_err") is not None, (
        "get_error must return the stored exception after stage failure"
    )


def test_format_stage_error_returns_empty_string_when_no_error() -> None:
    """format_stage_error returns "" when no error is stored for the stage."""
    _reset_state()
    assert format_stage_error("nonexistent_stage") == ""


def test_format_stage_error_extracts_elevenlabs_style_body_message() -> None:
    """format_stage_error surfaces body['detail']['message'] instead of the raw
    exception repr (which otherwise dumps full HTTP headers/status_code/body —
    observed live during v2.0.0 browser UAT with a real ElevenLabs 402 error).
    """
    _reset_state()

    class FakeApiError(Exception):
        def __init__(self) -> None:
            super().__init__("status_code: 402, headers: {...a huge dict...}")
            self.body = {
                "detail": {
                    "type": "payment_required",
                    "message": "Free users cannot use library voices via the API.",
                }
            }

    class FakeFailingStage:
        stage_name = "fake_err_api"
        checkpoint_name = "fake_err_api"

        def run(self, workdir, config):
            raise FakeApiError()

    import tempfile

    from avideo.utils.workdir import WorkdirManager

    tmp = Path(tempfile.mkdtemp())
    wm = WorkdirManager(tmp)
    config = _minimal_config(tmp)

    run_stage(FakeFailingStage(), wm, config)

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if stage_status("fake_err_api", wm) == RunStatus.ERROR:
            break
        time.sleep(0.1)

    msg = format_stage_error("fake_err_api")
    assert msg == "Free users cannot use library voices via the API."
    assert "headers" not in msg
    assert "status_code" not in msg
