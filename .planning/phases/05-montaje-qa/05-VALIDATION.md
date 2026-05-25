---
phase: 5
slug: montaje-qa
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-mock |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| **Quick run command** | `uv run pytest tests/test_assemble.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | unit <1s; guarded real-ffmpeg smoke ~3-5s |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_assemble.py -x -q`
- **After every plan wave:** `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** <5s

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| ASMB-01 | real ffprobe durations drive slide length | unit (mock probe) | `uv run pytest tests/test_assemble.py -k probe_drives_duration -x -q` | ❌ W0 | ⬜ |
| ASMB-02 | crossfade offsets + XF=0 concat + clamp | unit (pure) | `uv run pytest tests/test_assemble.py -k crossfade -x -q` | ❌ W0 | ⬜ |
| ASMB-03 | output is 1920×1080 yuv420p | smoke (guarded) | `uv run pytest tests/test_assemble.py -k smoke_dimensions -x -q` | ❌ W0 | ⬜ |
| QA-01 | duration deviation vs target | unit (pure) | `uv run pytest tests/test_assemble.py -k deviation -x -q` | ❌ W0 | ⬜ |
| QA-02 | two-pass loudnorm parse + apply args | unit (parse) + smoke (≈ -16 LUFS) | `uv run pytest tests/test_assemble.py -k loudnorm -x -q` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Pure (mock-free, no ffmpeg):** `crossfade_offsets`, `expected_total`, crossfade clamping (`min(XF,prev,next)`, ≤0→hard cut), `parse_loudnorm_json(stderr)`, duration deviation, `build_filtergraph(...)` substrings (`scale=1920:1080`, `setsar=1`, `xfade=`/`concat=`), `build_assemble_args(...)` (list[str], `-movflags +faststart` present, single filter_complex element, NO shell=True), path dispatch (1 slide / N / XF=0).

**Mocked:** `subprocess.run` (ffmpeg/ffprobe) → fake CompletedProcess + canned loudnorm stderr; `probe_duration` → fixed floats; AssembleStage end-to-end with placeholder PNG/audio files.

**Real-ffmpeg smoke (exactly one, guarded by `shutil.which("ffmpeg")`):** Pillow tiny PNGs + lavfi sine audios → real assemble → ffprobe asserts width==1920, height==1080, pix_fmt==yuv420p, abs(duration - expected_total) < 0.1 (±1 frame). Mirrors `tests/test_slides_render.py` skip pattern.

**Verified pitfalls (from RESEARCH empirical spike):** (1) `-c:v copy` on loudnorm pass-2 drops `+faststart` → must re-add; (2) negative xfade offset on short slides fails silently → clamp `eff_XF = min(XF, prev, next)`, ≤0 → hard cut.

---

## Wave 0 Requirements

- [ ] `tests/test_assemble.py` — ASMB-01/02/03, QA-01/02 (pure unit + one guarded smoke)
- [ ] `tests/conftest.py` — canned loudnorm pass-1 stderr fixture; tiny-PNG + tiny-audio generator helper for smoke
- [ ] No framework install — pytest/pytest-mock/pillow already in dev deps

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Final video plays correctly, A/V sync, crossfade looks right | ASMB-01/02 | Subjective playback judgment | Run full pipeline; play `workdir/output.mp4`; confirm slides match narration, transitions smooth |
| Burned subtitles render legibly (--burn-subs) | ASMB-02 | Visual | Run with `--burn-subs`; confirm subs visible/legible over slides |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
