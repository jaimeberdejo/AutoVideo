---
seed: SEED-002
planted: 2026-05-31
planted_during: v2.0.0 UAT (Studio browser testing)
trigger_when: planning improvements to the Guion (Fase 2) / Diapositivas (Fase 3) variation loops
status: planted
---

# SEED-002: Steerable "Pedir variación" (free-text instruction)

Today "Pedir variación" in Fase 2 (Guion) and Fase 3 (Diapositivas) re-generates
BLINDLY — the user can't say *what* to change. Add a free-text instruction so the
user steers the regeneration.

## Desired behaviour (from owner, 2026-05-31)
- **Fase 2 (Guion):** a text box like "¿Qué quieres cambiar?" — e.g. "tono más
  cercano", "menos tecnicismos", **"cambia el número de slides a 4"**.
- **Fase 3 (Diapositivas):** e.g. "esquema de color azul", "hazlas más visuales
  con imágenes".

## Design nuances (do NOT ignore)
1. **Routing by intent:** tone/wording → scriptwriter (cheap, current path). But
   **slide count / structure → storyboard** (re-run storyboard→timing→scriptwriter,
   which breaks the SCR-03 "only scriptwriter" optimization). Color/visual style →
   theme.yaml / `visual_type` / slides render. Decide: one box that re-runs the
   right stage(s) based on a stage selector, vs. per-target boxes.
2. **Plumbing:** the instruction must reach the LLM prompt. Options: add an optional
   `variation_feedback: str` to RunConfig (or a small `feedback.json` checkpoint the
   stage reads), and inject it into the scriptwriter / storyboard / slides prompt
   templates as an extra "user feedback" block.
3. **"más visual con imágenes"** intersects [[SEED-001]] (Pexels image source) —
   coordinate the two.
4. Keep it idempotent + invalidate downstream after a steered re-run.

## Scope checklist
- UI: `st.text_area` in phase_2_guion.py + phase_3_slides.py variation sections.
- Backend: feedback param threaded into scriptwriter/storyboard/slides prompts.
- pipeline_ops: rerun_scriptwriter / rerun_slides accept feedback; choose which
  stage(s) to re-run for "slide count" vs "tone" vs "visual".
- Tests: prompt includes feedback; routing re-runs correct stage(s).
