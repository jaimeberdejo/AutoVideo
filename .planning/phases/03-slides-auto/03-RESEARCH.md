# Phase 3: Slides Auto - Research

**Researched:** 2026-05-25
**Domain:** HTML/CSS → PNG rendering (Jinja2 + Playwright sync, Chromium headless), offline fonts/icons, AI-proposed theme
**Confidence:** HIGH

## Summary

Phase 3 reemplaza el stub `slides` con un renderizador real que convierte cada `SlideSpec` del `storyboard.json` en un PNG **exactamente 1920×1080** vía HTML/CSS (Jinja2) + Playwright (sync, Chromium headless). El stack está completamente verificado en este entorno: Playwright 1.60.0 está instalado, Chromium-1217 ya está en la caché `~/Library/Caches/ms-playwright`, y `python-lucide` 0.2.24 expone `lucide_icon()` con 1694 iconos en una BD SQLite offline. Un smoke test end-to-end real (ejecutado en esta sesión) confirma que `new_page(viewport={1920,1080}) → set_content(html) → page.evaluate("await document.fonts.ready") → screenshot(animations="disabled")` produce un PNG RGB exacto de 1920×1080.

El riesgo técnico número uno del proyecto es el **renderizado de fuentes offline en headless Chromium**. Verifiqué empíricamente la mitigación robusta: empotrar las fuentes como **data-URI base64 en `@font-face`** dentro del CSS, y esperar `document.fonts.load('<size> <family>')` para CADA familia declarada **antes** de `document.fonts.ready`. (`document.fonts.ready` por sí solo resuelve inmediatamente si ninguna fuente fue *solicitada* todavía — un pitfall silencioso). Con esto, `document.fonts.check()` devuelve `True` sin red. Esto también evita el problema conocido de `chromium-headless-shell` sin fontconfig en Docker (Phase 7).

**Primary recommendation:** `integrations/playwright.py` abre UN browser/context por run (`device_scale_factor=1`, viewport 1920×1080), renderiza vía `page.set_content(html)` con fuentes empotradas base64, espera explícitamente cada `@font-face` + `document.fonts.ready`, y captura con `screenshot(type="png", animations="disabled")`. `stages/slides_auto.py` orquesta: lee `storyboard.json` → genera/lee `theme.yaml` (idempotente) → renderiza Jinja2 (base + macros por `visual_type`) → Playwright → `slide_00.png … slide_NN.png`. `ThemeConfig` (Pydantic) se inyecta como CSS custom properties en la plantilla base.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tema (theme.yaml)**
- **D-01** El tema lo **propone la IA**: una llamada a Claude genera `theme.yaml` (paleta, tipografías, espaciado) coherente con el contenido del storyboard. Hay un **theme por defecto** integrado que se usa si la generación se salta/falla, y el usuario puede editar el archivo a mano (precedence: theme.yaml del usuario > generado por IA > default).
- **D-02** `theme.yaml` define al menos: paleta (primario/fondo/texto/acentos), familias tipográficas (heading/body), tamaños base y escala, espaciados/márgenes. Validado con un modelo Pydantic (`ThemeConfig`).
- **D-03** Reanudable: si `theme.yaml` ya existe, no se regenera (idempotencia).

**Templates HTML (Jinja2)**
- **D-04** **Una plantilla base** (layout 1920×1080, carga de fuentes, CSS del tema) + **macros/partials Jinja2 por `visual_type`** (title, bullets, chart, diagram, quote, comparison, image_icon). El base inyecta el tema como CSS variables.
- **D-05** El render usa las decisiones de Phase 1 (sync_playwright, un browser instance por run) y espera `fonts.ready` + `animations=disabled` antes del screenshot para evitar PNG con fuentes a medio cargar (pitfall conocido).
- **D-06** Salida: un PNG por slide en `workdir/slides/slide_XX.png`, exactamente 1920×1080.

**Visuales offline (sin red en runtime)**
- **D-07** Iconos vía **`python-lucide`** (BD SQLite embebida, sin CDN): se incrustan los SVG Lucide en el contexto Jinja2. Gráficos/diagramas (chart/diagram/comparison) se dibujan **por código** (SVG/HTML/CSS generado), nunca imágenes IA ni stock.
- **D-08** Ningún recurso externo se descarga en runtime: fuentes empaquetadas/self-hosted, iconos offline, CSS local. Debe funcionar en Docker sin internet.

**Integración con el pipeline**
- **D-09** `integrations/playwright.py` encapsula el render (sync_playwright, page.set_viewport_size 1920×1080, screenshot PNG). `stages/slides_auto.py` orquesta: lee storyboard → (genera/lee theme) → render Jinja2 → Playwright → PNG por slide.
- **D-10** La etapa real reemplaza el stub `slides` en el registro del orquestador, respetando StageProtocol y el checkpoint del directorio `slides/`.

### Claude's Discretion
- Diseño visual concreto de cada `visual_type` (CSS exacto), elección de fuentes por defecto, librería concreta para charts por código si hace falta, estructura interna del prompt de generación de tema, tamaño/estilo de iconos — a criterio de Claude siguiendo estas decisiones y CLAUDE.md (solo SVG + código).

### Deferred Ideas (OUT OF SCOPE)
- Export a .pptx (v2) — fuera de alcance.
- Sobreescritura de marca propia en theme.yaml (BRAND-01, v2) — fuera de alcance.
- Modos `hybrid`/`manual`, verificador Claude Vision (Phase 6) — fuera de alcance de Phase 3.
- Voz, subtítulos, montaje (Phases 4/5) — fuera de alcance.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SLIDE-01 | En modo `auto`, cada slide del storyboard se renderiza a PNG 1920×1080 desde HTML (Jinja2 + `theme.yaml`) con Playwright | Smoke test verificado: `new_page(viewport 1920×1080) + set_content + fonts.ready + screenshot(png)` → PNG RGB exacto 1920×1080. Patrón completo en "Code Examples". |
| SLIDE-02 | Las slides usan solo iconos SVG (Lucide/Heroicons) y gráficos/diagramas generados por código (sin imágenes IA ni stock) | `python-lucide` 0.2.24 verificado: `lucide_icon(name, width, height, stroke)` → SVG string, 1694 iconos offline (SQLite). Charts/diagramas = SVG inline generado en macros Jinja2 (patrones en "Code-drawn graphics"). |
| SLIDE-03 | El tema (paleta, tipografías, espaciado) se parametriza en `theme.yaml` y lo propone la IA | `call_structured()` ya existe y es reutilizable → `ThemeConfig` Pydantic. theme.yaml leído/escrito con `pyyaml` ya en deps. Idempotencia D-03. Default fallback. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Generación de `theme.yaml` (IA) | LLM integration (`integrations/anthropic.py`) | Stage (`stages/slides_auto.py`) | Reutiliza `call_structured()` ya existente; el stage orquesta cuándo llamar (idempotencia) |
| Render HTML → PNG | Browser automation (`integrations/playwright.py`) | — | Encapsula TODA la interacción con Playwright/Chromium; el stage nunca toca la API de Playwright directamente (espejo de cómo `stages/storyboard.py` solo llama `call_structured`) |
| Templating HTML (base + macros) | Presentation layer (Jinja2 templates en `src/avideo/templates/`) | Stage (carga el environment) | Lógica de layout en plantillas; el stage solo pasa contexto (slide + theme + iconos) |
| Iconos SVG | Asset provider (`python-lucide`) | Jinja2 (función/filtro inyectado al env) | Iconos resueltos offline; expuestos a las plantillas como helper Jinja2 |
| Charts/diagramas por código | Presentation layer (Jinja2 macros generando SVG inline) | — | Sin librerías de charting externas; SVG generado por macros/funciones puras |
| Orquestación de la etapa | Stage (`stages/slides_auto.py`) | Orchestrator (loop existente) | Lee storyboard.json, decide theme, itera slides, devuelve `SlidesOutput`; el orquestador escribe checkpoint + done |
| Persistencia del checkpoint | Orchestrator + `WorkdirManager` | — | El stage devuelve `SlidesOutput`; el orquestador llama `write_checkpoint`/`mark_done` (Pitfall-4, contrato existente) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `playwright` | `1.60.0` | Render HTML/CSS → PNG vía Chromium headless | [VERIFIED: importlib.metadata en este entorno → 1.60.0; PyPI latest = 1.60.0] Coincide con CLAUDE.md y con la imagen Docker pineada `playwright/python:v1.60.0-noble` |
| `jinja2` | `3.1.6` | Templating HTML (base + macros por visual_type) | [VERIFIED: `import jinja2; jinja2.__version__` → 3.1.6 ya instalado en el entorno] Ya disponible; estándar para templating Python |
| `python-lucide` | `0.2.24` | Iconos Lucide SVG offline (BD SQLite embebida) | [VERIFIED: PyPI latest 0.2.24, 2026-03-29; probado en sesión: 1694 iconos, `lucide_icon()` devuelve SVG string sin red] |
| `pyyaml` | `6.0.3` (ya en deps) | Leer/escribir `theme.yaml` | [VERIFIED: ya en pyproject.toml] Ya es dependencia del proyecto (config.yaml/bullets.yaml) |
| `pydantic` | `2.13.4` (ya en deps) | `ThemeConfig` validation | [VERIFIED: ya en pyproject.toml] v2 ya en uso en todo el proyecto |
| `anthropic` | `0.104.1` (ya en deps) | Generación IA del tema vía `call_structured()` | [VERIFIED: ya en pyproject.toml + `integrations/anthropic.py` existe] Reutiliza el helper existente |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rich` | `15.0.0` (ya en deps) | Progress por slide durante el render | El orquestador ya tiene una progress bar global; opcionalmente log por slide |
| `Pillow` (PIL) | latest | SOLO en tests — verificar dimensiones del PNG (`Image.open(...).size`) | Test de smoke (TEST-03): abrir el PNG y assert `(1920,1080)`. NO en runtime. Considerar añadir a `[dependency-groups] dev` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `page.set_content(html)` (HTML en memoria) | `page.goto("file://.../slide.html")` (HTML a disco) | `goto(file://)` resuelve URLs relativas de `@font-face`/iconos contra el directorio del archivo (no necesita base64). Pero deja archivos `.html` temporales y mezcla I/O con render. `set_content` + base64 es más limpio y portable a Docker. Recomendado: `set_content` + fuentes base64. |
| `python-lucide` | Heroicons embebidos a mano | CLAUDE.md menciona "Lucide/Heroicons"; `python-lucide` da 1694 iconos offline sin curado manual. Usar `python-lucide`. |
| SVG inline generado por código | `matplotlib`/`plotly` para charts | CLAUDE.md y D-07 prohíben librerías de imágenes; charts deben ser SVG/HTML/CSS por código. NO usar librerías de charting. |
| `device_scale_factor=1` | `device_scale_factor=2` + `scale="css"` | DSF=2 daría PNG físico 3840×2160 (más nítido pero NO 1920×1080 → violaría D-06). Para clavar 1920×1080 exacto, usar **DSF=1**. Si se quisiera supersampling se necesitaría downscale posterior — fuera de alcance. Usar DSF=1. |

**Installation:**
```bash
uv add playwright jinja2 python-lucide
uv add --dev pillow            # solo para el test de dimensiones del PNG
uv run playwright install chromium   # browsers (Chromium-1217 ya en caché local)
```

**Version verification (esta sesión):**
- `playwright` → 1.60.0 [VERIFIED: `uv run --with playwright python -c "import importlib.metadata; print(importlib.metadata.version('playwright'))"`]
- `jinja2` → 3.1.6 [VERIFIED: import en el entorno]
- `python-lucide` → 0.2.24, release 2026-03-29 [VERIFIED: PyPI + import probado]
- Chromium browser revision `chromium-1217` + `chromium_headless_shell-1217` ya en `~/Library/Caches/ms-playwright` [VERIFIED: `ls`]

## Architecture Patterns

### System Architecture Diagram

```
storyboard.json (Phase 2 checkpoint)
        │  read_checkpoint("storyboard", StoryboardOutput)
        ▼
┌─────────────────────────────────────────────────────────────┐
│  stages/slides_auto.py  (SlidesAutoStage.run)                 │
│                                                               │
│   1. theme resolution (idempotent, D-01/D-03)                 │
│      ├─ theme.yaml exists? ── yes ──► load + ThemeConfig      │
│      └─ no ─► call_structured(→ThemeConfig) ─► write theme.yaml│
│              └─ on API error ─► DEFAULT_THEME (built-in)      │
│                                                               │
│   2. build Jinja2 Environment                                 │
│      └─ register lucide helper (python-lucide, offline)       │
│                                                               │
│   3. for each SlideSpec (index, visual_type):                 │
│      ├─ render base.html.j2 + macro[visual_type]              │
│      │     theme → CSS custom properties                      │
│      │     fonts → base64 @font-face                          │
│      │     icons → lucide_icon(...) SVG inline                │
│      │     charts/diagrams → SVG inline (code-drawn)          │
│      └─ HTML string ──────────────────────────┐              │
└───────────────────────────────────────────────┼──────────────┘
                                                 ▼
┌─────────────────────────────────────────────────────────────┐
│  integrations/playwright.py  (render_html_to_png / Renderer) │
│   sync_playwright → chromium.launch() (ONE per run)           │
│   new_page(viewport=1920×1080, device_scale_factor=1)        │
│   page.set_content(html, wait_until="load")                  │
│   page.evaluate("await fonts.load(...) ; await fonts.ready")  │
│   page.screenshot(type="png", animations="disabled")        │
└───────────────────────────────────────────────┬──────────────┘
                                                 ▼
                          workdir/slides/slide_00.png … slide_NN.png
                                                 │
                                                 ▼
                          return SlidesOutput(png_paths=[...], mode="auto")
                                                 │  (orchestrator)
                                                 ▼
                          write_checkpoint("slides") → mark_done("slides")
```

### Recommended Project Structure
```
src/avideo/
├── integrations/
│   ├── anthropic.py          # existe — reutilizado para theme (call_structured)
│   └── playwright.py         # NUEVO — Renderer: sync_playwright, 1 browser/run, screenshot PNG
├── models/
│   ├── slides.py             # existe — SlidesOutput (sin cambios necesarios)
│   └── theme.py              # NUEVO — ThemeConfig (paleta, tipografías, escala, espaciado)
├── stages/
│   └── slides_auto.py        # NUEVO — SlidesAutoStage (stage_name="slides")
├── templates/                # NUEVO — paquete de plantillas Jinja2
│   ├── base.html.j2          # layout 1920×1080, CSS vars del tema, @font-face base64
│   └── macros.html.j2        # macro por visual_type (7 valores)
├── assets/
│   └── fonts/                # NUEVO — .ttf/.woff2 empaquetados (offline, base64 en runtime)
└── utils/
    └── theme.py / theme_defaults.py  # DEFAULT_THEME + carga/precedence (opcional)
theme.yaml                    # generado por IA o editado por el usuario (raíz o workdir)
```

> Nota sobre empaquetado: las plantillas y fuentes en `src/avideo/` deben incluirse en el wheel. Con `uv_build` (PEP 517) los datos no-`.py` requieren configuración. Documentar para Phase 7 (PKG-01) — usar `importlib.resources` para leer plantillas/fuentes de forma robusta en runtime (no rutas relativas a `__file__`). [ASSUMED: detalles exactos de inclusión de package-data con uv_build no verificados en esta sesión]

### Pattern 1: Renderer con UN browser por run (D-05)
**What:** `integrations/playwright.py` expone un context manager / clase que abre `sync_playwright` + `chromium.launch()` una sola vez, renderiza N slides reutilizando el mismo browser, y cierra todo al final.
**When to use:** Siempre en el stage. Abrir/cerrar un browser por slide es ~10× más lento.
**Example:**
```python
# Source: verificado end-to-end en esta sesión (playwright 1.60.0)
from contextlib import contextmanager
from playwright.sync_api import sync_playwright

class SlideRenderer:
    """Un browser/context por run; render_to_png(html, out_path) por slide."""
    def __init__(self) -> None:
        self._pw = None
        self._browser = None

    def __enter__(self) -> "SlideRenderer":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()  # headless por defecto
        return self

    def __exit__(self, *exc) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def render_to_png(self, html: str, out_path) -> None:
        page = self._browser.new_page(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,            # 1 → PNG físico exacto 1920×1080 (D-06)
        )
        try:
            page.set_content(html, wait_until="load")
            # CRÍTICO: solicitar cada familia ANTES de fonts.ready (ver Pitfall 1)
            page.evaluate(
                """async () => {
                    const faces = [...document.fonts];
                    await Promise.all(faces.map(f => f.load().catch(() => {})));
                    await document.fonts.ready;
                }"""
            )
            page.screenshot(path=str(out_path), type="png", animations="disabled")
        finally:
            page.close()
```

### Pattern 2: ThemeConfig → CSS custom properties (D-04)
**What:** La plantilla base inyecta `ThemeConfig` como variables CSS en `:root`, de modo que los macros usan `var(--color-primary)` etc.
**Example:**
```python
# models/theme.py  (Pydantic v2)
from pydantic import BaseModel, Field

class Palette(BaseModel):
    primary: str = "#2563eb"
    background: str = "#0f172a"
    text: str = "#f1f5f9"
    accent: str = "#38bdf8"

class Typography(BaseModel):
    heading: str = "Inter"
    body: str = "Inter"

class ThemeConfig(BaseModel):
    palette: Palette = Field(default_factory=Palette)
    typography: Typography = Field(default_factory=Typography)
    base_font_px: int = 32
    scale: float = 1.25          # modular scale
    margin_px: int = 120
    gap_px: int = 40
```
```jinja
{# base.html.j2 #}
<style>
  :root {
    --color-primary: {{ theme.palette.primary }};
    --color-bg: {{ theme.palette.background }};
    --color-text: {{ theme.palette.text }};
    --color-accent: {{ theme.palette.accent }};
    --font-heading: '{{ theme.typography.heading }}';
    --font-body: '{{ theme.typography.body }}';
    --margin: {{ theme.margin_px }}px;
  }
  {{ font_face_css }}  {# @font-face base64 inyectado por el stage #}
  html, body { width: 1920px; height: 1080px; margin: 0; }
  body { background: var(--color-bg); color: var(--color-text);
         font-family: var(--font-body), sans-serif; padding: var(--margin); }
</style>
```

### Pattern 3: Iconos Lucide offline como helper Jinja2 (D-07)
**What:** Registrar `lucide_icon` como global del Environment para que los macros llamen `{{ icon('chart-bar', size=64, stroke=theme.palette.accent) }}`.
**Example:**
```python
# Source: python-lucide 0.2.24 — API verificada por import directo en esta sesión
from lucide import lucide_icon  # devuelve un SVG string

def icon(name: str, size: int = 48, stroke: str = "currentColor") -> str:
    return lucide_icon(name, width=size, height=size, stroke=stroke)

env.globals["icon"] = icon
# IMPORTANTE: el SVG es confiable (generado por nosotros) pero contiene markup;
# marcar como seguro en plantilla: {{ icon('zap')|safe }}  (o usar |safe en el macro)
```
> Nombres de iconos en Lucide nuevo: `chart-bar` (NO `bar-chart`). [VERIFIED: `'chart-bar' in get_icon_list()` → True; `'bar-chart'` → False]. Curar un pequeño mapa `VisualType → icono` por defecto.

### Pattern 4: Charts/diagramas por código (SVG inline) (D-07, SLIDE-02)
**What:** Para `chart`/`diagram`/`comparison`, generar SVG inline en macros Jinja2 (barras = `<rect>` con alturas calculadas; flujos = `<rect>`+`<line>`/`<path>`; comparación = dos columnas HTML/CSS grid). Sin librerías externas.
**Example (bar chart por código):**
```jinja
{% macro bar_chart(values, color) %}
{% set maxv = values|max %}
<svg viewBox="0 0 800 400" width="800" height="400">
  {% for v in values %}
    {% set h = (v / maxv * 360)|round %}
    <rect x="{{ loop.index0 * 120 + 40 }}" y="{{ 380 - h }}"
          width="80" height="{{ h }}" fill="{{ color }}" rx="6"/>
  {% endfor %}
</svg>
{% endmacro %}
```
> Para `chart`, los valores numéricos NO existen en `SlideSpec` (solo `title` + `bullets`). Opciones: (a) parsear números de los bullets cuando los haya; (b) tratar `chart` como layout decorativo/ilustrativo cuando no hay datos. Ver Open Question #2.

### Pattern 5: Macro dispatch por visual_type (D-04)
```jinja
{# base.html.j2 — el cuerpo despacha al macro correcto #}
{% from "macros.html.j2" import title_slide, bullets_slide, chart_slide,
   diagram_slide, quote_slide, comparison_slide, image_icon_slide %}
{% set renderers = {
   "title": title_slide, "bullets": bullets_slide, "chart": chart_slide,
   "diagram": diagram_slide, "quote": quote_slide,
   "comparison": comparison_slide, "image_icon": image_icon_slide } %}
{{ renderers[slide.visual_type.value](slide, theme) }}
```
> `visual_type` es un `VisualType` enum (str-Enum) → usar `.value` o configurar Jinja2 para que `str(enum)` funcione. Cubrir los 7 valores; tener un fallback a `bullets_slide` si llega un valor inesperado (robustez).

### Anti-Patterns to Avoid
- **`device_scale_factor=2` esperando 1920×1080:** produce un PNG físico de 3840×2160. Viola D-06. Usar DSF=1.
- **`full_page=True` en screenshot:** captura toda la página scrollable; si el contenido desborda 1080px el PNG no será 1920×1080. Mantener `full_page=False` (default) + viewport fijo + contenido que NO desborde.
- **Esperar solo `document.fonts.ready` sin `.load()`:** resuelve inmediatamente si ninguna fuente fue solicitada → screenshot con fuente fallback. Solicitar cada face primero (Pitfall 1).
- **Referenciar fuentes/iconos por URL relativa o `file://` en `set_content`:** `set_content` no tiene base URL → 404 silencioso → fallback de fuente. Empotrar base64 o usar `goto(file://)`.
- **Abrir/cerrar un browser por slide:** lento. Un browser por run (D-05).
- **`shell=True` o concatenación de strings para iconos sin `|safe`:** Jinja2 auto-escapa el SVG → aparece markup como texto. Marcar SVG confiable con `|safe`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Iconos SVG | Curar/descargar SVGs Lucide a mano | `python-lucide` (`lucide_icon`) | 1694 iconos offline en SQLite; consistencia de viewBox/stroke; sin red |
| HTML → imagen | Pillow/cairo dibujando texto | Playwright + Chromium | Pillow no renderiza HTML/CSS; CLAUDE.md prohíbe Pillow como renderizador |
| Retry/backoff de la llamada de tema | Loop 429/5xx propio | `anthropic` SDK `max_retries=3` (ya en `_get_client()`) | El SDK ya hace backoff + jitter + Retry-After (D-13) |
| Tool-use → Pydantic para el tema | Parsear JSON de texto | `call_structured()` existente | Helper ya probado y mockeable (espejo de storyboard/scriptwriter) |
| Escritura atómica del checkpoint | `open().write()` directo | El orquestador + `WorkdirManager.write_checkpoint` | Pitfall-4: el stage SOLO devuelve `SlidesOutput`; nunca escribe checkpoint/done |
| Charts | matplotlib/plotly | SVG inline por macros | D-07/CLAUDE.md prohíben librerías de imágenes; SVG por código es 100% reproducible |
| Carga de YAML del tema | parser propio | `pyyaml` (ya en deps) | Igual que config.yaml/bullets.yaml |

**Key insight:** Casi todo el "fontanería" ya existe en el proyecto (call_structured, WorkdirManager atómico, StageProtocol, pyyaml, anthropic SDK). El trabajo NUEVO genuino es: el Renderer de Playwright, las plantillas Jinja2, `ThemeConfig`/default, y el cableado en `PIPELINE_STAGES`.

## Common Pitfalls

### Pitfall 1: `document.fonts.ready` resuelve antes de cargar las fuentes
**What goes wrong:** El screenshot sale con la fuente fallback (system-ui) en vez de la fuente del tema, de forma intermitente.
**Why it happens:** `document.fonts.ready` es una promesa que resuelve cuando NO hay cargas de fuentes *pendientes*. Si en el momento de evaluarla ningún glifo ha solicitado todavía la fuente custom, resuelve inmediatamente sin haberla cargado. Headless Chromium agrava esto.
**How to avoid:** Solicitar explícitamente cada `@font-face` antes: `await Promise.all([...document.fonts].map(f => f.load()))` y LUEGO `await document.fonts.ready`. [VERIFIED en sesión: con este patrón `document.fonts.check('80px Bundled')` → True; sin él, no garantizado].
**Warning signs:** PNG con tipografía inconsistente entre ejecuciones; la fuente "salta" entre runs.

### Pitfall 2: Fuentes no resueltas en `set_content` (sin base URL)
**What goes wrong:** `@font-face { src: url(fonts/Inter.woff2) }` o `file://` → la fuente nunca carga; en Docker es 100% reproducible el fallo.
**Why it happens:** `page.set_content()` llama internamente a `document.write()` sin una URL base; las URLs relativas no se resuelven.
**How to avoid:** Empotrar la fuente como `url(data:font/ttf;base64,...)` en el CSS (verificado offline en sesión). Alternativa: `page.goto("file://<abs>.html")` con la fuente junto al HTML.
**Warning signs:** Funciona "en mi máquina" (fuente del SO disponible) pero falla en Docker (`chromium-headless-shell` sin fontconfig).

### Pitfall 3: Tamaño del PNG ≠ 1920×1080
**What goes wrong:** El PNG sale 3840×2160 (DSF=2) o más alto de 1080 (full_page o contenido que desborda).
**Why it happens:** `device_scale_factor>1` multiplica los píxeles físicos; `full_page=True` o contenido > 1080px estira la captura.
**How to avoid:** `device_scale_factor=1`, viewport exacto, `full_page=False`, y CSS con `html,body { width:1920px; height:1080px; overflow:hidden }`. Verificar en el test con `Image.open(png).size == (1920,1080)`.
**Warning signs:** El test de dimensiones falla; el vídeo de Phase 5 sale con barras o recortes.

### Pitfall 4: Contenido que desborda 1080px (slides con muchos bullets)
**What goes wrong:** Texto cortado o scroll; el screenshot recorta contenido.
**Why it happens:** Storyboard puede generar 5 bullets largos; con tamaño base fijo desbordan verticalmente.
**How to avoid:** CSS defensivo: `overflow:hidden`, escala tipográfica con `clamp()`/unidades relativas, o limitar bullets en el prompt del storyboard (ya: "2–5 short bullet points"). Considerar `font-size` adaptativo por nº de bullets.
**Warning signs:** Slides con 5 bullets cortados abajo.

### Pitfall 5: Estado de workdir incompatible (visual_type "text" del stub Phase 1)
**What goes wrong:** `renderers[slide.visual_type]` → KeyError si un `storyboard.json` viejo tiene `visual_type="text"`.
**Why it happens:** El stub Phase 1 usaba `visual_type="text"`, que NO está en `VisualType` (ver nota de migración en `models/storyboard.py`).
**How to avoid:** El dispatch debe tener fallback a `bullets_slide` para valores desconocidos; documentar "borra workdir viejo". `VisualType` validará al leer el checkpoint si el JSON es nuevo.
**Warning signs:** KeyError en el primer render sobre un workdir reutilizado.

### Pitfall 6: `cost_estimator` no contabiliza la nueva llamada LLM del tema
**What goes wrong:** `--dry-run` subestima coste/tokens (no incluye la generación del tema).
**Why it happens:** `cost_estimator.py` línea ~142 lista `slides` como "no LLM cost". Phase 3 añade una llamada Claude.
**How to avoid:** Añadir `estimate_theme_tokens()` y sumarlo en `estimate_all()`. [VERIFIED: grep en `utils/cost_estimator.py`]. Es un cambio pequeño pero necesario para CLI-06.
**Warning signs:** Dry-run no menciona el tema; coste real > estimado.

### Pitfall 7: Chromium no instalado / mismatch de versión en CI/Docker
**What goes wrong:** `Executable doesn't exist at .../chromium-XXXX` en runtime.
**Why it happens:** `pip install playwright` NO instala los browsers; requiere `playwright install chromium`. La revisión del browser debe coincidir con la versión del paquete.
**How to avoid:** Documentar `uv run playwright install chromium` (y en Docker usar la imagen `playwright/python:v1.60.0-noble` que ya trae browsers — Phase 7). En este entorno los browsers YA están (chromium-1217). El test de smoke debe skipear elegantemente si faltan.
**Warning signs:** ImportError/ejecutable ausente; tests rojos solo en CI.

## Code Examples

### End-to-end render de una slide a PNG 1920×1080 (verificado en sesión)
```python
# Source: ejecutado y verificado en esta sesión — playwright 1.60.0, Chromium-1217
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080},
                            device_scale_factor=1)
    page.set_content(HTML, wait_until="load")
    page.evaluate("async () => { await document.fonts.ready; }")
    page.screenshot(path="slide_00.png", type="png", animations="disabled")
    browser.close()
# Resultado verificado: PIL Image.open(...).size == (1920, 1080), mode RGB
```

### Fuente offline base64 (verificado: carga sin red)
```python
# Source: verificado en sesión — document.fonts.check('80px Bundled') -> True
import base64
b64 = base64.b64encode(open("assets/fonts/Inter.ttf", "rb").read()).decode()
font_face_css = (
    "@font-face { font-family:'Inter';"
    f" src: url(data:font/ttf;base64,{b64}) format('truetype'); }}"
)
# Inyectar font_face_css en <style> de base.html.j2.
# Esperar carga explícita:
page.evaluate("""async () => {
    await Promise.all([...document.fonts].map(f => f.load().catch(()=>{})));
    await document.fonts.ready;
}""")
```

### Icono Lucide offline (verificado)
```python
# Source: python-lucide 0.2.24 — probado por import directo
from lucide import lucide_icon, get_icon_list
svg = lucide_icon("chart-bar", width=48, height=48, stroke="#38bdf8")
# -> '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"
#     viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width=...>'
assert "chart-bar" in get_icon_list()   # 1694 iconos disponibles offline
```

### Generación del tema con call_structured (idempotente, D-01/D-03)
```python
# Source: patrón espejo de stages/storyboard.py (verificado en codebase)
from avideo.integrations.anthropic import call_structured
from avideo.models.theme import ThemeConfig

def resolve_theme(theme_path, storyboard) -> ThemeConfig:
    if theme_path.exists():                       # D-03 idempotencia
        return ThemeConfig.model_validate(yaml.safe_load(theme_path.read_text()))
    try:
        theme = call_structured(
            system=_THEME_SYSTEM_PROMPT,
            user=_summarize_storyboard(storyboard),
            tool_name="emit_theme",
            tool_description="Emit a coherent visual theme (palette, fonts, spacing).",
            output_model=ThemeConfig,
            max_tokens=2048,
        )
    except Exception:                             # D-01 fallback
        theme = ThemeConfig()                     # DEFAULT_THEME integrado
    theme_path.write_text(yaml.safe_dump(theme.model_dump()))
    return theme
```
> Mock point: importar `call_structured` a nivel de módulo en `stages/slides_auto.py` para que los tests parcheen `avideo.stages.slides_auto.call_structured` (igual que storyboard).

### Swap del stub en PIPELINE_STAGES (D-10)
```python
# stages/stubs.py — reemplazar SlidesStub() por SlidesAutoStage()
from avideo.stages.slides_auto import SlidesAutoStage
PIPELINE_STAGES = [
    ContextStage(), StoryboardStage(), TimingStage(), ScriptwriterStage(),
    SlidesAutoStage(),    # Phase 3: real (was SlidesStub)  — stage_name="slides"
    VerifyStub(), VoiceStub(), AlignStub(), SubsStub(), AssembleStub(),
]
```
> `stage_name="slides"` y `checkpoint_name="slides"` (default) se preservan → el orquestador, los done-markers y `CREATIVE_STAGES` (L2 pausa en "slides") siguen funcionando sin cambios. El checkpoint `slides.json` contendrá `SlidesOutput(png_paths=[...], mode="auto")`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Nombres de iconos Lucide `bar-chart` | `chart-bar` (categoría-nombre) | Lucide reorganizó nombres | Usar nombres nuevos; verificar con `get_icon_list()` |
| `wkhtmltopdf`/WeasyPrint para HTML→imagen | Playwright headless Chromium | — | CSS moderno (grid, vars, transforms) soportado; CLAUDE.md ya lo fija |
| `device="device"` scale por defecto | Controlar `device_scale_factor` + `scale` explícito | — | Para clavar dimensiones exactas usar DSF=1 |

**Deprecated/outdated:**
- `bar-chart` (Lucide): renombrado; usar `chart-bar`.
- Pillow/cairo como renderizador HTML: no aplican (prohibido por CLAUDE.md).

## Runtime State Inventory

> Phase 3 es mayormente greenfield (añade etapa real), pero hay un swap de stub y estado de workdir reutilizable.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `workdir/storyboard.json` de runs viejos puede tener `visual_type="text"` (stub Phase 1, fuera del enum) | Code: dispatch con fallback a `bullets_slide`; doc: "borra workdir viejo + `.storyboard.done`" |
| Live service config | None — sin servicios externos persistentes (verificado: no hay DB/colas/servicios en el repo) | None |
| OS-registered state | None — sin tareas programadas ni procesos registrados | None |
| Secrets/env vars | `ANTHROPIC_API_KEY` (ya usado por `integrations/anthropic.py`); ningún secreto nuevo | None (la generación de tema reutiliza la misma key) |
| Build artifacts | Plantillas Jinja2 + fuentes en `src/avideo/` deben empaquetarse en el wheel (uv_build package-data) | Code/config: configurar inclusión de datos no-`.py` (Phase 7, PKG-01); usar `importlib.resources` para leerlos |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 8.x + `pytest-mock` 3.x (113 tests existentes verdes) [VERIFIED: `uv run pytest --co` → 113 collected] |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["src"]`) |
| Quick run command | `uv run pytest tests/test_slides_render.py -x` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SLIDE-01 | Render de 1 slide → PNG exacto 1920×1080 (smoke, Chromium real) | smoke/integration | `uv run pytest tests/test_slides_render.py::test_render_png_is_1920x1080 -x` | ❌ Wave 0 |
| SLIDE-01 | `SlidesAutoStage.run` produce N PNGs y devuelve `SlidesOutput(png_paths)` (Playwright mockeado) | unit | `uv run pytest tests/test_slides_auto.py::test_run_renders_all_slides -x` | ❌ Wave 0 |
| SLIDE-01 | `stage_name=="slides"` y `checkpoint_name=="slides"` (contrato preservado) | unit | `uv run pytest tests/test_slides_auto.py::test_stage_contract -x` | ❌ Wave 0 |
| SLIDE-02 | El HTML renderizado contiene SVG inline (icono Lucide) y NO `<img src=...>` externo | unit | `uv run pytest tests/test_slides_auto.py::test_html_offline_only -x` | ❌ Wave 0 |
| SLIDE-02 | `lucide_icon('chart-bar')` devuelve SVG offline (sin red) | unit | `uv run pytest tests/test_slides_auto.py::test_lucide_offline -x` | ❌ Wave 0 |
| SLIDE-03 | theme.yaml existente NO se regenera (idempotencia, call_structured no se llama) | unit | `uv run pytest tests/test_slides_auto.py::test_theme_idempotent -x` | ❌ Wave 0 |
| SLIDE-03 | Sin theme.yaml → call_structured genera ThemeConfig (mockeado) y escribe el archivo | unit | `uv run pytest tests/test_slides_auto.py::test_theme_generated_and_written -x` | ❌ Wave 0 |
| SLIDE-03 | call_structured falla → cae a DEFAULT_THEME sin romper | unit | `uv run pytest tests/test_slides_auto.py::test_theme_fallback_on_error -x` | ❌ Wave 0 |
| (cross) | Los 7 `visual_type` renderizan sin KeyError | unit | `uv run pytest tests/test_slides_auto.py::test_all_visual_types_render -x` | ❌ Wave 0 |

**Smoke test (SLIDE-01) — real vs mock:**
- **Render real (Chromium):** necesario para TEST-03 (Phase 7) y para validar 1920×1080. Headless Chromium SÍ está disponible localmente (chromium-1217 en caché). En CI hay que ejecutar `playwright install chromium`. El test debe usar `pytest.importorskip("playwright")` + skip si el ejecutable falta (`try: launch() except Error: pytest.skip(...)`), para no romper la suite en entornos sin browsers.
- **Stage unit (mock):** parchear `avideo.stages.slides_auto`'s renderer y `call_structured` → testear la orquestación (idempotencia, nº de PNGs, paths) sin lanzar Chromium ni llamar a la API. Rápido (<1s), corre siempre en CI.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_slides_auto.py -x` (unit, sin Chromium — rápido)
- **Per wave merge:** `uv run pytest -q` (suite completa, incluye smoke con Chromium si disponible)
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_slides_auto.py` — unit del stage (idempotencia tema, dispatch por visual_type, nº de PNGs, offline-only) con Playwright + call_structured mockeados — cubre SLIDE-01/02/03
- [ ] `tests/test_slides_render.py` — smoke real: HTML mínimo → Chromium → PNG, assert `(1920,1080)` con Pillow; `importorskip`/skip si no hay browser — cubre SLIDE-01 (y prepara TEST-03 de Phase 7)
- [ ] Fixture compartida: `fake_storyboard` (StoryboardOutput con varios visual_type) en `conftest.py`
- [ ] Dependencia dev: `uv add --dev pillow` (para assert de dimensiones del PNG)
- [ ] Asegurar `playwright install chromium` documentado para CI (Chromium ya presente localmente)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `playwright` (pkg) | Render HTML→PNG | ✓ | 1.60.0 | — (requisito) |
| Chromium browser | Playwright launch | ✓ | chromium-1217 (en `~/Library/Caches/ms-playwright`) | `playwright install chromium` |
| `chromium_headless_shell` | headless render | ✓ | 1217 | — |
| `jinja2` | Templating | ✓ | 3.1.6 | — |
| `python-lucide` | Iconos offline | ✓ (instalable, probado) | 0.2.24 | — (sin alternativa offline equivalente) |
| `pyyaml` | theme.yaml | ✓ | 6.0.3 (en deps) | — |
| `anthropic` + `ANTHROPIC_API_KEY` | Generación IA del tema | ✓ (SDK); key en `.env` | 0.104.1 | DEFAULT_THEME integrado (D-01) si falta key/falla la llamada |
| `Pillow` | Test de dimensiones | ✗ (no en deps) | — | Añadir a dev deps; o leer cabecera PNG sin Pillow (IHDR) |
| `ffmpeg` | NO usado en Phase 3 (Phase 5) | ✓ (ffmpeg-1011 en caché Playwright) | — | n/a esta fase |

**Missing dependencies with no fallback:** Ninguna bloqueante para Phase 3 (todo el stack está disponible o trivialmente instalable).

**Missing dependencies with fallback:**
- `Pillow`: añadir a `[dependency-groups] dev`. Alternativa sin dependencia: parsear el bloque IHDR del PNG (bytes 16–24) para leer ancho/alto. Pillow es más legible — recomendado para el test.
- `ANTHROPIC_API_KEY` ausente: la generación de tema cae a `DEFAULT_THEME` (D-01), así que el modo `auto` sigue produciendo slides offline-friendly sin la key (útil para tests y CI).

## Open Questions

1. **Ubicación canónica de `theme.yaml`: raíz del proyecto vs `workdir/`**
   - What we know: CONTEXT D-01 dice "el usuario puede editar el archivo"; STATE/code_context dice "raíz del proyecto o workdir". Precedence: usuario > IA > default.
   - What's unclear: si vive en raíz (editable, persiste entre runs) o en `workdir/` (efímero por run, encaja con idempotencia por checkpoint).
   - Recommendation: `theme.yaml` en la **raíz del proyecto** (editable, persistente, precedence usuario), y opcionalmente copiar el efectivo a `workdir/theme.yaml` como registro del run. Idempotencia D-03 sobre la raíz. Confirmar con el usuario en discuss/plan.

2. **`visual_type="chart"` sin datos numéricos en `SlideSpec`**
   - What we know: `SlideSpec` solo tiene `title` + `bullets` (sin valores numéricos). El storyboard elige `chart` cuando hay "datos cuantitativos".
   - What's unclear: de dónde salen los números para dibujar el chart.
   - Recommendation: (a) intentar parsear números/porcentajes de los `bullets` con un regex simple; si no hay, (b) renderizar un layout "chart" ilustrativo (icono + bullets estilizados) en vez de un gráfico con datos inventados (evita datos falsos). Es discrecional de Claude (CONTEXT). Documentar la decisión en el plan.

3. **Fuente por defecto empaquetada (licencia + formato)**
   - What we know: CLAUDE.md no fija una fuente; D-01 deja la elección a Claude. Verificado que base64 @font-face carga offline.
   - What's unclear: qué fuente concreta empaquetar (licencia OFL para redistribuir en el wheel/Docker).
   - Recommendation: usar una fuente OFL (p.ej. **Inter** o **Source Sans 3**) descargada a `src/avideo/assets/fonts/` (.ttf o .woff2). Confirmar licencia OFL antes de commitear el binario. [ASSUMED: Inter es OFL — verificar]

4. **Empaquetado de datos no-`.py` (plantillas + fuentes) con `uv_build`**
   - What we know: las plantillas Jinja2 y las fuentes deben incluirse en el wheel.
   - What's unclear: configuración exacta de package-data con `uv_build` (no verificada en esta sesión).
   - Recommendation: usar `importlib.resources.files("avideo.templates")` para localizar plantillas/fuentes en runtime (robusto en wheel y editable). Resolver la config de inclusión en Phase 7 (PKG-01).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | La fuente recomendada (Inter/Source Sans 3) es OFL y redistribuible en el wheel/Docker | Open Q #3 | Si no es redistribuible: problema de licencia al commitear el binario; mitigado eligiendo una fuente OFL confirmada |
| A2 | `uv_build` requiere config explícita para incluir datos no-`.py` (plantillas/fuentes) en el wheel | Project Structure / Open Q #4 | Si el build no incluye los assets, el render falla en el paquete instalado; mitigado con `importlib.resources` y resolución en Phase 7 |
| A3 | `theme.yaml` vive en la raíz del proyecto (no workdir) | Open Q #1 | Decisión de UX/idempotencia; bajo riesgo, fácil de mover; confirmar con usuario |

**Nota:** El stack técnico (Playwright API, dimensiones del PNG, fuentes base64 offline, python-lucide API) NO está en este log — fue **verificado empíricamente en esta sesión**, no asumido.

## Sources

### Primary (HIGH confidence)
- Verificación empírica en esta sesión (smoke tests ejecutados):
  - `playwright` 1.60.0 + Chromium-1217: `new_page(viewport 1920×1080, dsf=1) + set_content + fonts.ready + screenshot(png, animations=disabled)` → PNG RGB exacto 1920×1080.
  - Fuente base64 `@font-face`: `document.fonts.check('80px Bundled')` → True offline.
  - `python-lucide` 0.2.24: `lucide_icon('chart-bar', width, height, stroke)` → SVG string; `get_icon_list()` → 1694 iconos; `'chart-bar'` ✓ / `'bar-chart'` ✗.
- Context7 `/websites/playwright_dev_python` — `page.screenshot` (animations, scale, clip, full_page, type), `set_viewport_size`, `device_scale_factor`, `set_content` (wait_until, sin base URL), `wait_for_function`, `page.evaluate` (auto-await de promesas).
- Codebase (leído): `orchestrator.py`, `stages/base.py`, `stages/stubs.py`, `stages/storyboard.py`, `integrations/anthropic.py`, `utils/workdir.py`, `models/{storyboard,slides,config}.py`, `utils/cost_estimator.py`, `tests/{conftest,test_storyboard}.py`.
- CLAUDE.md (tech stack pineado, restricciones de visuales).

### Secondary (MEDIUM confidence)
- PyPI: `playwright` latest 1.60.0; `python-lucide` 0.2.24 (2026-03-29) — vía WebFetch a pypi.org/pypi/.../json.
- WebSearch (verificado contra issues oficiales de microsoft/playwright): pitfall de fuentes offline en headless Chromium y ausencia de fontconfig en `chromium-headless-shell` (relevante para Docker/Phase 7).

### Tertiary (LOW confidence)
- Detalles de inclusión de package-data con `uv_build` — no verificados en sesión (Open Q #4 / A2).
- Licencia OFL exacta de la fuente por defecto — a confirmar (Open Q #3 / A1).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — todas las versiones verificadas por import/PyPI; smoke tests reales ejecutados.
- Architecture: HIGH — encaja con patrones existentes (StageProtocol, call_structured, WorkdirManager); render verificado end-to-end.
- Pitfalls: HIGH — los dos pitfalls de mayor riesgo (fonts.ready + base64 offline) verificados empíricamente, no asumidos.
- Empaquetado (package-data) y licencia de fuente: MEDIUM/LOW — diferidos a Phase 7 / a confirmar.

**Research date:** 2026-05-25
**Valid until:** 2026-06-24 (30 días — stack estable y pineado en CLAUDE.md)
