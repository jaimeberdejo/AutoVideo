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

Level semantics (locked in CONTEXT.md, fully wired in Phase 6):
    L1 = pause after EVERY stage; for "verify" in hybrid/manual mode the pre-run
         creative pause is suppressed and replaced by the post-run iterate pause
         (report shown, then pause once).  In auto mode verify keeps its pre-run
         creative pause (post-run gate is a no-op for auto).
    L2 = pause only on creative checkpoints: storyboard, scriptwriter, slides, verify.
         Same verify suppression as L1: pre-run pause suppressed in hybrid/manual,
         replaced by post-run iterate pause.
    L3 = no pre-run pauses; post-run verdict check after verify: stops (Exit 1) on
         any "fail" verdict; "warning" never stops L3/L4.
    L4 = never pause; post-run verdict check after verify: stops (Exit 1) on any
         "fail" verdict (same as L3); continues silently when all ok.
"""
from __future__ import annotations

import typer
from rich.table import Table

from avideo.models import RunConfig
from avideo.models.verification import VerificationReport
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

#: Status → Rich style mapping for the verification report table.
_STATUS_STYLE: dict[str, str] = {"ok": "green", "warning": "yellow", "fail": "red"}


# ---------------------------------------------------------------------------
# _render_verification_report — Rich table for L1/L2 iterate gate
# ---------------------------------------------------------------------------


def _render_verification_report(report: VerificationReport) -> None:
    """Print a Rich table summarising the VerificationReport for L1/L2 review.

    Columns: Slide | Status (colour-coded) | Issues | Suggestions.
    Printed to the same console as all other pipeline output (stderr via Rich).

    Args:
        report: The ``VerificationReport`` returned by ``VerifyStage.run``.
    """
    table = Table(title="Verification Report", show_lines=True)
    table.add_column("Slide", style="dim", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Issues")
    table.add_column("Suggestions")
    for v in report.slides:
        style = _STATUS_STYLE.get(v.status, "white")
        table.add_row(
            str(v.slide_index),
            f"[{style}]{v.status}[/{style}]",
            "\n".join(v.issues),
            "\n".join(v.suggestions),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# should_pause — pure function, testable without I/O
# ---------------------------------------------------------------------------


def should_pause(stage_name: str, level: int) -> bool:
    """Return True if the orchestrator should pause for approval before this stage.

    Implements L1/L2/L4 pre-run gate semantics as locked in CONTEXT.md.

    - L1: always pause before every stage (pre-run gate).
    - L2: pause only for creative stages (storyboard, scriptwriter, slides, verify).
    - L3: never pauses pre-run. The L3 verify verdict is a POST-run check
          (see the verify-gate block in run_pipeline). Returning False here is
          correct and must NOT be changed to True (Pitfall 4).
    - L4: never pause (fully autonomous).

    Note on "verify" at L1/L2 in hybrid/manual mode: the pre-run pause for
    "verify" is suppressed in the loop when slides_mode != "auto" (the single
    verify pause is the post-run iterate pause instead). In auto mode the post-run
    gate is a no-op, so the pre-run creative pause is kept — this preserves the
    L1==10 and L2==4 pause counts expected by existing auto-mode tests.

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
    # level == 3: post-run verdict check (not a pre-run pause — Pitfall 4)
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
                # Approval gate (L1/L2 only; L4 never pauses; L3 uses post-run check).
                # For "verify" in hybrid/manual mode, suppress the pre-run creative pause
                # so the single verify pause is the POST-run iterate pause (below).
                # In auto mode the post-run gate is a no-op, so the pre-run pause is kept
                # to preserve L1==10 and L2==4 pause counts (auto-mode tests).
                _is_verify = stage.stage_name == "verify"
                _suppress_prerun = _is_verify and config.slides_mode.value != "auto"
                if should_pause(stage.stage_name, config.level) and not _suppress_prerun:
                    pause_for_approval(stage.stage_name)

                # Happy path — Pitfall-4 ordering: write_checkpoint THEN mark_done
                output = stage.run(workdir, config)

                # -------------------------------------------------------------------
                # Post-verify verdict gate (VERIFY-03 / Pitfall 4: post-run check).
                # Must run BEFORE write_checkpoint so a fail verdict prevents recording
                # a successful done marker.
                # -------------------------------------------------------------------
                if stage.stage_name in FAIL_STAGES:
                    report: VerificationReport = output  # type: ignore[assignment]
                    has_fail = any(v.status == "fail" for v in report.slides)
                    mode = config.slides_mode.value

                    if mode == "auto":
                        pass  # verifier skipped/trivial — no gate (VERIFY-03)
                    elif config.level in (1, 2):
                        # L1/L2: render report + pause to iterate
                        _render_verification_report(report)
                        pause_for_approval(
                            "verify",
                            reason=(
                                "review verification; fix slides in slides_user/ "
                                "and re-run to re-verify"
                            ),
                        )
                    elif config.level in (3, 4):
                        # L3/L4: stop on fail; warning never stops (VERIFY-03)
                        if has_fail:
                            console.print(
                                "[red]Verification failed (fail verdict) — stopping.[/red]"
                            )
                            raise typer.Exit(1)
                        # all-ok → continue silently

                workdir.write_checkpoint(stage.checkpoint_name, output)
                workdir.mark_done(stage.stage_name)
                console.print(f"[green]Done:[/green] {stage.stage_name}")
            except typer.Exit:
                # Re-raise typer.Exit BEFORE the broad except so a fail verdict's
                # Exit(1) is never swallowed into the generic "Stage failed" handler.
                # This is required so test_orch_level3_verify_fail_exits sees exit_code 1
                # (T-06-05 / VERIFY-03 gate bypass mitigation).
                raise
            except KeyboardInterrupt:
                console.print(
                    f"\n[yellow]Interrupted at {stage.stage_name}[/yellow]"
                )
                raise typer.Exit(130)
            except Exception as exc:  # pragma: no cover (real errors arrive in later phases)
                console.print(f"[red]Stage {stage.stage_name} failed:[/red] {exc}")
                raise typer.Exit(1)

            progress.advance(task_id)
