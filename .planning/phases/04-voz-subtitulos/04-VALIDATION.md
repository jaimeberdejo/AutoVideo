---
phase: 4
slug: voz-subtitulos
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest>=8.0 + pytest-mock>=3.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| **Quick run command** | `uv run pytest tests/test_subtitles.py tests/test_elevenlabs.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | <2s (all network/audio/model calls mocked) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_subtitles.py tests/test_elevenlabs.py -x -q` (pure logic, <2s)
- **After every plan wave:** `uv run pytest -q` (full suite)
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** <2 seconds

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| VOICE-01 | convert_with_timestamps per slide → mp3 + timings | unit (mock SDK) | `uv run pytest tests/test_voice_elevenlabs.py -x -q` | ❌ W0 | ⬜ |
| VOICE-02 | strictly-increasing validation + retry≤3 + fallback | unit (pure + mock) | `uv run pytest tests/test_elevenlabs.py -k increasing -x -q` | ❌ W0 | ⬜ |
| VOICE-03 | autodetect WAV vs record; export segmented script | unit (mock sounddevice/soundfile) | `uv run pytest tests/test_voice_record.py -x -q` | ❌ W0 | ⬜ |
| ALIGN-01 | whisperx align → word_segments → UnifiedTimings | unit (mock whisperx) | `uv run pytest tests/test_align.py -x -q` | ❌ W0 | ⬜ |
| ALIGN-02 | elevenlabs mode: align does NOT run (idempotent no-op) | unit | `uv run pytest tests/test_align.py -k elevenlabs_skip -x -q` | ❌ W0 | ⬜ |
| SUB-01 | UnifiedTimings → SRT (comma) + VTT (dot, WEBVTT) | unit (PURE) | `uv run pytest tests/test_subtitles.py -x -q` | ❌ W0 | ⬜ |
| SUB-02 | burn_subs flag registered; Phase 4 does NOT burn | unit | `uv run pytest tests/test_subtitles.py -k burn -x -q` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Mocked vs pure:**
- **Mocked:** ElevenLabs `convert_with_timestamps` (patch at stage module scope; response has `.audio_base64` + `.alignment.character_start_times_seconds`), WhisperX `load_model`/`align`, sounddevice `rec`/`wait` + soundfile `write`.
- **Pure (no mock):** strictly-increasing validation; cue segmentation (~42 chars, ≤2 lines, ≤5s, CPS cap); SRT/VTT serialization (comma vs dot, indices, WEBVTT header); WAV autodetection (tmp_path).

**Critical correction from RESEARCH:** ElevenLabs 2.x returns `character_start_times_seconds` / `character_end_times_seconds` (SECONDS), not the old `*_ms`. Validation + decode must read `_seconds`.

---

## Wave 0 Requirements

- [ ] `tests/test_subtitles.py` — SUB-01/SUB-02 (PURE: SRT/VTT format, cue segmentation, CPS)
- [ ] `tests/test_elevenlabs.py` — VOICE-02 (increasing validation + retry; mock SDK)
- [ ] `tests/test_voice_elevenlabs.py` — VOICE-01 (mp3 written, UnifiedTimings)
- [ ] `tests/test_voice_record.py` — VOICE-03 (autodetect + mock recording)
- [ ] `tests/test_align.py` — ALIGN-01/ALIGN-02 (mock whisperx; skip in elevenlabs)
- [ ] `tests/conftest.py` additions — fake ElevenLabs response, fake whisperx word_segments, WorkdirManager in tmp_path
- [ ] Deps: `uv add elevenlabs`; record-mode heavy deps (whisperx/torch/sounddevice) as optional extra; pin torch 2.5.1 (WhisperX VAD weights_only pitfall)

*(pytest + pytest-mock already in dev group — no framework install.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real ElevenLabs audio quality | VOICE-01 | Needs ELEVENLABS_API_KEY + subjective audio judgment | Run `--voice elevenlabs` with a key; listen to `workdir/audio/slide_*.mp3` |
| Real WhisperX alignment on recorded audio | ALIGN-01 | Needs real audio + model download | Run `--voice record` with sample wavs; inspect word timings |
| Live mic recording | VOICE-03 | Hardware/interactive | Run record mode, speak, confirm slide_XX.wav saved |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 2s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
