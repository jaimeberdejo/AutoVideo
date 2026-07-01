# Phase 10: Contenido Page - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** Smart-discuss auto-accepted (autonomous; built on Phase 9 shell + 09-UI-SPEC contract)

<domain>
## Phase Boundary

Implement the Fase 1 (Contenido) wizard page on top of the Phase 9 shell: topic + target-duration input with validation, a choice between user-provided bullets or Claude auto-generation from the topic, and an interactive editor where the user reviews/edits/approves bullets. On approval it persists `workdir/bullets.yaml` and sets the phase gate so the shell can advance. Covers CNT-01, CNT-02, CNT-03. Reuse existing pipeline pieces (bullets loader/`BulletsInput`, the anthropic client/`call_structured`); add a small "generate bullets from topic" helper if one doesn't already exist. No downstream phases here.

</domain>

<decisions>
## Implementation Decisions

### Page contract (replaces the Phase 9 placeholder for phase 1)
- Replace `src/avideo/ui/pages/phase_1_contenido.py`'s placeholder body with the real page; keep its `render(workdir: WorkdirManager) -> bool` signature (returns gate_met).
- Inputs: `st.text_input`/`st.text_area` for tema (topic), `st.number_input` for duración (seconds) with validation (min/max reasonable bounds, e.g. 15s–1800s; surface a clear error if out of range — CNT-01).
- Source choice (CNT-02): `st.radio` — "Escribir mis bullets" vs "Generar desde el tema". Both routes converge on the SAME editor.

### Bullet generation (CNT-02)
- Add a helper (e.g. `stages/bullets_gen.py` or a function in the content/storyboard area) `generate_bullets(topic, duration, n=...) -> list[str]` using the existing anthropic `call_structured` + a Pydantic schema. Run it via the PipelineBridge or a simple synchronous `st.status` call (generation is fast, single LLM call) — show a spinner, don't freeze indefinitely.
- Generated bullets land in the editor for review (never auto-approved).

### Editor + persistence (CNT-03)
- Interactive editor: `st.data_editor` (dynamic rows: add/delete/reorder) bound to the bullets list, OR a multiline `st.text_area` (one bullet per line) — choose `st.data_editor` with `num_rows="dynamic"` for add/delete.
- On "Aprobar y continuar" (the shell's gate), write `workdir/bullets.yaml` via the existing bullets schema/`BulletsInput` serialization (atomic write through WorkdirManager). The CLI pipeline's `bullets: Path` contract must be satisfied — `bullets.yaml` is the same format `avideo generate --bullets` consumes.
- The RunConfig in session_state is updated with topic/duration so later phases inherit them.
- Editing bullets after approval (back-nav) invalidates downstream (handled by the shell's invalidate_downstream).

### Claude's Discretion
- Exact bullet-count heuristic for generation (derive a sensible default from duration), schema field names, editor widget polish, validation bounds.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BulletsInput` + `load_bullets` (bullets.yaml schema/loader from Phase 2) — reuse for serialization/validation.
- `integrations/anthropic.py` `call_structured` (tool-use → Pydantic) — reuse for bullet generation.
- Phase 9: `ui/state.py` (RunConfig-from-inputs, session model), `ui/pages/phase_1_contenido.py` (placeholder to replace), WorkdirManager (atomic write), PipelineBridge.

### Established Patterns
- Pydantic v2; atomic writes; typed+docstrings. Unit-test the pure logic (generate_bullets with mocked anthropic; bullets.yaml serialization round-trip; duration validation). Page rendering is manual-verify.

### Integration Points
- `ui/pages/phase_1_contenido.py`; new bullets-generation helper; `workdir/bullets.yaml` output consumed by the existing storyboard stage in Phase 11.

</code_context>

<specifics>
## Specific Ideas

Persist `bullets.yaml` in the EXACT format `avideo generate --bullets` already consumes (so the engine is unchanged). Generation is one Claude call — keep it snappy with a spinner, not the full thread bridge (the bridge is for long render/TTS/assembly stages).

</specifics>

<deferred>
## Deferred Ideas

- Guion/slides/voz/extras pages (Phases 11–13). Image/screenshot bullet items were removed from scope (old Phases 8–9) — bullets are plain text here.

</deferred>
