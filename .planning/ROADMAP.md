# Roadmap: Auto Video Narrado

## Milestones

- ✅ **v1.60.0 MVP Pipeline** — Phases 1–7 (shipped 2026-05-29) — see [milestones/v1.60.0-ROADMAP.md](milestones/v1.60.0-ROADMAP.md)
- ✅ **v2.0.0 Studio Guiado** — Phases 8–13 (shipped 2026-07-01) — see [milestones/v2.0.0-ROADMAP.md](milestones/v2.0.0-ROADMAP.md)

## Overview

Pipeline CLI en Python que transforma bullets + duración en un vídeo narrado (slides 1080p, voz ElevenLabs/OpenAI, subtítulos SRT/VTT, montaje FFmpeg). El MVP (Phases 1–7) y v2.0.0 Studio Guiado (Phases 8–13, UI Streamlit guiada) están enviados y archivados.

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

<details>
<summary>✅ v2.0.0 Studio Guiado (Phases 8–13) — SHIPPED 2026-07-01</summary>

- [x] **Phase 8: Backend Integrations** — OpenAI Audio TTS + STT round-trip + audio enhancement + background music FFmpeg pipeline (completed 2026-05-29)
- [x] **Phase 9: UI Foundation** — Streamlit shell + PipelineBridge + state model + invalidate_downstream + workdir reconstruction (completed 2026-05-29)
- [x] **Phase 10: Contenido Page** — Fase 1 wizard: intake de tema + duración + auto-generación de bullets + gate de aprobación (completed 2026-05-29)
- [x] **Phase 11: Guion + Slides Pages** — Fases 2 y 3 wizard: guion editable + variaciones + slides interactivas + verificador QC (completed 2026-05-29)
- [x] **Phase 12: Voz Page** — Fase 4 wizard: selección de proveedor de narración + previews de audio + gate de aprobación (completed 2026-05-29)
- [x] **Phase 13: Extras + Ensamblaje + Polish** — Fases 5–6 wizard: extras + montaje final + preview/descarga + packaging y tests (completed 2026-05-29)

Full phase detail: [milestones/v2.0.0-ROADMAP.md](milestones/v2.0.0-ROADMAP.md)

</details>

### 📋 Next Milestone — Not yet planned

Run `/gsd-new-milestone` to start requirements definition and roadmap planning for the next milestone.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 2. LLM Pipeline | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 3. Slides Auto | v1.60.0 | 2/2 | Complete | 2026-05-25 |
| 4. Voz + Subtítulos | v1.60.0 | 3/3 | Complete | 2026-05-25 |
| 5. Montaje + QA | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 6. Slides Hybrid/Manual + Verificador | v1.60.0 | 2/2 | Complete | 2026-05-26 |
| 7. Empaquetado + Tests + Docs | v1.60.0 | 3/3 | Complete | 2026-05-26 |
| 8. Backend Integrations | v2.0.0 | 5/5 | Complete   | 2026-05-29 |
| 9. UI Foundation | v2.0.0 | 4/4 | Complete   | 2026-05-29 |
| 10. Contenido Page | v2.0.0 | 3/3 | Complete   | 2026-05-29 |
| 11. Guion + Slides Pages | v2.0.0 | 4/4 | Complete   | 2026-05-29 |
| 12. Voz Page | v2.0.0 | 3/3 | Complete   | 2026-05-29 |
| 13. Extras + Ensamblaje + Polish | v2.0.0 | 4/4 | Complete   | 2026-05-29 |
