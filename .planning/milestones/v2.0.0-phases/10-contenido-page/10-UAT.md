---
status: verified
phase: 10-contenido-page
started: 2026-07-01T11:48:00Z
updated: 2026-07-01T12:31:00Z
---

## Tests

### 1. Topic + duration input with validation
expected: User can type a topic and a duration (mm:ss or seconds); invalid/out-of-range durations are rejected with a clear message.
result: PASS — verified live. "1:00" parsed to "Duración: 1:00 (60 s)"; field accepts mm:ss and raw seconds.

### 2. Bullets: write-your-own path
expected: User can write bullets manually in an interactive editor (add/edit/remove rows), see a live count, and approve.
result: PASS — verified live with a real topic (small-business carbon footprint tracking, 5 bullets). The bullet grid is a Streamlit `st.data_editor` rendered on `<canvas>` (glide-data-grid) — no accessible per-cell DOM elements, so automation requires coordinate-based double-click + type, not role/selector-based interaction. Noted as a testability limitation, not a functional bug. One bullet was observed with markdown/plain unicode text (´huella de carbono´) rendering correctly.

### 3. Approve → persists bullets.yaml + context.json, advances wizard
expected: Approving writes `workdir/bullets.yaml` (CLI-compatible format) and unblocks the footer "Aprobar y continuar" gate.
result: PASS — verified `bullets.yaml` and `context.json` on disk matched the exact approved title/bullets after each approval (including after a directed-variation edit).

## Not exercised in this session
- "Generar desde el tema (Claude)" (auto-generate bullets from topic) — radio option present and selectable but not clicked through to completion (time-boxed; the manual-bullets path was prioritized since it was needed for every other phase downstream).

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 1 (auto-generate-bullets path)
