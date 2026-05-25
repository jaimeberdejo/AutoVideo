"""Sequential pipeline orchestrator — the spine of the auto-video-narrado pipeline.

Responsibilities:
- Execute all stages in PIPELINE_STAGES order.
- Skip stages whose done marker already exists (idempotence + resume).
- Enforce L1–L4 approval gates via should_pause / pause_for_approval.
- Write checkpoints atomically and mark stages done ONLY after a successful write
  (Pitfall-4 ordering guarantee: write_checkpoint → mark_done, never the reverse).
- Intercept KeyboardInterrupt cleanly — partial-run state is left intact for resume.
- Branch on dry_run: print cost table and exit without running any stage.

The orchestrator is the ONLY component that pauses for user approval.
Stages (StageProtocol) must never call input() or Confirm.ask() directly.

Level semantics (locked in CONTEXT.md):
    L1 = pause after EVERY stage
    L2 = pause only on creative checkpoints: storyboard, scriptwriter, slides, verify
    L3 = pause after verify if it produced a warning/fail verdict.
         Not yet wired in Phase 1: the verifier stub never fails and no verdict
         is read post-run.  TODO(Phase 6): evaluate verdict after verify.run()
         and call pause_for_approval when has_fail is True.
    L4 = never pause (fully autonomous)
"""
from __future__ import annotations

import typer

from avideo.models import RunConfig
from avideo.stages.stubs import PIPELINE_STAGES
from avideo.utils.cost_estimator import estimate_all
from avideo.utils.rich_ui import console, make_progress, pause_for_approval
from avideo.utils.workdir import WorkdirManager

# ---------------------------------------------------------------------------
# Approval-gate constants
# ---------------------------------------------------------------------------

#: Stage names that trigger L2 pauses (creative checkpoints).
#: Uses the ACTUAL stage_name attributes, not checkpoint names.
CREATIVE_STAGES: frozenset[str] = frozenset({
    "storyboard",
    "scriptwriter",
    "slides",
    "verify",
})

#: Stage names that can emit a "fail" verdict (only the verifier in Phase 6).
FAIL_STAGES: frozenset[str] = frozenset({"verify"})


# ---------------------------------------------------------------------------
# should_pause — pure function, testable without I/O
# ---------------------------------------------------------------------------


def should_pause(stage_name: str, level: int) -> bool:
    """Return True if the orchestrator should pause for approval before this stage.

    Implements L1/L2/L4 gate semantics as locked in CONTEXT.md.

    - L1: always pause.
    - L2: pause only for creative stages (storyboard, scriptwriter, slides, verify).
    - L3: L3 semantics ("pause after verify if it produced a warning/fail verdict")
          require a post-run check.  That wiring is deferred to Phase 6 when the
          verifier stage is implemented.  In Phase 1, level=3 behaves like level=4
          (no pauses) because the stub verifier never fails.
    - L4: never pause.

    Args:
        stage_name: The ``stage_name`` attribute of the stage about to run.
        level: Automation level 1–4.

    Returns:
        True if the pipeline should call ``pause_for_approval`` before proceeding.
    """
    if level == 4:
        return False
    if level == 1:
        return True
    if level == 2:
        return stage_name in CREATIVE_STAGES
    # level == 3: post-run verdict check not yet implemented (Phase 6 TODO)
    return False


# ---------------------------------------------------------------------------
# run_pipeline — main entry point
# ---------------------------------------------------------------------------


def run_pipeline(config: RunConfig) -> None:
    """Execute the full pipeline sequentially, respecting resume and approval gates.

    Steps:
    1. If dry_run: print cost estimate table and return — no stage runs, no workdir created.
    2. Instantiate WorkdirManager (creates workdir + subdirectories).
    3. Iterate over PIPELINE_STAGES:
       a. Skip if already done (done marker present).
       b. Pause for approval if should_pause returns True.
       c. Run stage; write checkpoint; mark done (in this exact order — Pitfall-4).
       d. On KeyboardInterrupt: print clean message and exit 130.
    4. Wrap loop in a transient Rich Progress bar (CLI-08).

    Args:
        config: Fully merged RunConfig (CLI flags > config.yaml > defaults).

    Raises:
        typer.Exit: On KeyboardInterrupt at the approval prompt or during a stage
            (code 130), or on any unhandled stage exception (code 1).  No raw
            Python traceback reaches the user.
    """
    # ------------------------------------------------------------------
    # Dry-run branch: print cost table and return immediately.
    # WorkdirManager is NOT constructed here — dry-run must be side-effect free.
    # ------------------------------------------------------------------
    if config.dry_run:
        estimate_all(config)
        return

    workdir = WorkdirManager(config.workdir)

    # ------------------------------------------------------------------
    # Main pipeline loop
    # ------------------------------------------------------------------
    with make_progress() as progress:
        task_id = progress.add_task("Running pipeline…", total=len(PIPELINE_STAGES))

        for stage in PIPELINE_STAGES:
            # Skip-done: idempotent resume
            if workdir.is_done(stage.stage_name):
                console.print(f"[dim]Skipping {stage.stage_name} (done)[/dim]")
                progress.advance(task_id)
                continue

            # Pitfall-4 ordering + clean error handling:
            # Wrap the approval gate AND stage execution so that both Ctrl-C
            # (at the prompt or during the stage) and unexpected stage errors
            # surface as a clean Rich message rather than a raw traceback.
            try:
                # Approval gate (L1/L2/L3 only; L4 never pauses)
                if should_pause(stage.stage_name, config.level):
                    pause_for_approval(stage.stage_name)

                # Happy path — Pitfall-4 ordering: write_checkpoint THEN mark_done
                output = stage.run(workdir, config)
                workdir.write_checkpoint(stage.checkpoint_name, output)
                workdir.mark_done(stage.stage_name)
                console.print(f"[green]Done:[/green] {stage.stage_name}")
            except KeyboardInterrupt:
                console.print(
                    f"\n[yellow]Interrupted at {stage.stage_name}[/yellow]"
                )
                raise typer.Exit(130)
            except Exception as exc:  # pragma: no cover (real errors arrive in later phases)
                console.print(f"[red]Stage {stage.stage_name} failed:[/red] {exc}")
                raise typer.Exit(1)

            progress.advance(task_id)
