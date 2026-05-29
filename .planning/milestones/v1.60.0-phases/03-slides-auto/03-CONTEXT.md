# Phase 3: Slides Auto - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 implementa el modo `auto` de generación de slides: cada slide del `storyboard.json` (Phase 2) se renderiza a **PNG 1920×1080** vía HTML/CSS (Jinja2) + Playwright (Chromium headless), con tema parametrizable en `theme.yaml` e iconos SVG Lucide servidos **offline**. Sustituye el stub `slides`. NO incluye voz, subtítulos, montaje, ni los modos hybrid/manual ni el verificador (esos son Phase 4/5/6). Depende solo de Phase 2 (necesita `storyboard.json`). Puede construirse en paralelo con Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Tema (theme.yaml)
- **D-01** El tema lo **propone la IA**: una llamada a Claude genera `theme.yaml` (paleta, tipografías, espaciado) coherente con el contenido del storyboard. Hay un **theme por defecto** integrado que se usa si la generación se salta/falla, y el usuario puede editar el archivo a mano (precedence: theme.yaml del usuario > generado por IA > default).
- **D-02** `theme.yaml` define al menos: paleta (primario/fondo/texto/acentos), familias tipográficas (heading/body), tamaños base y escala, espaciados/márgenes. Validado con un modelo Pydantic (`ThemeConfig`).
- **D-03** Reanudable: si `theme.yaml` ya existe, no se regenera (idempotencia).

### Templates HTML (Jinja2)
- **D-04** **Una plantilla base** (layout 1920×1080, carga de fuentes, CSS del tema) + **macros/partials Jinja2 por `visual_type`** (title, bullets, chart, diagram, quote, comparison, image_icon). El base inyecta el tema como CSS variables.
- **D-05** El render usa las decisiones de Phase 1 (sync_playwright, un browser instance por run) y espera `fonts.ready` + `animations=disabled` antes del screenshot para evitar PNG con fuentes a medio cargar (pitfall conocido).
- **D-06** Salida: un PNG por slide en `workdir/slides/slide_XX.png`, exactamente 1920×1080.

### Visuales offline (sin red en runtime)
- **D-07** Iconos vía **`python-lucide`** (BD SQLite embebida, sin CDN): se incrustan los SVG Lucide en el contexto Jinja2. Gráficos/diagramas (chart/diagram/comparison) se dibujan **por código** (SVG/HTML/CSS generado), nunca imágenes IA ni stock.
- **D-08** Ningún recurso externo se descarga en runtime: fuentes empaquetadas/self-hosted, iconos offline, CSS local. Debe funcionar en Docker sin internet.

### Integración con el pipeline
- **D-09** `integrations/playwright.py` encapsula el render (sync_playwright, page.set_viewport_size 1920×1080, screenshot PNG). `stages/slides_auto.py` orquesta: lee storyboard → (genera/lee theme) → render Jinja2 → Playwright → PNG por slide.
- **D-10** La etapa real reemplaza el stub `slides` en el registro del orquestador, respetando StageProtocol y el checkpoint del directorio `slides/`.

### Claude's Discretion
- Diseño visual concreto de cada `visual_type` (CSS exacto), elección de fuentes por defecto, librería concreta para charts por código si hace falta, estructura interna del prompt de generación de tema, tamaño/estilo de iconos — a criterio de Claude siguiendo estas decisiones y CLAUDE.md (solo SVG + código).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/avideo/models/storyboard.py` — `StoryboardOutput` + `SlideSpec` con `visual_type: VisualType` (Enum: title/bullets/chart/diagram/quote/comparison/image_icon). El render mapea cada `visual_type` a su macro.
- `src/avideo/orchestrator.py` + `stages/base.py` — StageProtocol/CheckpointMixin; loop con checkpoints atómicos. La etapa `slides` se enchufa aquí.
- `src/avideo/utils/workdir.py` — `WorkdirManager` ya crea el subdir `slides/`.
- `src/avideo/integrations/anthropic.py` — `call_structured()` reutilizable para la generación de `theme.yaml` (tool-use estructurado → `ThemeConfig`).
- Decisiones STATE.md: sync_playwright (no async), un browser por run, fuentes offline.

### Established Patterns
- Pydantic v2, tipado, docstrings, errores con Rich, idempotencia por checkpoint `.done`.
- Tests con pytest; el render de una slide a PNG es un smoke test (TEST-03 en Phase 7).

### Integration Points
- Lee `workdir/storyboard.json` (Phase 2). Escribe `workdir/slides/slide_XX.png`.
- Nuevo: `integrations/playwright.py`, `stages/slides_auto.py`, plantillas en `src/avideo/templates/` (o similar), `theme.yaml` (raíz del proyecto o workdir), `models/theme.py` (`ThemeConfig`).
- Requiere `playwright install chromium` (documentar para Phase 7 Dockerfile).

</code_context>

<specifics>
## Specific Ideas

- Success criteria: `--slides-mode auto` produce un PNG 1920×1080 por slide con las fuentes del tema cargadas; solo iconos SVG offline + gráficos por código; tema leído de `theme.yaml` (propuesto por IA, sobreescribible).
- Render pixel-perfect: esperar `document.fonts.ready` antes del screenshot.

</specifics>

<deferred>
## Deferred Ideas

- Export a .pptx (v2) — fuera de alcance.
- Sobreescritura de marca propia en theme.yaml (BRAND-01, v2) — fuera de alcance.

</deferred>
