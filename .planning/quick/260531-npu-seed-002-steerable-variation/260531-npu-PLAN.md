---
quick_id: 260531-npu
type: execute
wave: 1
depends_on: []
files_modified:
  - src/avideo/models/feedback.py
  - src/avideo/utils/workdir.py
  - src/avideo/stages/storyboard.py
  - src/avideo/stages/scriptwriter.py
  - src/avideo/stages/slides_auto.py
  - src/avideo/ui/pipeline_ops.py
  - src/avideo/ui/pages/phase_2_guion.py
  - src/avideo/ui/pages/phase_3_slides.py
  - tests/test_seed002_feedback.py
autonomous: true
requirements: [SEED-002]

must_haves:
  truths:
    - "Fase 2 Guion shows st.text_area + st.radio (Afinar tono/redacción | Cambiar nº de slides/estructura)"
    - "Fase 3 Diapositivas shows st.text_area + st.radio (Estilo visual/colores; 'Añadir imágenes' option is present but disabled)"
    - "feedback.json is written to workdir before the re-run and cleared by the stage after a successful call_structured"
    - "rerun_with_feedback(workdir, config, 'scriptwriter', text) deletes .scriptwriter.done + invalidates downstream + runs ScriptwriterStage"
    - "rerun_with_feedback(workdir, config, 'storyboard', text) deletes .storyboard.done + invalidates downstream + runs StoryboardStage"
    - "rerun_with_feedback(workdir, config, 'slides', text) deletes .slides.done + invalidates downstream + runs SlidesDispatchStage"
    - "_build_prompts in storyboard, scriptwriter, slides_auto includes the delimited feedback block when feedback is non-None"
    - "_build_prompts omits the feedback block when feedback is None (backward compat)"
    - "All 419 existing tests continue to pass"
  artifacts:
    - path: src/avideo/models/feedback.py
      provides: FeedbackCheckpoint pydantic model (keyed by stage name)
    - path: src/avideo/utils/workdir.py
      provides: write_feedback / read_feedback / clear_feedback helpers
    - path: src/avideo/ui/pipeline_ops.py
      provides: rerun_with_feedback dispatcher
    - path: tests/test_seed002_feedback.py
      provides: test coverage for all three behaviour contracts
  key_links:
    - from: phase_2_guion.py btn_variation
      to: pipeline_ops.rerun_with_feedback
      via: stage selector radio → target_stage kwarg
    - from: pipeline_ops.rerun_with_feedback
      to: workdir.write_feedback / done_marker.unlink / run_stage
      via: sequential calls in dispatcher
    - from: stages/*.run()
      to: workdir.read_feedback / clear_feedback
      via: start of run(), cleared after successful call_structured
---

<objective>
Implement SEED-002 steerable variation: add free-text instruction + explicit stage selector to
"Pedir variación" in Fase 2 (Guion) and Fase 3 (Diapositivas) so the user can direct
regeneration instead of re-generating blindly.

Purpose: User can say "tono más cercano", "cambia el número de slides a 4", or "esquema
de color azul" and the right stage is re-run with that instruction injected into the LLM prompt.

Output:
- FeedbackCheckpoint model + workdir helpers (feedback.json transport)
- rerun_with_feedback dispatcher in pipeline_ops (no RunConfig changes)
- _build_prompts updated in storyboard, scriptwriter, slides_auto (optional feedback param)
- UI in phase_2_guion + phase_3_slides (st.text_area + st.radio replacing bare buttons)
- Test file covering prompt injection + dispatcher routing + consumed-once lifecycle
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260531-npu-seed-002-steerable-variation/260531-npu-CONTEXT.md

<!-- Key interfaces extracted from codebase — executor uses these directly. -->
<interfaces>
<!-- WorkdirManager (src/avideo/utils/workdir.py) — add three helpers below existing methods -->
class WorkdirManager:
    def checkpoint_path(self, name: str) -> Path: ...
    def done_marker(self, stage: str) -> Path: ...
    def is_done(self, stage: str) -> bool: ...
    def mark_done(self, stage: str) -> None: ...
    def invalidate_downstream(self, from_stage: str) -> list[str]: ...
    def write_checkpoint(self, name: str, model: BaseModel) -> None: ...  # atomic via os.replace
    def read_checkpoint(self, name: str, model_class: type[BaseModel]) -> BaseModel: ...

<!-- pipeline_ops.py — existing single-stage runners to keep as thin wrappers -->
def rerun_scriptwriter(workdir, config) -> None:   # keep; delegate to rerun_with_feedback
def rerun_slides(workdir, config, theme_path=None) -> None:  # keep; delegate to rerun_with_feedback

<!-- Stage _build_prompts signatures to extend (feedback: str | None = None) -->
# storyboard.py — currently:
def _build_prompts(storyboard, timings, language) -> tuple[str, str]
# becomes:
def _build_prompts(storyboard, timings, language, feedback: str | None = None) -> tuple[str, str]

# storyboard.py — no _build_prompts, builds prompts inline in run(); needs same pattern:
# add optional feedback param to run() → append block before call_structured

# slides_auto.py — prompt built inline in resolve_theme() and in SlidesAutoStage.run()
# The visual feedback should be appended to the _THEME_USER_PROMPT user string,
# OR to a new _SLIDES_FEEDBACK_BLOCK injected in SlidesAutoStage.run() per slide.
# Per CONTEXT.md decision: append to the theme-generation user prompt via feedback param
# in SlidesAutoStage.run() → resolve_theme() call. Theme is NOT idempotent-skipped when
# feedback is present (delete theme.yaml from workdir before re-run via clear feedback path).

<!-- Existing mock seam pattern (for tests) -->
# avideo.stages.storyboard.call_structured  → mocker.patch("avideo.stages.storyboard.call_structured")
# avideo.stages.scriptwriter.call_structured → mocker.patch("avideo.stages.scriptwriter.call_structured")
# avideo.stages.slides_auto.call_structured  → mocker.patch("avideo.stages.slides_auto.call_structured")
# avideo.ui.pipeline_ops.run_stage           → mocker.patch("avideo.ui.pipeline_ops.run_stage")

<!-- Feedback block delimiter (use this exact string for consistency) -->
_FEEDBACK_BLOCK_TEMPLATE = """\

--- Instrucción del usuario (prioritaria) ---
{feedback}
--- Fin de instrucción ---
"""

<!-- STAGE_ORDER (workdir.py) — used to validate stage names -->
STAGE_ORDER = ["context","storyboard","timing","scriptwriter","slides","verify","voice","align","subs","assemble"]
</interfaces>
</context>

<tasks>

<!-- ============================================================ -->
<!-- TASK 1: FeedbackCheckpoint model + WorkdirManager helpers   -->
<!-- ============================================================ -->

<task type="auto" tdd="true">
  <name>Task 1: FeedbackCheckpoint model and workdir helpers</name>
  <files>
    src/avideo/models/feedback.py
    src/avideo/utils/workdir.py
  </files>
  <behavior>
    - write_feedback("scriptwriter", "tono más cercano") → feedback.json exists with {"scriptwriter": "tono más cercano"}
    - write_feedback("storyboard", "4 slides") on existing file → merges (adds key, keeps others)
    - read_feedback("scriptwriter") on missing file → returns None
    - read_feedback("scriptwriter") after write_feedback → returns the text
    - clear_feedback("scriptwriter") removes that key; file still valid JSON for other keys
    - clear_feedback on missing file → no error (silent no-op)
    - FeedbackCheckpoint is a pydantic BaseModel with field: entries: dict[str, str] = {}
  </behavior>
  <action>
Create `src/avideo/models/feedback.py`:
```python
"""FeedbackCheckpoint — ephemeral per-stage user feedback transport model."""
from __future__ import annotations
from pydantic import BaseModel

class FeedbackCheckpoint(BaseModel):
    """Keyed by stage name. Entries are ephemeral: cleared by each stage after use."""
    entries: dict[str, str] = {}
```

In `src/avideo/utils/workdir.py`, add three helpers after `read_checkpoint`. All three
operate on `workdir/feedback.json` using the FeedbackCheckpoint model.
Import is lazy (inside each method body) to avoid circular imports.

```python
def write_feedback(self, stage: str, text: str) -> None:
    """Write (or merge) a feedback entry for *stage* into feedback.json."""
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
    """Return the feedback text for *stage*, or None if absent."""
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
    """Remove the feedback entry for *stage* (silent no-op if absent)."""
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
```

Tests go in `tests/test_seed002_feedback.py` (initial class `TestWorkdirFeedback`).
Use `WorkdirManager(tmp_path / "workdir")` directly (no mocking needed — pure filesystem).
  </action>
  <verify>
    <automated>cd /Users/jaimeberdejosanchez/projects/auto-video-narrado && uv run pytest tests/test_seed002_feedback.py::TestWorkdirFeedback -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>All TestWorkdirFeedback tests pass; feedback.json round-trip confirmed.</done>
</task>

<!-- ============================================================ -->
<!-- TASK 2: Stage prompt injection + consumed-once lifecycle     -->
<!-- ============================================================ -->

<task type="auto" tdd="true">
  <name>Task 2: Stage prompt injection (storyboard, scriptwriter, slides_auto) + consumed-once</name>
  <files>
    src/avideo/stages/storyboard.py
    src/avideo/stages/scriptwriter.py
    src/avideo/stages/slides_auto.py
  </files>
  <behavior>
    Storyboard:
    - _build_prompts(sb, timings, "es", feedback=None) → user prompt does NOT contain "Instrucción del usuario"
    - _build_prompts(sb, timings, "es", feedback="cambia a 4 slides") → user prompt contains the feedback block
    - StoryboardStage.run() reads workdir.read_feedback("storyboard") at start; after call_structured
      succeeds, calls workdir.clear_feedback("storyboard")

    Scriptwriter:
    - _build_prompts(sb, tm, "es", feedback=None) → user prompt does NOT contain "Instrucción del usuario"
    - _build_prompts(sb, tm, "es", feedback="tono más cercano") → user prompt contains the block
    - ScriptwriterStage.run() reads workdir.read_feedback("scriptwriter"); clears after first
      call_structured succeeds (before the calibration retry check)

    SlidesAuto:
    - SlidesAutoStage.run() reads workdir.read_feedback("slides"); if present, passes it to
      resolve_theme() AND deletes theme.yaml before calling resolve_theme (so idempotency
      check is bypassed and a fresh theme is generated). Clears feedback after call_structured
      inside resolve_theme succeeds.
    - resolve_theme(theme_path, storyboard, feedback=None) — feedback appended to user prompt
      when non-None, using _FEEDBACK_BLOCK_TEMPLATE.
  </behavior>
  <action>
**Feedback block template** — add as module-level constant in each of the three stage files:

```python
_FEEDBACK_BLOCK = """\

--- Instrucción del usuario (prioritaria) ---
{feedback}
--- Fin de instrucción ---
"""
```

**storyboard.py** changes:

1. `_build_prompts` signature: add `feedback: str | None = None` after `language`.
   After building `user`, if `feedback` is not None: `user += _FEEDBACK_BLOCK.format(feedback=feedback)`.

   Note: storyboard.py does not currently have a separate `_build_prompts` function —
   the prompt is built inline in `run()`. Extract it into a `_build_prompts` function
   following the same pattern as scriptwriter.py:
   ```python
   def _build_prompts(
       bullets_input, context_text, title, duration, language, feedback=None
   ) -> tuple[str, str]:
   ```
   Then call it from `run()`.

2. In `StoryboardStage.run()`:
   - After reading `context_text`, add:
     `feedback = workdir.read_feedback("storyboard")`
   - Pass `feedback=feedback` to `_build_prompts`.
   - After the `call_structured(...)` call returns `result`, add:
     `workdir.clear_feedback("storyboard")`
   - Return `result`.

**scriptwriter.py** changes:

1. `_build_prompts` signature: add `feedback: str | None = None` as fourth param.
   After building `user`, if `feedback`: `user += _FEEDBACK_BLOCK.format(feedback=feedback)`.

2. In `ScriptwriterStage.run()`:
   - Before `_build_prompts` call: `feedback = workdir.read_feedback("scriptwriter")`
   - Pass `feedback=feedback` to `_build_prompts`.
   - After the FIRST `call_structured(...)` call returns `result` (before drift check):
     `workdir.clear_feedback("scriptwriter")`

**slides_auto.py** changes:

1. `resolve_theme` signature: add `feedback: str | None = None` after `storyboard`.
   In the user prompt building block (before `call_structured`):
   `if feedback: user += _FEEDBACK_BLOCK.format(feedback=feedback)`

2. In `SlidesAutoStage.run()`:
   - Before `resolve_theme` call: `feedback = workdir.read_feedback("slides")`
   - If feedback is not None, delete theme.yaml to bypass idempotency:
     `if feedback and self._theme_path.exists(): self._theme_path.unlink()`
   - Pass `feedback=feedback` to `resolve_theme`.
   - After `resolve_theme` returns (theme resolved): `workdir.clear_feedback("slides")`

Add tests to `tests/test_seed002_feedback.py` in new classes:
- `TestStoryboardFeedbackPrompt` — patches `call_structured`, calls `_build_prompts` directly
- `TestScriptwriterFeedbackPrompt` — patches `call_structured`, calls `_build_prompts` directly
- `TestSlidesAutoFeedbackPrompt` — patches `call_structured` + `SlideRenderer`, verifies
  that resolve_theme user prompt includes feedback block when non-None
- `TestFeedbackConsumedOnce` — for scriptwriter: write_feedback + run() → clear_feedback called
  (mock call_structured; check workdir feedback is absent after run)
  </action>
  <verify>
    <automated>cd /Users/jaimeberdejosanchez/projects/auto-video-narrado && uv run pytest tests/test_seed002_feedback.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>
    All test_seed002_feedback.py tests pass. Existing storyboard/scriptwriter/slides_auto tests
    still pass (backward compat: feedback=None is the default).
    Run: uv run pytest tests/test_storyboard.py tests/test_scriptwriter.py tests/test_slides_auto.py -q
  </done>
</task>

<!-- ============================================================ -->
<!-- TASK 3: pipeline_ops.rerun_with_feedback dispatcher          -->
<!-- ============================================================ -->

<task type="auto" tdd="true">
  <name>Task 3: rerun_with_feedback dispatcher in pipeline_ops</name>
  <files>
    src/avideo/ui/pipeline_ops.py
  </files>
  <behavior>
    - rerun_with_feedback(workdir, config, "scriptwriter", "tono más cercano"):
        calls workdir.write_feedback("scriptwriter", "tono más cercano")
        calls workdir.done_marker("scriptwriter").unlink(missing_ok=True)
        calls workdir.invalidate_downstream("scriptwriter")
        calls run_stage(ScriptwriterStage(), workdir, config)
    - rerun_with_feedback(workdir, config, "storyboard", "cambia a 4 slides"):
        calls workdir.write_feedback("storyboard", ...)
        calls workdir.done_marker("storyboard").unlink(missing_ok=True)
        calls workdir.invalidate_downstream("storyboard")
        calls run_stage(StoryboardStage(), workdir, config)
    - rerun_with_feedback(workdir, config, "slides", "esquema azul"):
        calls workdir.write_feedback("slides", ...)
        calls workdir.done_marker("slides").unlink(missing_ok=True)
        calls workdir.invalidate_downstream("slides")
        calls run_stage(SlidesDispatchStage(...), workdir, config)
    - rerun_with_feedback with unknown stage raises ValueError
    - rerun_scriptwriter now delegates to rerun_with_feedback(workdir, config, "scriptwriter", feedback="")
      (or keep its body, but call rerun_with_feedback internally — no behavior change for callers)
    - rerun_slides now delegates similarly for "slides"
    - pipeline_ops still has NO Streamlit import
  </behavior>
  <action>
Add `rerun_with_feedback` after the existing `rerun_slides` function. Keep `rerun_scriptwriter`
and `rerun_slides` as public API (they are imported by existing UI pages and tested separately)
but have them delegate to `rerun_with_feedback` with empty-string feedback (preserves behavior,
avoids duplication):

```python
_VALID_FEEDBACK_STAGES = {"storyboard", "scriptwriter", "slides"}


def rerun_with_feedback(
    workdir: "WorkdirManager",
    config: "RunConfig",
    target_stage: str,
    feedback: str,
) -> None:
    """Write feedback.json, invalidate done-markers, and launch the target stage.

    This is the single entry point for all steered re-runs from the UI. The stage
    reads workdir.read_feedback(target_stage) at the start of its run() and clears
    it after a successful call_structured call (consumed-once lifecycle).

    For target_stage="storyboard": runs StoryboardStage. Done-marker chaining
    (storyboard→timing→scriptwriter) re-walks automatically via existing mechanism.
    For target_stage="scriptwriter": runs ScriptwriterStage only.
    For target_stage="slides": runs SlidesDispatchStage only.

    Args:
        workdir: Active WorkdirManager for the current run.
        config: RunConfig for the current run.
        target_stage: One of "storyboard", "scriptwriter", "slides".
        feedback: Free-text instruction from the user (may be empty string).

    Raises:
        ValueError: If target_stage is not one of the valid feedback stages.
    """
    if target_stage not in _VALID_FEEDBACK_STAGES:
        raise ValueError(
            f"Unknown feedback stage: {target_stage!r}. "
            f"Expected one of: {sorted(_VALID_FEEDBACK_STAGES)}"
        )

    # Write feedback before touching done-markers (idempotency: crash between write
    # and unlink leaves feedback on disk, which is fine — stage reads + clears it).
    if feedback:
        workdir.write_feedback(target_stage, feedback)

    if target_stage == "storyboard":
        from avideo.stages.storyboard import StoryboardStage  # noqa: PLC0415
        workdir.done_marker("storyboard").unlink(missing_ok=True)
        workdir.invalidate_downstream("storyboard")
        run_stage(StoryboardStage(), workdir, config)

    elif target_stage == "scriptwriter":
        from avideo.stages.scriptwriter import ScriptwriterStage  # noqa: PLC0415
        workdir.done_marker("scriptwriter").unlink(missing_ok=True)
        workdir.invalidate_downstream("scriptwriter")
        run_stage(ScriptwriterStage(), workdir, config)

    elif target_stage == "slides":
        from avideo.stages.slides_dispatch import SlidesDispatchStage  # noqa: PLC0415
        workdir.done_marker("slides").unlink(missing_ok=True)
        workdir.invalidate_downstream("slides")
        run_stage(SlidesDispatchStage(), workdir, config)
```

Refactor `rerun_scriptwriter` and `rerun_slides` to delegate (pass feedback="" so
write_feedback is skipped by the `if feedback:` guard, preserving original behavior):

```python
def rerun_scriptwriter(workdir, config):
    rerun_with_feedback(workdir, config, "scriptwriter", feedback="")

def rerun_slides(workdir, config, theme_path=None):
    # theme_path is forwarded only when using SlidesDispatchStage directly.
    # For the feedback path, theme deletion is handled inside SlidesAutoStage.run().
    # Keep the existing body for the non-feedback path to avoid breaking theme_path callers:
    from avideo.stages.slides_dispatch import SlidesDispatchStage  # noqa: PLC0415
    workdir.done_marker("slides").unlink(missing_ok=True)
    workdir.invalidate_downstream("slides")
    run_stage(SlidesDispatchStage(theme_path), workdir, config)
```

Note: keep `rerun_slides` body as-is (with theme_path) since that param is irrelevant
to feedback (the SlidesAutoStage handles theme deletion internally when feedback present).
Only `rerun_scriptwriter` delegates cleanly.

Add tests to `tests/test_seed002_feedback.py` in `TestRerunWithFeedback`:
- one test per target_stage ("storyboard", "scriptwriter", "slides") verifying:
  write_feedback called, done_marker unlinked, invalidate_downstream called with correct stage,
  run_stage called with correct stage class instance.
- test that unknown stage raises ValueError.
- Use `mocker.patch.object(wm, "write_feedback")`, `mocker.patch.object(wm, "invalidate_downstream")`,
  `mocker.patch("avideo.ui.pipeline_ops.run_stage")`.
  </action>
  <verify>
    <automated>cd /Users/jaimeberdejosanchez/projects/auto-video-narrado && uv run pytest tests/test_seed002_feedback.py::TestRerunWithFeedback -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>
    All TestRerunWithFeedback tests pass. Existing pipeline_ops tests unaffected:
    uv run pytest tests/test_pipeline_ops.py -q
  </done>
</task>

<!-- ============================================================ -->
<!-- TASK 4: UI — phase_2_guion + phase_3_slides variation widget -->
<!-- ============================================================ -->

<task type="auto">
  <name>Task 4: UI — replace bare variation buttons with text_area + radio selectors</name>
  <files>
    src/avideo/ui/pages/phase_2_guion.py
    src/avideo/ui/pages/phase_3_slides.py
  </files>
  <action>
**phase_2_guion.py** — replace the SCR-03 section (lines 115–127):

Old code:
```python
with col_var:
    if st.button("Pedir variacion del guion", key="btn_variation"):
        from avideo.ui.pipeline_ops import rerun_scriptwriter  # noqa: PLC0415
        if "scr_edited_narrations" in st.session_state:
            del st.session_state["scr_edited_narrations"]
        config = _build_config(workdir)
        rerun_scriptwriter(workdir, config)
        st.rerun()
```

New code (replace col_var block):
```python
with col_var:
    st.markdown("**Pedir variación del guion**")
    variation_target = st.radio(
        "¿Qué quieres cambiar?",
        options=["Afinar tono / redacción", "Cambiar nº de slides / estructura"],
        key="scr_variation_target",
        horizontal=True,
    )
    variation_text = st.text_area(
        "Instrucción (opcional — qué cambiar exactamente)",
        key="scr_variation_text",
        placeholder='Ej: "tono más cercano y sin tecnicismos" / "cambia el número de slides a 4"',
        height=80,
    )
    if st.button("Aplicar variación", key="btn_variation"):
        from avideo.ui.pipeline_ops import rerun_with_feedback  # noqa: PLC0415

        if "scr_edited_narrations" in st.session_state:
            del st.session_state["scr_edited_narrations"]

        target_stage = (
            "storyboard"
            if variation_target == "Cambiar nº de slides / estructura"
            else "scriptwriter"
        )
        config = _build_config(workdir)
        rerun_with_feedback(workdir, config, target_stage, variation_text.strip())
        st.rerun()
```

**phase_3_slides.py** — replace the SLD-02 "Pedir variación de slides" button
(lines 186–191 in `_render_auto`):

Old code:
```python
if st.button("Pedir variación de slides", key="btn_slides_variation"):
    from avideo.ui.pipeline_ops import rerun_slides  # noqa: PLC0415
    workdir.invalidate_downstream("slides")  # clears verify too
    rerun_slides(workdir, config)
    st.rerun()
```

New code:
```python
st.markdown("**Pedir variación de diapositivas**")
slides_variation_target = st.radio(
    "¿Qué quieres cambiar?",
    options=[
        "Estilo visual / colores",
        "Añadir imágenes (próximamente — SEED-001)",
    ],
    key="sld_variation_target",
    horizontal=True,
)
slides_variation_text = st.text_area(
    "Instrucción (opcional)",
    key="sld_variation_text",
    placeholder='Ej: "esquema de color azul" / "más contraste en los títulos"',
    height=80,
)
is_pexels_option = slides_variation_target.startswith("Añadir imágenes")
if is_pexels_option:
    st.info("La opción 'Añadir imágenes' estará disponible en SEED-001.")
if st.button(
    "Aplicar variación",
    key="btn_slides_variation",
    disabled=is_pexels_option,
):
    from avideo.ui.pipeline_ops import rerun_with_feedback  # noqa: PLC0415

    rerun_with_feedback(workdir, config, "slides", slides_variation_text.strip())
    st.rerun()
```

No automated tests for UI (Streamlit widgets require browser). Manual smoke check
in the verify step below.
  </action>
  <verify>
    <automated>cd /Users/jaimeberdejosanchez/projects/auto-video-narrado && uv run pytest tests/ -x -q --ignore=tests/test_anthropic_integration.py --ignore=tests/test_elevenlabs.py --ignore=tests/test_whisperx_integration.py 2>&1 | tail -30</automated>
  </verify>
  <done>
    Full test suite passes (419+ tests green). UI pages import cleanly (no Streamlit errors
    at import time). The variation section in Fase 2 and Fase 3 uses text_area + radio widgets.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user text_area → feedback.json | Free-text from user is written verbatim to disk and injected into LLM prompts |
| feedback.json → LLM prompt | Feedback text is appended inside a delimited block; not interpreted as system instructions |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S002-01 | Tampering | workdir/feedback.json | accept | File lives in user-controlled workdir alongside other checkpoints; no new attack surface vs. existing JSON files |
| T-S002-02 | Information Disclosure | LLM prompt injection via feedback text | mitigate | Feedback is appended as a clearly delimited block at the end of the user prompt, not the system prompt; existing T-02-06 untrusted-reference framing pattern covers context text — apply same discipline to feedback blocks |
| T-S002-03 | Elevation of Privilege | Malicious feedback overrides system prompt | accept | Feedback injected in user turn only (system prompt unchanged); Claude's system prompt is the authoritative instruction layer; user turn additions cannot override tool-use constraints |
</threat_model>

<verification>
Run the full suite after all tasks to confirm 419+ tests pass and no regressions:

```bash
cd /Users/jaimeberdejosanchez/projects/auto-video-narrado
uv run pytest tests/ -q \
  --ignore=tests/test_anthropic_integration.py \
  --ignore=tests/test_elevenlabs.py \
  --ignore=tests/test_whisperx_integration.py \
  2>&1 | tail -10
```

Expected: all tests pass, `test_seed002_feedback.py` adds new passing tests.
</verification>

<success_criteria>
- FeedbackCheckpoint model exists in src/avideo/models/feedback.py with `entries: dict[str, str] = {}`
- WorkdirManager has write_feedback / read_feedback / clear_feedback (lazy imports, silent no-op on missing file)
- storyboard._build_prompts, scriptwriter._build_prompts, slides_auto.resolve_theme all accept optional `feedback` param; include the delimited block only when non-None and non-empty
- Each stage reads and clears its own feedback entry in run() (consumed-once)
- rerun_with_feedback in pipeline_ops handles "storyboard", "scriptwriter", "slides"; raises ValueError for unknown stages
- Fase 2 Guion variation section: st.radio (tono vs nº slides) + st.text_area + "Aplicar variación" button
- Fase 3 Diapositivas variation section: st.radio (visual/colores + disabled Añadir imágenes option) + st.text_area + disabled-when-pexels button
- All 419 existing tests still pass
- test_seed002_feedback.py covers: workdir helpers round-trip, prompt injection present/absent, dispatcher routing x3 stages, consumed-once lifecycle
</success_criteria>

<output>
After completion, create `.planning/quick/260531-npu-seed-002-steerable-variation/260531-npu-SUMMARY.md`
following the standard summary template.
</output>
