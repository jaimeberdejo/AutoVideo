# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.60.0 — MVP Pipeline

**Shipped:** 2026-05-29
**Phases:** 7 | **Plans:** 18 | **Tasks:** 22 | **Commits:** 142

### What Was Built
- Pipeline `avideo generate` end-to-end: context → storyboard → timing → scriptwriter → slides → verify → voice → align → subs → assemble.
- Tres modos de slides (`auto` HTML/Playwright, `hybrid`, `manual`) y dos modos de voz (`elevenlabs` con timestamps, `record` con WhisperX), con verificador Claude Vision.
- Montaje FFmpeg (duraciones reales por ffprobe, crossfade, loudnorm EBU R128 de dos pasadas), subtítulos `.srt`/`.vtt`, e informe QA.
- Empaquetado con `uv` + `Dockerfile` reproducible (Playwright pineado + FFmpeg + Poppler) y 303 tests verdes con todas las APIs/binarios mockeados.

### What Worked
- **Construcción bottom-up con stubs primero (Phase 1):** tener el orquestador + contratos Pydantic + los 10 stubs end-to-end antes de implementar cada etapa permitió swaps incrementales (`Stub → Stage`) sin romper el pipeline.
- **Checkpoints atómicos e idempotentes (tmp→rename + done markers):** reanudar a mitad fue trivial y los tests de doble ejecución validaron la idempotencia.
- **Plan-checker y code-review atraparon defectos reales antes de mergear:** contradicción del gate L3/L4 (Phase 6), 4 blockers en Phase 6 (alpha PNG, fuga de recurso PDF, paridad de cuenta de slides, no-mark-done-on-fail) y un bug de orden de build en el Dockerfile (Phase 7).
- **Mocks estrictos en tests:** sin llamadas reales a Anthropic/ElevenLabs/Chromium/FFmpeg; los smoke tests de render/assemble se saltan limpiamente si faltan binarios.

### What Was Inefficient
- **STATE.md quedó desincronizado durante la ejecución** (campos como "Current focus: Phase 05" y "Progress 0%" persistieron tras completar el milestone) — requirió corrección manual al cierre.
- **El extractor automático de one-liners de los SUMMARY.md no produjo accomplishments usables** (devolvió literales "One-liner:", "Font:", etc.) — hubo que reescribir MILESTONES.md a mano. Los SUMMARY no siguen un formato de one-liner consistente.
- **El roadmap creció más allá del milestone (Phases 8–9 añadidas tras la auditoría)** mezcló alcance enviado con alcance futuro en REQUIREMENTS.md, complicando el archivado limpio.

### Patterns Established
- **Stub-first pipeline:** definir todos los contratos I/O + stubs antes de implementar; cada fase hace swap de su stub por la etapa real.
- **Validación de salidas de API externas antes del checkpoint:** p. ej. timestamps ElevenLabs estrictamente crecientes + retry≤3 antes de persistir.
- **FFmpeg siempre por subprocess con lista de args (nunca `shell=True`)**; fluent builder en `integrations/ffmpeg.py`.
- **Visuales 100% reproducibles:** SVG offline + gráficos por código; los medios del usuario (Phases 8–9) se aportan, nunca se generan con IA.

### Key Lessons
1. **Mantener STATE.md como artefacto vivo durante la ejecución, no solo al cierre** — o aceptar que el cierre de milestone lo reconcilia, pero entonces no confiar en sus campos a mitad de camino.
2. **Estandarizar el bloque "one-liner" en cada SUMMARY.md** para que la extracción automática de accomplishments funcione en el cierre de milestone.
3. **Congelar el alcance del milestone al pasar la auditoría;** las nuevas ideas van a un milestone/roadmap separado en lugar de ampliar el REQUIREMENTS.md ya auditado.

### Cost Observations
- Model mix: Opus para planificación/fixes, Sonnet para ejecución (perfil `balanced`, modo `yolo`).
- Notable: el coste de re-trabajo fue bajo gracias a plan-check + code-review por fase; los defectos se atraparon antes del merge en lugar de en integración.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.60.0 | 7 | 18 | Baseline: pipeline secuencial stub-first con plan-check + code-review por fase |

### Cumulative Quality

| Milestone | Tests | External calls in tests | Zero-Dep Additions |
|-----------|-------|-------------------------|--------------------|
| v1.60.0 | 303 passing | 0 (todo mockeado) | — |

### Top Lessons (Verified Across Milestones)

1. (Pendiente de validación cruzada en el próximo milestone.)
