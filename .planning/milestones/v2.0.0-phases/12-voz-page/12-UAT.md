---
status: verified
phase: 12-voz-page
started: 2026-07-01T11:48:00Z
updated: 2026-07-01T12:31:00Z
---

## Tests

### 1. Three provider options selectable
expected: ElevenLabs, OpenAI Audio, Grabaciones propias all selectable via radio; provider-specific config widgets appear (Voice ID / OpenAI voice+model / none).
result: PASS — verified live for all 3 radio options and their config widgets.

### 2. ElevenLabs synthesis + real external-API error handling
expected: Clicking "Generar voz" launches synthesis via the bridge; success shows per-slide `st.audio`; failure shows a clear, actionable error.
result: PASS (after 2 fixes) — real ElevenLabs call correctly failed with a real account-tier error (free tier cannot use library voices via the API, HTTP 402). Found and fixed 2 bugs:
  - The raw exception (full HTTP headers + status_code + body dump) was shown verbatim to the user — added `bridge.format_stage_error()` to extract just the human-readable `body.detail.message`.
  - The "Generar voz" button stayed permanently disabled after the error (its `disabled=` value is computed once per full Streamlit script rerun, but the 2s polling fragment that shows the error never forces a full rerun) — user had no way to retry without a manual browser refresh. Fixed with a consumed-once rerun-on-error flag.

### 3. OpenAI Audio synthesis (TTS + whisper-1 STT round-trip)
expected: OpenAI TTS produces per-slide MP3s; since OpenAI TTS returns no timestamps, a mandatory whisper-1 STT round-trip produces word-level timestamps indistinguishable in format from ElevenLabs'.
result: PASS — verified live end-to-end: 5 real MP3s generated, `.voice.done` and `.align.done` both written, `timings.json` populated with real word-level budgets, all 5 `st.audio` previews rendered playable.

### 4. Gate unlocks only when all slides have audio + valid timestamps
expected: "Aprobar y continuar" stays disabled until every slide has audio and timings.json has word-level data.
result: PASS — verified: gate stayed disabled during synthesis/alignment, enabled only once both were done.

## Not exercised in this session
- "Grabaciones propias" (own-recording upload) path, including non-destructive audio enhancement (denoise+normalize) before/after preview and "Adoptar". Time-boxed in favor of exercising the OpenAI path through to a complete assembled video.

## Summary

total: 4
passed: 4
issues: 0 (2 UX bugs found — fixed, see main report)
pending: 0
skipped: 1 (own-recording upload + enhance path)
