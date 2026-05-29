# Requirements: Auto Video Narrado

**Core Value:** A partir de unos bullets + una duración, obtener un vídeo narrado coherente y de alta calidad (slides + voz + subtítulos sincronizados) sin intervención manual obligatoria, con checkpoints opcionales de supervisión.

> El milestone v1.60.0 (Phases 1–7) está enviado y archivado en
> `milestones/v1.60.0-REQUIREMENTS.md`. No hay un milestone siguiente
> definido todavía. Las ideas reconocidas pero no planificadas viven en
> "Later Requirements" abajo. Usa `/gsd-new-milestone` para definir el
> próximo alcance.

## Requirements

_No active milestone. Run `/gsd-new-milestone` to define the next scope._

## Later Requirements

Diferidos a futuro. Reconocidos pero fuera del roadmap actual.

### Export y formatos

- **EXPORT-01**: Exportación de slides a `.pptx` con `python-pptx` (opción secundaria)
- **FMT-01**: Salida 9:16 vertical (formato social) con plantillas adaptadas
- **BRAND-01**: Sobreescritura del `theme.yaml` con marca propia (paleta/tipografías/logo)

## Out of Scope

Excluido explícitamente. Documentado para evitar scope creep.

| Feature | Razón |
|---------|-------|
| Generación de imágenes con IA | Solo iconos SVG y gráficos por código (control y consistencia visual) |
| Bancos de imágenes / stock | Visuales 100% reproducibles y editables |
| Orquestadores visuales (n8n) | Se quiere orquestador propio en Python, simple |
| Frameworks de agentes (LangGraph) | Innecesario para un pipeline lineal (DAG secuencial) |
| MoviePy | Se usa FFmpeg directo por rendimiento y control |
| Partir de un `.pptx` existente como flujo principal | El workflow genera las slides; ingesta solo en hybrid/manual |
| Avatares / lip-sync (p. ej. Wav2Lip) | Modelos pesados; resuelven un problema distinto |

## Traceability

_Empty — no active milestone requirements. Filled by the roadmap when the next milestone is defined._

---
*v1.60.0 shipped 2026-05-29. Phases 8–9 (screenshot/video support) removed from scope 2026-05-29.*
