# Roadmap: Auto Video Narrado

## Milestones

- ✅ **v1.60.0 MVP Pipeline** — Phases 1–7 (shipped 2026-05-29) — see [milestones/v1.60.0-ROADMAP.md](milestones/v1.60.0-ROADMAP.md)

## Overview

Pipeline CLI en Python que transforma bullets + duración en un vídeo narrado (slides 1080p, voz ElevenLabs, subtítulos SRT/VTT, montaje FFmpeg). El MVP (Phases 1–7) está enviado y archivado. No hay un milestone siguiente planificado todavía — usa `/gsd-new-milestone` cuando quieras definir el próximo.

## Phases

<details>
<summary>✅ v1.60.0 MVP Pipeline (Phases 1–7) — SHIPPED 2026-05-29</summary>

- [x] **Phase 1: Foundation** — Orquestador secuencial + CLI typer + modelos Pydantic + WorkdirManager + niveles L1-L4 (completed 2026-05-25)
- [x] **Phase 2: LLM Pipeline** — Ingesta de contexto + Storyboard (Claude) + Director de timing + Guionista (Claude) (completed 2026-05-25)
- [x] **Phase 3: Slides Auto** — Jinja2 + Playwright → PNG 1920×1080 + theme.yaml + iconos SVG offline (modo `auto`) (completed 2026-05-25)
- [x] **Phase 4: Voz + Subtítulos** — ElevenLabs TTS con timestamps + modo record + WhisperX + SRT/VTT (completed 2026-05-25)
- [x] **Phase 5: Montaje + QA** — FFmpeg concat + crossfade + loudnorm + quemado de subtítulos + informe QA (completed 2026-05-26)
- [x] **Phase 6: Slides Hybrid/Manual + Verificador** — Propuesta de diseño + ingesta de slides + verificador Claude Vision (completed 2026-05-26)
- [x] **Phase 7: Empaquetado + Tests + Docs** — pyproject.toml/uv + Dockerfile + pytest + README (completed 2026-05-26)

Full phase detail: [milestones/v1.60.0-ROADMAP.md](milestones/v1.60.0-ROADMAP.md)

</details>

## Progress

No active milestone. v1.60.0 (Phases 1–7) shipped and archived.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 2. LLM Pipeline | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 3. Slides Auto | v1.60.0 | 2/2 | Complete | 2026-05-25 |
| 4. Voz + Subtítulos | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 5. Montaje + QA | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 6. Slides Hybrid/Manual + Verificador | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 7. Empaquetado + Tests + Docs | v1.60.0 | 3/3 | Complete | 2026-05-26 |
