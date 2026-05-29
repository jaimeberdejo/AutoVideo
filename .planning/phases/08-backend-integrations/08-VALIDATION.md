---
phase: 8
slug: backend-integrations
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (+ pytest-mock) |
| **Config file** | pyproject.toml ([tool.pytest]) |
| **Quick run command** | `uv run pytest -q tests/test_voice_openai.py tests/test_audio_enhance.py tests/test_ffmpeg_music.py` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~25–40 seconds (full suite, all external calls mocked) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched module
- **After every plan wave:** Run `uv run pytest -q` (full suite — must stay ≥303 green + new tests)
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** ~40 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _filled by planner_ | — | — | VOZ-02/VOZ-03/EXT-02/EXT-03 | — | no shell=True; API keys from env | unit | `uv run pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_voice_openai.py` — mock `avideo.integrations.openai._get_client`; assert per-slide synthesis + whisper-1 word-timestamp round-trip → UnifiedTimings (VOZ-02)
- [ ] `tests/test_audio_enhance.py` — mock ffmpeg subprocess; assert `afftdn`+`loudnorm` filter string, original file untouched, alignment uses original (VOZ-03)
- [ ] `tests/test_ffmpeg_music.py` — assert `build_music_mix_args()` emits `amix=inputs=2:normalize=0`, explicit `volume=`, `sidechaincompress`, `afade` with ffprobe-measured duration; single loudnorm (EXT-02, EXT-03)
- [ ] Reuse existing `tests/conftest.py` fixtures (mirror `test_voice_elevenlabs.py` + `test_assemble.py` patterns)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| whisper-1 Spanish word-timestamp quality | VOZ-02 | Requires real audio + API; subjective sync quality | Run a real OpenAI TTS slide end-to-end, burn subs, eyeball drift; fallback WhisperX if poor |
| Perceived music ducking / no pumping | EXT-02/03 | Subjective audio quality | Assemble a real clip with music, listen for narration clarity + no double-norm pumping |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
