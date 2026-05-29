---
phase: 01-foundation
reviewed: 2026-05-25T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/avideo/cli.py
  - src/avideo/orchestrator.py
  - src/avideo/models/config.py
  - src/avideo/stages/base.py
  - src/avideo/stages/stubs.py
  - src/avideo/utils/workdir.py
  - src/avideo/utils/rich_ui.py
  - src/avideo/utils/cost_estimator.py
findings:
  critical: 0
  warning: 6
  info: 3
  total: 9
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-05-25
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 1 (Foundation) delivers a clean, well-documented, modular skeleton: a Typer
CLI, a Pydantic-v2 `RunConfig`, a sequential resumable orchestrator with atomic
checkpoint writes, a `StageProtocol`/`CheckpointMixin` contract, and ten Phase-1
stub stages. The atomicity machinery (`tmp` + `os.replace`, same-directory rename,
`write_checkpoint` → `mark_done` ordering) is correct and well tested. Stubs are
intentional and were not flagged as incomplete.

The review found **no BLOCKER/critical issues** but **six WARNINGs**. The most
material is a real config-correctness bug: `RunConfig` is a `BaseSettings` with no
`env_prefix`, so it silently reads ubiquitous bare environment variables — most
notably `LANGUAGE` (set by locale on essentially every Linux box), but also
`LEVEL`, `DURATION`, `CONTEXT`, `VERBOSE`, etc. This was reproduced empirically:
with no `config.yaml` present and `LANGUAGE=en_US:en` in the environment,
`RunConfig().language == "en_US:en"` instead of the intended default `"es"`. Other
WARNINGs concern the dry-run side-effect (workdir is created despite "no output"
contract), an unguarded `KeyboardInterrupt` at the approval prompt, a dead/incorrect
L3 gate, and two docstring claims that the code does not honor.

## Warnings

### WR-01: `RunConfig` reads bare environment variables — `LANGUAGE` (and others) silently override defaults

**File:** `src/avideo/models/config.py:35-69`
**Issue:** `RunConfig(BaseSettings)` declares no `env_prefix` in its
`SettingsConfigDict`, and `env_settings` is included in `settings_customise_sources`
(line 84). Pydantic-settings therefore maps each field to a bare, upper-cased
environment variable name. Several of these collide with extremely common shell/OS
variables:

- `language` ↔ `LANGUAGE` — set by locale on virtually all Linux systems (e.g. `en_US:en`).
- `level` ↔ `LEVEL`, `duration` ↔ `DURATION`, `context` ↔ `CONTEXT`,
  `verbose` ↔ `VERBOSE`, `voice` ↔ `VOICE`, `wpm` ↔ `WPM`, `bullets` ↔ `BULLETS`.

Reproduced: with `config.yaml` removed and `LANGUAGE=en_US:en` exported,
`RunConfig(bullets=..., duration=120).language` returns `"en_US:en"` rather than
`"es"`. That polluted value then flows into the storyboard/scriptwriter stages
(`config.language`) and produces incorrect narration language. `CONTEXT` can also
inject an arbitrary path into `config.context` (the model performs no existence
check; only the Typer flag does), and `LEVEL` can silently change the automation
gate. The behavior is environment-dependent and effectively undebuggable for an
end user.

This is masked today only because the committed `config.yaml` happens to set
`language: es` (YAML outranks env). Remove or omit a key from `config.yaml` and the
env value wins.

**Fix:** Either disable env as a source for this settings model, or namespace it so
collisions are impossible:
```python
model_config = SettingsConfigDict(
    yaml_file="config.yaml",
    yaml_file_encoding="utf-8",
    extra="ignore",
    env_prefix="AVIDEO_",   # AVIDEO_LANGUAGE, AVIDEO_LEVEL, ... no collision with LANGUAGE
)
```
If env-based config is not actually a requirement for `RunConfig`, drop
`env_settings` from the returned tuple in `settings_customise_sources` entirely:
```python
return (init_settings, YamlConfigSettingsSource(settings_cls))
```

### WR-02: `--dry-run` creates the workdir and all subdirectories despite "no output" contract

**File:** `src/avideo/orchestrator.py:111-118`
**Issue:** `WorkdirManager(config.workdir)` is constructed on line 111 — which in
its `__init__` calls `root.mkdir(parents=True, exist_ok=True)` and creates the
`slides/`, `audio/`, `subs/`, `design_proposal/`, `slides_user/` subdirectories —
*before* the `if config.dry_run:` branch on line 116. The CLI help for `--dry-run`
states "Show cost estimate **without generating any output**" and the orchestrator
docstring says the dry-run branch returns "no stage runs." Reproduced: after a
dry-run against a fresh `workdir`, the directory and all five subdirectories exist
on disk. The existing test `test_orch_dry_run_no_stages_no_mp4` only asserts
`output.mp4` is absent, so this filesystem side-effect is uncaught.

**Fix:** Move workdir construction below the dry-run branch so dry-run is truly
side-effect free:
```python
def run_pipeline(config: RunConfig) -> None:
    if config.dry_run:
        estimate_all(config)
        return
    workdir = WorkdirManager(config.workdir)
    ...
```

### WR-03: `KeyboardInterrupt` at the approval prompt escapes as a raw traceback

**File:** `src/avideo/orchestrator.py:133-147`
**Issue:** `pause_for_approval(stage.stage_name)` (line 135) is called **outside**
the `try/except KeyboardInterrupt` block (which begins at line 138). The approval
prompt (`Confirm.ask` → `console.input` → builtin `input`) is exactly where a user
is most likely to press Ctrl-C. When they do, `KeyboardInterrupt` is raised from
`pause_for_approval`, is not caught here, and propagates uncaught out of
`run_pipeline` and `cli.generate` — producing a raw Python traceback. This directly
contradicts the module docstring ("Intercept KeyboardInterrupt cleanly") and the
`rich_ui` design goal of never letting a raw traceback reach the user. (Only
`typer.Abort` from a declined prompt is handled gracefully; Ctrl-C is not.)

**Fix:** Wrap the whole per-stage body, including the pause, in the interrupt
handler:
```python
for stage in PIPELINE_STAGES:
    if workdir.is_done(stage.stage_name):
        ...
        continue
    try:
        if should_pause(stage.stage_name, config.level):
            pause_for_approval(stage.stage_name)
        output = stage.run(workdir, config)
        workdir.write_checkpoint(stage.checkpoint_name, output)
        workdir.mark_done(stage.stage_name)
        console.print(f"[green]Done:[/green] {stage.stage_name}")
    except KeyboardInterrupt:
        console.print(f"\n[yellow]Interrupted at {stage.stage_name}[/yellow]")
        raise typer.Exit(130)
    progress.advance(task_id)
```

### WR-04: L3 gate logic is dead and semantically inverted — cannot pause even in Phase 6

**File:** `src/avideo/orchestrator.py:54-83, 134`; `src/avideo/orchestrator.py:69-71` (docstring)
**Issue:** `should_pause` implements L3 as
`stage_name in FAIL_STAGES and has_fail` (line 82), but two things make this gate
unable to ever fire — contradicting the docstring claim that "the logic is present
and correct for Phase 6":

1. The orchestrator calls `should_pause(stage.stage_name, config.level)` (line 134)
   and never passes `has_fail`, so it always defaults to `False`. L3 therefore never
   pauses regardless of any verdict.
2. Even if `has_fail` were wired up, the pause is evaluated **before** the stage
   runs (line 134 precedes `stage.run` on line 139). A fail/warning verdict for
   `verify` only exists *after* `verify` runs, so a "pause when this stage produced a
   warning/fail" semantic cannot be satisfied by a pre-run check. The orchestrator
   also never reads the prior `verification.json` to compute `has_fail` on resume.

`SlideVerdict.status` is a free-form `str` and is never inspected anywhere, so there
is no path that derives `has_fail`. Net effect: L3 is functionally identical to L4
(never pauses). Harmless for Phase-1 stubs (which never fail), but the design as
written will not work when wired up in Phase 6 without a structural change.

**Fix:** Decide and document the real L3 semantics, then wire them. If L3 means
"pause *after* verify if it reported a warning/fail," the gate must be evaluated
post-run, reading the just-written verdict, e.g.:
```python
output = stage.run(workdir, config)
workdir.write_checkpoint(stage.checkpoint_name, output)
workdir.mark_done(stage.stage_name)
if config.level == 3 and stage.stage_name in FAIL_STAGES:
    has_fail = isinstance(output, VerificationReport) and any(
        v.status in {"warning", "fail"} for v in output.slides
    )
    if has_fail:
        pause_for_approval(stage.stage_name, reason="verification warning/fail")
```
At minimum, correct the docstring on lines 69-71 to state that L3 is not yet wired
into the loop.

### WR-05: Orchestrator docstring promises `typer.Exit` on stage errors, but raw exceptions propagate

**File:** `src/avideo/orchestrator.py:107-110`
**Issue:** The `run_pipeline` docstring's `Raises:` section states `typer.Exit: On
KeyboardInterrupt (code 130) or any unhandled stage error that propagates out of the
stage's run() method.` In reality, only `KeyboardInterrupt` is caught (line 143).
Any other exception from `stage.run` / `write_checkpoint` / `mark_done` (e.g. an
`OSError` from a full disk, or a real LLM/network error in later phases) propagates
unconverted, and `cli.generate` does not wrap `run_pipeline` either — so it reaches
the user as a raw traceback, again violating the "no raw traceback" design goal.
This is correct-by-accident for Phase-1 stubs (which never raise) but the docstring
is inaccurate and the behavior diverges from the CLI's error-handling contract.

**Fix:** Either implement the documented behavior (catch generic stage exceptions,
log via `console`, and `raise typer.Exit(1)`), or correct the docstring to state
that non-`KeyboardInterrupt` exceptions propagate unhandled. Wiring a top-level
handler is preferable for UX consistency:
```python
except KeyboardInterrupt:
    console.print(f"\n[yellow]Interrupted at {stage.stage_name}[/yellow]")
    raise typer.Exit(130)
except Exception as exc:  # pragma: no cover (real errors arrive in later phases)
    console.print(f"[red]Stage {stage.stage_name} failed:[/red] {exc}")
    raise typer.Exit(1)
```

### WR-06: `write_checkpoint` can leave an orphaned `.json.tmp` if the tmp write fails mid-stream

**File:** `src/avideo/utils/workdir.py:108-111`
**Issue:** `tmp.write_text(...)` (line 110) is not guarded. If the write fails
partway through (disk full, interrupted I/O), `os.replace` never runs — so the
target JSON stays safe and `mark_done` is never reached (the atomicity guarantee
holds). However, the partially written `tmp` file (`<name>.json.tmp`) is left behind
on disk. The class docstring and `test_write_checkpoint_no_tmp_file_left_behind`
assert tmp cleanliness only on the success path; the failure path accumulates stale
tmp files across retries/resumes. This is a robustness gap, not a data-integrity
gap.

**Fix:** Clean up the tmp file on failure:
```python
target = self.checkpoint_path(name)
tmp = target.with_suffix(".json.tmp")
try:
    tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    os.replace(str(tmp), str(target))
except OSError:
    tmp.unlink(missing_ok=True)
    raise
```

## Info

### IN-01: `total_tokens` typed as `float` but used as an integer count

**File:** `src/avideo/utils/cost_estimator.py:66, 71, 84`
**Issue:** `total_tokens: float = 0` accumulates `int` values and is later rendered
with `int(total_tokens)`. Token counts are inherently integers; typing the
accumulator as `float` is misleading and forces the `int(...)` cast on line 84.
**Fix:** Declare `total_tokens: int = 0` and drop the cast in the total row.

### IN-02: `STAGE_COSTS` token values declared as floats for an int-only field

**File:** `src/avideo/utils/cost_estimator.py:30-41`
**Issue:** The nested dict is typed `dict[str, dict[str, float]]`, forcing
`int(costs["tokens"])` on line 70 even though every `tokens` value is a whole
number. Magic placeholder numbers are acceptable for Phase 1, but a cleaner shape
would separate the two units.
**Fix:** Use a small typed structure (e.g. a `NamedTuple`/dataclass `StageCost(tokens:
int, usd: float)`) so the int/float split is explicit and the casts disappear.

### IN-03: `should_pause` has an unreachable final `return False`

**File:** `src/avideo/orchestrator.py:75-83`
**Issue:** `level` is validated by `RunConfig` to be `1 <= level <= 4`, so the
branches for levels 1-4 are exhaustive and the trailing `return False` on line 83 is
dead code. It is harmless (defensive default) but unreachable given the model
constraint.
**Fix:** Acceptable as a defensive default; optionally add a comment noting it is a
guard for out-of-range levels that the model already prevents.

---

_Reviewed: 2026-05-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
