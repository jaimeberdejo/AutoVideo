"""ScriptwriterStage — whole-script Claude call with ONE calibration retry.

Design decisions implemented here:
- D-09: Whole-script single call — Claude sees all slides at once for coherence and
  natural transitions. Per-slide word budgets are explicit in the prompt.
- D-10: ONE calibration retry (≤2 total calls): if _max_drift > 0.25 after the first
  call, send a single correction prompt; accept whatever returns — NO loop.
- D-11: Natural spoken tone in the configured language (default 'es'); tool-use
  forced via call_structured (D-03 re-used from storyboard).
- Pitfall 7: max_tokens scaled generously — max(8192, total_words * 8) capped at 60k.
- T-02-10: API key never logged; lazy client from integrations/anthropic.py.
- T-02-11: Calibration strictly ≤2 calls; max_tokens bounded under 64k ceiling.

Mock point: ``call_structured`` is imported at module scope so tests can patch
``avideo.stages.scriptwriter.call_structured`` without touching the integration layer.

stage_name = "scriptwriter" and checkpoint_name = "script" match the Phase-1
ScriptwriterStub — checkpoint file remains script.json for downstream phases.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from avideo.integrations.anthropic import call_structured  # noqa: F401 — module-scope mock point
from avideo.models.script import ScriptOutput
from avideo.models.storyboard import StoryboardOutput
from avideo.models.timing import TimingOutput
from avideo.stages.base import CheckpointMixin

if TYPE_CHECKING:
    from avideo.models.config import RunConfig
    from avideo.utils.workdir import WorkdirManager

# ---------------------------------------------------------------------------
# Token sizing constants (Pitfall 7)
# ---------------------------------------------------------------------------

#: Minimum max_tokens for any scriptwriter call.
_MIN_MAX_TOKENS: int = 8192

#: Hard ceiling — Sonnet 4.6 allows 64k output tokens.
_HARD_CEILING: int = 60_000

#: Approximate tokens per output word (output tokens include whitespace/markup overhead).
_TOKENS_PER_WORD: int = 8


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Eres un experto guionista de locución para vídeos de presentación narrada.

Tu tarea: escribir la narración completa de la presentación, slide por slide, \
en {language}. El texto debe sonar natural cuando se lee en voz alta, como si \
fuera una locución profesional — no una lista de puntos leídos, sino un discurso \
fluido y cohesionado que conecte las ideas de un slide al siguiente.

Restricciones importantes:
- Escribe EXACTAMENTE una narración por slide (ni más ni menos).
- Ajusta la longitud de cada narración al presupuesto de palabras indicado para \
  ese slide (la cifra entre paréntesis es la cantidad objetivo de palabras).
- No uses lenguaje de presentación ("Como podemos ver en este slide…"); en su \
  lugar, habla directamente del contenido.
- El idioma de salida DEBE ser: {language}.

Usa la herramienta emit_script para devolver la narración estructurada. \
No incluyas texto fuera de la llamada a la herramienta.
"""

_USER_PROMPT_TEMPLATE = """\
Presentación: {n_slides} slides, duración total ≈ {total_seconds}s

Por favor escribe la narración completa de la siguiente presentación. \
Cada slide incluye su título, bullets de contenido, y el presupuesto de palabras \
objetivo entre paréntesis.

{slides_section}
"""

_SLIDE_BLOCK_TEMPLATE = """\
--- Slide {idx} (objetivo: {budget} palabras) ---
Título: {title}
Bullets:
{bullets_list}
"""

_CORRECTION_PROMPT_TEMPLATE = """\
Presentación: {n_slides} slides, duración total ≈ {total_seconds}s

{slides_section}

Guion anterior (para tu referencia — mantén el contenido y el tono, solo \
ajusta la longitud donde se indique):
{prev_narrations}

El guion anterior no cumple con los presupuestos de palabras en algunas slides. \
Por favor, ajusta SOLO la longitud de las narraciones fuera de rango y devuelve \
el guion COMPLETO de nuevo (las {n_slides} slides, no solo las corregidas), \
manteniendo el mismo contenido y sin inventar temas nuevos.

Revisión necesaria:
{slide_notes}

Mantén el mismo tono natural y cohesión. Usa emit_script para la respuesta.
"""

_TOOL_DESCRIPTION = (
    "Emit the complete narration script as structured JSON. "
    "Each slide must have a slide_index (int) and a narration (str) — "
    "natural spoken prose calibrated to the word budget for that slide."
)

# SEED-002: Feedback block delimiter — appended to user prompt when feedback is present.
_FEEDBACK_BLOCK = """\

--- Instrucción del usuario (prioritaria) ---
{feedback}
--- Fin de instrucción ---
"""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _max_drift(script: ScriptOutput, budgets: list[int]) -> float:
    """Return the maximum fractional word-count drift across all slides.

    drift_i = abs(actual_words_i - budget_i) / budget_i

    Args:
        script: The ScriptOutput to evaluate.
        budgets: List of per-slide word budgets (same length as script.slides).

    Returns:
        Maximum drift as a float in [0, ∞). Returns 0.0 if no slides or all
        budgets are zero (cannot compute drift).
    """
    if not script.slides or not budgets:
        return 0.0

    max_d = 0.0
    for slide, budget in zip(script.slides, budgets):
        if budget == 0:
            continue  # cannot compute drift for zero budget; skip
        actual = len(slide.narration.split())
        drift = abs(actual - budget) / budget
        if drift > max_d:
            max_d = drift
    return max_d


def _build_prompts(
    storyboard: StoryboardOutput,
    timings: TimingOutput,
    language: str,
    feedback: str | None = None,
) -> tuple[str, str]:
    """Build (system, user) prompts for the whole-script call.

    Args:
        storyboard: StoryboardOutput with slide titles + bullets.
        timings: TimingOutput with per-slide word_budget.
        language: Target language code (e.g. "es", "en").
        feedback: Optional free-text user instruction (SEED-002).  When
                  non-None and non-empty, a delimited block is appended to
                  the user prompt.  ``None`` produces identical output to the
                  pre-SEED-002 behaviour (backward compatible).

    Returns:
        (system_prompt, user_prompt) strings.
    """
    system = _SYSTEM_PROMPT.format(language=language)

    budget_map = {t.slide_index: t.word_budget for t in timings.slides}
    total_seconds = timings.total_seconds

    slide_blocks: list[str] = []
    for i, slide in enumerate(storyboard.slides):
        budget = budget_map.get(i, 0)
        bullets_list = "\n".join(f"  - {b}" for b in slide.bullets)
        block = _SLIDE_BLOCK_TEMPLATE.format(
            idx=i,
            budget=budget,
            title=slide.title,
            bullets_list=bullets_list,
        )
        slide_blocks.append(block)

    user = _USER_PROMPT_TEMPLATE.format(
        n_slides=len(storyboard.slides),
        total_seconds=int(total_seconds),
        slides_section="\n".join(slide_blocks),
    )

    # SEED-002: append feedback block when present (consumed-once — cleared after use)
    if feedback:
        user += _FEEDBACK_BLOCK.format(feedback=feedback)

    return system, user


def _correction_prompt(
    storyboard: StoryboardOutput,
    timings: TimingOutput,
    prev_script: ScriptOutput,
    budgets: list[int],
) -> str:
    """Build the correction prompt highlighting off-budget slides.

    The correction call is a fresh, single-turn ``call_structured`` invocation
    (no conversation history is threaded through) — so this prompt must be
    fully self-contained. It re-includes the original slide titles/bullets
    AND the previous narrations; omitting them causes the model to lose all
    topic context and hallucinate an unrelated generic script (observed live
    during v2.0.0 browser UAT: a 60s/6-slide carbon-footprint presentation
    came back as a 4-slide generic "innovation" script after the retry).

    Args:
        storyboard: StoryboardOutput with slide titles + bullets (for re-grounding).
        timings: TimingOutput with per-slide word_budget.
        prev_script: The previous ScriptOutput to correct.
        budgets: Per-slide word budgets.

    Returns:
        User-turn correction prompt string.
    """
    notes: list[str] = []
    for slide, budget in zip(prev_script.slides, budgets):
        if budget == 0:
            continue
        actual = len(slide.narration.split())
        drift = abs(actual - budget) / budget
        if drift > 0.25:
            direction = "corta" if actual < budget else "larga"
            notes.append(
                f"  Slide {slide.slide_index}: tiene {actual} palabras, objetivo {budget} "
                f"(demasiado {direction})"
            )

    if not notes:
        notes.append("  (todas las slides son correctas — devuelve el mismo guion)")

    budget_map = {t.slide_index: t.word_budget for t in timings.slides}
    slide_blocks: list[str] = []
    for i, slide in enumerate(storyboard.slides):
        budget = budget_map.get(i, 0)
        bullets_list = "\n".join(f"  - {b}" for b in slide.bullets)
        slide_blocks.append(
            _SLIDE_BLOCK_TEMPLATE.format(idx=i, budget=budget, title=slide.title, bullets_list=bullets_list)
        )

    prev_narrations = "\n".join(
        f"  Slide {s.slide_index}: {s.narration}" for s in prev_script.slides
    )

    return _CORRECTION_PROMPT_TEMPLATE.format(
        n_slides=len(storyboard.slides),
        total_seconds=int(timings.total_seconds),
        slides_section="\n".join(slide_blocks),
        prev_narrations=prev_narrations,
        slide_notes="\n".join(notes),
    )


def _size_max_tokens(budgets: list[int]) -> int:
    """Compute a generous max_tokens for the scriptwriter call (Pitfall 7).

    Args:
        budgets: Per-slide word budgets.

    Returns:
        max_tokens: max(8192, total_words * 8), capped at _HARD_CEILING.
    """
    total_words = sum(budgets)
    tokens = max(_MIN_MAX_TOKENS, total_words * _TOKENS_PER_WORD)
    return min(tokens, _HARD_CEILING)


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


class ScriptwriterStage(CheckpointMixin):
    """Real scriptwriter stage replacing Phase-1 ScriptwriterStub.

    Reads storyboard.json + timings.json, generates a whole-script narration
    via a single Claude call (D-09), and optionally performs ONE calibration
    retry if the output drifts >25% from per-slide word budgets (D-10).

    At most 2 call_structured calls are made — no infinite loop (T-02-11).

    stage_name = "scriptwriter" and checkpoint_name = "script" preserve the
    workdir contract from the Phase-1 ScriptwriterStub.
    """

    stage_name: str = "scriptwriter"

    @property
    def checkpoint_name(self) -> str:  # type: ignore[override]
        """Override: checkpoint filename is 'script' (→ workdir/script.json)."""
        return "script"

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> ScriptOutput:
        """Generate a full narration script using the Anthropic API.

        Steps:
        1. Read storyboard.json + timings.json.
        2. Build whole-script prompts with explicit per-slide word budgets.
        3. Call call_structured → ScriptOutput (first call).
        4. If _max_drift > 0.25: send ONE correction call; accept result regardless.
        5. Return the final ScriptOutput (no further drift check, no loop).

        Args:
            workdir: WorkdirManager for reading storyboard + timings checkpoints.
            config: RunConfig with language, wpm.

        Returns:
            A validated ScriptOutput with one SlideScript per slide and
            language == config.language.
        """
        # Step 1: Read checkpoints
        sb: StoryboardOutput = workdir.read_checkpoint("storyboard", StoryboardOutput)  # type: ignore[assignment]
        tm: TimingOutput = workdir.read_checkpoint("timings", TimingOutput)  # type: ignore[assignment]

        budgets = [t.word_budget for t in tm.slides]
        max_tok = _size_max_tokens(budgets)

        # SEED-002: read optional user feedback before building prompts
        feedback = workdir.read_feedback("scriptwriter")

        # Step 2: Build prompts (feedback injected when present — backward compat otherwise)
        system, user = _build_prompts(sb, tm, config.language, feedback=feedback)

        # Step 3: First call
        result: ScriptOutput = call_structured(
            system=system,
            user=user,
            tool_name="emit_script",
            tool_description=_TOOL_DESCRIPTION,
            output_model=ScriptOutput,
            max_tokens=max_tok,
        )

        # SEED-002: consumed-once — clear feedback after first successful call_structured
        # (before the calibration retry check so a crash during retry still leaves
        # feedback consumed — the retry uses the same prompts anyway)
        workdir.clear_feedback("scriptwriter")

        # Step 4: ONE calibration retry if drift > 25% (D-10 — NO loop)
        if _max_drift(result, budgets) > 0.25:
            correction_user = _correction_prompt(sb, tm, result, budgets)
            result = call_structured(
                system=system,
                user=correction_user,
                tool_name="emit_script",
                tool_description=_TOOL_DESCRIPTION,
                output_model=ScriptOutput,
                max_tokens=max_tok,
            )
            # Accept regardless — no further check, no third call (D-10)

        return result
