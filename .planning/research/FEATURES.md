# Feature Research

**Domain:** CLI pipeline — bullets/contexto → storyboard IA → slides generadas → voz TTS → vídeo narrado con subtítulos
**Researched:** 2026-05-25
**Confidence:** HIGH (stack bien documentado; patrones verificados contra fuentes oficiales y research papers de 2025)

---

## Feature Landscape

### Table Stakes (Los usuarios los dan por supuestos)

Features que se asumen presentes. Su ausencia hace el producto inservible o incompleto.

| Feature | Por qué se espera | Complejidad | Notas |
|---------|-------------------|-------------|-------|
| **Entrada desde bullets + duración objetivo** | Es el punto de entrada del pipeline; sin él no hay producto | BAJA | YAML/JSON; `typer` para CLI; validación Pydantic |
| **Storyboard/guion generado por IA** | Los sistemas actuales (AutoLectures, PresentAgent) generan narración automáticamente desde LLM | MEDIA | Anthropic SDK, Claude más reciente; JSON estructurado con num_slides + bullet_per_slide + word_budget |
| **Calibración WPM ↔ duración** | Sin esto el vídeo resultante nunca encaja en la duración objetivo; es la razón de ser del pipeline | MEDIA | Director de timing: `words = duration_s / 60 * WPM`; WPM configurable (default 150); reparto por slide proporcional a peso de contenido |
| **Generación de slides en modo auto** | Sin slides no hay vídeo; el modo auto es el camino feliz sin intervención del usuario | ALTA | Jinja2 → HTML → Playwright → PNG 1920×1080 (deviceScaleFactor=2); solo SVG Lucide/Heroicons; theme.yaml |
| **Síntesis de voz TTS (ElevenLabs)** | Los pipelines modernos esperan TTS de calidad con timestamps; ElevenLabs ofrece endpoints con word-level alignment | MEDIA | `eleven_multilingual_v2`; endpoint `/v1/text-to-speech/{voice_id}/with-timestamps`; devuelve JSON con char/word timings |
| **Subtítulos .srt / .vtt generados siempre** | Accesibilidad y usabilidad multiplataforma; es expectativa en cualquier vídeo de presentación moderna | BAJA | Derivados directamente de los timings ElevenLabs (modo elevenlabs) o WhisperX (modo record); sin coste extra |
| **Montaje final con FFmpeg** | El usuario espera un archivo MP4 listo para usar, no carpetas de assets | ALTA | `ffmpeg` vía subprocess; concat de slides (imagen → stream de vídeo) + audios por slide; 1080p 16:9; sin MoviePy |
| **Salida 1080p 16:9 por defecto** | Estándar de facto para presentaciones tipo keynote/webinar | BAJA | Resolución y aspect ratio configurables como parámetro; 16:9 hardcoded como default |
| **Orquestador con checkpoints reanudables** | Los pipelines largos (IA + TTS + render) fallan; el usuario no quiere re-empezar desde cero | ALTA | Estado en `workdir/`; cada etapa lee/escribe JSON tipado; re-ejecutar una etapa es idempotente |
| **4 niveles de automatización (L1–L4)** | Control granular sobre cuándo pausar para revisión humana es expectativa en pipelines con IA generativa | MEDIA | L1=manual en cada paso; L2=aprueba storyboard+guion; L3=aprueba solo en fallo; L4=fully automated |
| **Ingestión de contexto opcional (.pptx/.pdf/.md)** | Los usuarios con materiales previos esperan poder alimentarlos al pipeline para coherencia de contenido | MEDIA | PyMuPDF para PDF; python-pptx para PPTX; extrae texto de referencia para Claude |
| **README con instrucciones de instalación** | Setup de Playwright browsers + FFmpeg + modelos WhisperX es no trivial; sin docs claras = tasa de abandono alta | BAJA | Cubre: `uv`, Playwright, FFmpeg, WhisperX/Torch, variables de entorno |

### Differentiators (Ventaja competitiva)

Features que diferencian el producto. No son esperadas, pero aportan valor real.

| Feature | Propuesta de valor | Complejidad | Notas |
|---------|-------------------|-------------|-------|
| **Verificador de slides con visión (Claude)** | Ningún pipeline open-source verifica automáticamente que las slides generadas/aportadas cubren el guion; cierra el bucle de calidad | ALTA | Solo en modos hybrid/manual; informe JSON por slide: {ok/warning/fail, cobertura_contenido, fidelidad_tema, encaje_guion, completitud}; Claude Opus 4.7 acepta imágenes hasta 2576px |
| **3 modos de slides (auto/hybrid/manual)** | Flexibilidad única: desde el pipeline completamente automatizado hasta el usuario que quiere usar sus propias slides | ALTA | auto: Playwright; hybrid: propuesta IA + slides del usuario; manual: slides del usuario puras |
| **`--dry-run` con estimación de coste y tokens** | Los usuarios de pipelines con IA necesitan saber el coste antes de lanzar; es una feature muy valorada pero rara en herramientas similares | MEDIA | Cuenta tokens (Anthropic SDK + tiktoken); estima llamadas ElevenLabs (chars × precio); calcula duración estimada; no genera audio ni vídeo |
| **Quemado opcional de subtítulos (flag)** | Dos mundos: vídeo limpio para edición posterior o vídeo con captions embedded listo para RRSS; ambos sin trabajo extra | BAJA | `--burn-subs` flag; FFmpeg `subtitles` filter; re-encode necesario; sin flag = soft subs en contenedor MKV o MP4 |
| **Normalización de loudness (EBU R128)** | La narración sintetizada por ElevenLabs puede tener variaciones de nivel entre slides; el usuario espera un vídeo con audio uniforme | BAJA | FFmpeg `loudnorm=I=-16:TP=-1.5:LRA=11`; pasada de análisis + pasada de corrección; QA report incluye LUFS medido |
| **Modo `record`: exporta guion segmentado + alineación WhisperX** | Permite locución humana con alineación automática; único en herramientas CLI de este tipo | ALTA | Exporta `script_segmented/slide_XX.txt`; graba con `sounddevice` o acepta `slide_XX.wav`; WhisperX forced alignment → word-level timestamps; pyannote no requerido (single speaker) |
| **Crossfade configurable entre slides** | Transiciones suaves mejoran la percepción de calidad del vídeo final sin trabajo editorial | BAJA | FFmpeg `acrossfade` en audio; `xfade` en vídeo; duración configurable (default 0.3s); puede desactivarse con `--no-crossfade` |
| **Informe QA: duración real vs objetivo** | Cierre del bucle: el usuario sabe cuánto se desvió el vídeo de su objetivo de duración | BAJA | Calculado tras el montaje; diferencia en segundos y porcentaje; incluido en `qa_report.json` |
| **Slides pixel-perfect vía HTML/CSS (Playwright)** | Control total sobre el diseño sin dependencia de PowerPoint; reproducible y editable como CSS plano | ALTA | `deviceScaleFactor=2`; 1920×1080 viewport; iconos SVG inline (Lucide/Heroicons); `theme.yaml` con paleta + tipografía |
| **Export opcional a .pptx (python-pptx)** | Los usuarios quieren a veces editar las slides después en PowerPoint; ofrece ese puente sin ser el flujo principal | MEDIA | `--export-pptx` flag; secundario al flujo principal HTML→PNG; python-pptx inserta las imágenes PNG como slides |
| **Configuración de idioma de narración** | español por defecto; multilingüe vía `eleven_multilingual_v2`; relevante para audiencias internacionales | BAJA | Parámetro `--language`; Claude recibe instrucción de idioma en el system prompt del guionista |
| **Diseño de tema propuesto por IA (theme.yaml)** | Elimina la necesidad de que el usuario defina colores/tipografía; la IA propone un tema coherente con el contenido | MEDIA | Claude genera `theme.yaml` en la etapa de storyboard; override manual permitido; paleta + font-family + tamaños |
| **Dockerfile con Playwright + FFmpeg + WhisperX** | Reproducibilidad total del entorno; el usuario no necesita instalar dependencias nativas complejas | MEDIA | Multi-stage build; playwright install --with-deps; FFmpeg static build; WhisperX + Torch |
| **Empaquetado con `uv` (pyproject.toml)** | `uv` es el gestor de entornos Python más rápido y moderno (2025); reduce el setup de minutos a segundos | BAJA | `pyproject.toml`; `uv sync`; no requiere pip/conda |

### Anti-Features (Explícitamente fuera de scope)

Features que parecen buenas pero crean problemas o están fuera del núcleo del producto.

| Anti-Feature | Por qué se pide | Por qué es problemático | Alternativa en este proyecto |
|--------------|-----------------|------------------------|------------------------------|
| **Generación de imágenes con IA (Dall-E, Stable Diffusion)** | Los usuarios quieren slides visualmente ricas con imágenes realistas | Inconsistencia visual entre slides; licencias ambiguas; coste adicional; no reproducible | Solo iconos SVG (Lucide/Heroicons) + gráficos por código; reproducibles al 100% |
| **Bancos de imágenes / stock photos** | Acelera el enrichment visual sin generar imágenes | Licencias complejas; dependencia de servicio externo; tamaño de assets impredecible | Mismo que arriba: SVG + código |
| **Orquestadores visuales (n8n, Zapier)** | Facilitan flujos no-code sin programación | Ocultan el control; añaden dependencia de servicio externo; dificultan debugging y extensión | Orquestador propio en Python: simple, tipado, testeable |
| **Frameworks pesados de agentes (LangGraph, AutoGen)** | Parecen simplificar pipelines multi-step con IA | El pipeline es lineal y secuencial; los frameworks de agentes añaden complejidad innecesaria y abstracciones que obstaculizan el control | Orquestador propio con etapas Pydantic-typed |
| **MoviePy para montaje de vídeo** | API Python más simple que FFmpeg subprocess | Rendimiento muy inferior a FFmpeg directo; abstracción con pérdida de control; no soporta el rango completo de filtros FFmpeg | FFmpeg directo vía subprocess |
| **Salida 9:16 vertical como default** | Formato dominante en RRSS (Reels, TikTok, Shorts) | Fuera del caso de uso principal (presentación/keynote); requiere refactor de templates de slides | 16:9 por defecto; 9:16 puede añadirse como extensión futura |
| **Partir de .pptx existente como flujo principal** | Los usuarios con decks existentes quieren reusar el diseño | Complejidad de parseo de estilos PowerPoint; resultado visual inconsistente; desvía del propósito de generación | Modos hybrid/manual permiten ingerir slides del usuario; la IA no empieza desde el .pptx |
| **Marca/branding propio como input obligatorio** | Los equipos de empresa quieren que el vídeo respete su identidad de marca | Aumenta la complejidad del onboarding; no todos los usuarios tienen brand guidelines formales | El tema lo propone la IA; override manual de `theme.yaml` es suficiente |
| **Real-time streaming de vídeo generado** | Algunos usuarios esperan preview durante la generación | Añade complejidad de streaming (websockets, chunks); el pipeline secuencial no lo justifica | Progreso por etapas visible vía `rich` en terminal |
| **Avatares o lip-sync (Wav2Lip)** | Algunos quieren un "presentador virtual" | Añade modelos de deep learning pesados; latencia alta; no es el caso de uso (slides, no cara hablante) | La narración de voz en off sobre slides es el producto |
| **Edición post-producción interactiva (timeline)** | Los usuarios avanzados quieren ajuste fino tras el montaje | Herramienta diferente (DaVinci, Premiere); añadiría complejidad de GUI incompatible con CLI | El pipeline genera assets intermedios (`audio/`, `subs/`, `slides/`) editables por cualquier editor |
| **Soporte multi-voz / diálogo** | Para contenidos con varios personajes o entrevistas | Complejidad de asignación de voz por segmento; fuera del caso de uso (monólogo narrativo) | ElevenLabs soporta multi-speaker en otros endpoints; puede ser extensión futura |

---

## Feature Dependencies

```
[Ingestión de contexto (.pptx/.pdf/.md)]  (opcional)
    └──alimenta──> [Storyboard IA (Claude)]
                       ├──requiere──> [Director de timing (WPM × duración)]
                       │                  └──produce──> [Presupuesto palabras/slide]
                       │                                     └──requiere──> [Guionista IA (Claude)]
                       │                                                         └──produce──> [script.json]
                       └──produce──> [storyboard.json]
                                          └──requiere──> [Generación de slides]
                                                              ├── modo auto: [Jinja2 → HTML → Playwright → PNG]
                                                              ├── modo hybrid: [Propuesta diseño IA + slides usuario]
                                                              └── modo manual: [Slides usuario directamente]

[Generación de slides (hybrid/manual)]
    └──requiere──> [Verificador de slides (Claude visión)]
                       └──produce──> [verification_report.json]
                                          └──controla──> [Niveles L1/L2: siempre pausa | L3/L4: pausa solo en fail]

[script.json]
    ├──alimenta──> [Voz ElevenLabs]
    │                  └──devuelve──> [audio/ + timings.json (word-level)]
    │                                     └──produce──> [Subtítulos .srt/.vtt]
    └──alimenta──> [Voz record]
                       ├──exporta──> [guion segmentado slide_XX.txt]
                       └──ingesta──> [slide_XX.wav grabado/aportado]
                                         └──requiere──> [WhisperX forced alignment]
                                                             └──produce──> [timings.json (word-level)]

[slides/PNG] + [audio/WAV] + [timings.json]
    └──requieren──> [Montaje FFmpeg]
                        ├──aplica──> [Crossfade (audio: acrossfade | vídeo: xfade)]
                        ├──aplica──> [Normalización loudness (loudnorm EBU R128)]
                        ├──aplica──> [Quemado subtítulos (flag --burn-subs)]
                        └──produce──> [output.mp4 1080p 16:9]
                                          └──requiere──> [QA: duración real vs objetivo + LUFS report]

[--dry-run]
    └──estima──> [tokens LLM (storyboard + guion + verificador) + chars ElevenLabs]
                     └──calcula──> [coste estimado + duración estimada]
                                       (sin generar audio/vídeo)

[Checkpoints reanudables]
    └──depende-de──> [workdir/ con JSON por etapa]
                         └──requiere──> [Pydantic typed I/O por etapa]
                                             └──habilita──> [Idempotencia: re-ejecutar = no duplica trabajo]

[4 niveles L1–L4] ──controlan──> [todos los puntos de aprobación humana]
    L1: pausa antes de storyboard, guion, slides, voz, montaje
    L2: pausa en storyboard + guion; continua si verificador ok
    L3: pausa solo si verificador tiene fail
    L4: fully automated, sin pausas

[Dockerfile] ──envuelve──> [Playwright browsers + FFmpeg + WhisperX + Torch]
    └──requiere──> [pyproject.toml con uv]
```

### Notas de dependencias clave

- **WhisperX requiere slides en modo record:** La alineación forzada solo es necesaria cuando el audio lo graba el usuario. En modo ElevenLabs, los timestamps vienen del propio API — sin WhisperX.
- **Verificador requiere imágenes de slides:** Solo operativo en modos `hybrid`/`manual`. En modo `auto` el pipeline confía en la generación propia. El verificador rasteriza .pptx/.pdf con pdf2image antes de enviar a Claude visión.
- **Crossfade depende del montaje:** No es una etapa propia; es un parámetro de la etapa FFmpeg. Complejidad baja una vez FFmpeg subprocess está implementado.
- **`--dry-run` no depende de ninguna otra etapa de ejecución:** Corre tokenización offline + estimación de precios hardcoded; puede ejecutarse antes de tener cualquier output.
- **Normalización de loudness es dos pasadas FFmpeg:** Primera pasada análisis → estadísticas; segunda pasada corrección con parámetros medidos. Añade ~50% de tiempo de montaje.
- **Export .pptx es postproceso opcional:** Requiere que las slides PNG estén generadas. `python-pptx` inserta las imágenes; no regenera el diseño.

---

## MVP Definition

### Launch With (v1) — Pipeline funcional end-to-end

Lo mínimo para validar el concepto completo: bullets → vídeo.

- [ ] **CLI `typer` + Pydantic config** — punto de entrada del sistema
- [ ] **Director de timing (WPM calibration)** — sin esto el vídeo nunca dura lo esperado
- [ ] **Storyboard IA (Claude)** — núcleo intelectual del pipeline
- [ ] **Guionista IA (Claude)** — narración calibrada por slide
- [ ] **Slides modo `auto` (Jinja2 + Playwright → PNG)** — el camino feliz sin intervención
- [ ] **Voz ElevenLabs con timestamps** — TTS de calidad + alineación sin WhisperX
- [ ] **Subtítulos .srt/.vtt desde timings** — accesibilidad y usabilidad básica
- [ ] **Montaje FFmpeg (concat + audio + 1080p)** — vídeo final entregable
- [ ] **Checkpoints reanudables (workdir/)** — sin esto los fallos de IA/TTS son bloqueantes
- [ ] **`--dry-run` con estimación de coste** — crítico para control de gasto antes de lanzar
- [ ] **L1–L4 niveles de automatización** — control de human-in-the-loop desde el inicio
- [ ] **Tests pytest mínimos** — storyboard mockeado, director de timing, render de una slide

### Add After Validation (v1.x) — Calidad + modos extra

Features a añadir una vez el pipeline base está probado en uso real.

- [ ] **Slides modo `hybrid` + Verificador Claude visión** — para usuarios con diseño propio; complejidad alta, validar demanda primero
- [ ] **Slides modo `manual`** — ingesta directa de slides del usuario sin verificación automática
- [ ] **Normalización de loudness (EBU R128)** — mejora la percepción de calidad del audio final
- [ ] **Crossfade audio/vídeo configurable** — refinamiento de calidad; bajo coste una vez FFmpeg está integrado
- [ ] **Quemado de subtítulos (`--burn-subs`)** — útil para distribución en RRSS; baja complejidad añadida
- [ ] **Ingestión de contexto (.pptx/.pdf/.md)** — para usuarios con materiales previos
- [ ] **QA report (duración real vs objetivo + LUFS)** — cierre del bucle de calidad

### Future Consideration (v2+) — Extensiones

Features a diferir hasta tener product-market fit validado.

- [ ] **Voz modo `record` + WhisperX** — alta complejidad (sounddevice + forced alignment); para usuarios que prefieren voz humana
- [ ] **Export .pptx (python-pptx)** — útil pero no core; defer hasta que haya demanda explícita
- [ ] **Soporte 9:16 vertical** — extensión de aspect ratio; requiere refactor de templates
- [ ] **Soporte multi-idioma avanzado** — más allá del parámetro `--language` básico
- [ ] **Branding/marca corporativa como input** — override completo de theme con brand guidelines

---

## Feature Prioritization Matrix

| Feature | Valor Usuario | Coste Implementación | Prioridad |
|---------|--------------|---------------------|-----------|
| CLI typer + Pydantic config | ALTO | BAJO | P1 |
| Director de timing WPM | ALTO | BAJO | P1 |
| Storyboard IA (Claude) | ALTO | MEDIO | P1 |
| Guionista IA (Claude) | ALTO | MEDIO | P1 |
| Slides modo auto (Playwright) | ALTO | ALTO | P1 |
| Voz ElevenLabs con timestamps | ALTO | MEDIO | P1 |
| Subtítulos .srt/.vtt | ALTO | BAJO | P1 |
| Montaje FFmpeg 1080p | ALTO | ALTO | P1 |
| Checkpoints reanudables | ALTO | MEDIO | P1 |
| `--dry-run` estimación coste | MEDIO | MEDIO | P1 |
| L1–L4 niveles automatización | ALTO | MEDIO | P1 |
| Tests pytest mínimos | MEDIO | BAJO | P1 |
| Verificador slides (Claude visión) | ALTO | ALTO | P2 |
| Slides modo hybrid | MEDIO | ALTO | P2 |
| Slides modo manual | MEDIO | BAJO | P2 |
| Normalización loudness EBU R128 | MEDIO | BAJO | P2 |
| Crossfade configurable | BAJO | BAJO | P2 |
| `--burn-subs` quemado subtítulos | MEDIO | BAJO | P2 |
| Ingestión contexto .pptx/.pdf | MEDIO | MEDIO | P2 |
| QA report duración + LUFS | MEDIO | BAJO | P2 |
| Voz modo record + WhisperX | MEDIO | ALTO | P3 |
| Export .pptx (python-pptx) | BAJO | MEDIO | P3 |
| Soporte 9:16 vertical | BAJO | ALTO | P3 |
| Dockerfile multi-stage | MEDIO | MEDIO | P2 |

**Clave de prioridad:**
- P1: Imprescindible para v1 funcional
- P2: Añadir tras validar el pipeline base (v1.x)
- P3: Diferir hasta v2+ o hasta demanda explícita

---

## Competitor Feature Analysis

| Feature | SlideNarrator (SaaS) | AutoLectures (Research, 2025) | PresentAgent (Research, 2024) | Nuestro Enfoque |
|---------|----------------------|-------------------------------|-------------------------------|-----------------|
| Input desde bullets | No (PPT/PDF como entrada) | Slides existentes | Documento estructurado | Sí — bullets + duración |
| Generación IA de guion | Sí (script AI) | Sí (LLM) | Sí (LLM) | Sí — Claude, idioma configurable |
| Calibración WPM/duración | No documentado | Implícito vía TTS | No explícito | Sí — WPM configurable, presupuesto por slide |
| TTS con word timestamps | Sí (AI voice) | Sí (TTS timestamps) | Sí (TTS) | Sí — ElevenLabs `/with-timestamps` |
| Subtítulos .srt/.vtt | No documentado | Sí (highlight sync) | Sí (captions) | Sí — siempre generados |
| Quemado de subtítulos | No | No (highlights visuales) | Sí | Sí — flag `--burn-subs` |
| Slides generadas programáticamente | No (usa PPT del usuario) | No (usa slides originales) | Sí (render) | Sí — Jinja2 + Playwright |
| Verificador IA de slides | No | No | No | Sí — Claude visión (diferenciador) |
| Modos de slides (auto/hybrid/manual) | No (solo manual) | Solo auto | Solo auto | Sí — 3 modos |
| Voz humana grabada | No | No | No | Sí — modo record + WhisperX |
| Dry-run / estimación de coste | No | No | No | Sí — diferenciador |
| Checkpoints reanudables | No | No | No | Sí — diferenciador |
| Niveles de automatización | No (fully auto SaaS) | Fully auto | Fully auto | Sí — L1–L4 |
| Control del código | No (SaaS cerrado) | Research paper | Research paper | Sí — open, Python local |
| Normalización loudness | No documentado | No | No | Sí — EBU R128 FFmpeg |
| Crossfade | No documentado | No | No | Sí — configurable |
| Dockerfile | No (SaaS) | No | No | Sí |

---

## Sources

- [AutoLectures: Generating Narrated Lecture Videos from Slides with Synchronized Highlights (arXiv, 2025)](https://arxiv.org/html/2505.02966v1)
- [PresentAgent: Multimodal Agent for Presentation Video Generation (arXiv, 2024)](https://arxiv.org/html/2507.04036v1)
- [ElevenLabs: Create speech with timing — word-level alignment API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)
- [ElevenLabs: Forced Alignment capability](https://elevenlabs.io/docs/overview/capabilities/forced-alignment)
- [WhisperX: Word-level timestamps + forced alignment (GitHub)](https://github.com/m-bain/whisperX)
- [FFmpeg loudnorm filter: EBU R128 loudness normalization](https://ffmpeg.org/ffmpeg-filters.html)
- [ffmpeg-normalize PyPI package](https://github.com/slhck/ffmpeg-normalize)
- [Playwright Python — Screenshots (oficial)](https://playwright.dev/python/docs/screenshots)
- [SlideNarrator — PowerPoint to narrated video SaaS](https://www.slidenarrator.com/)
- [tokencost — Easy token price estimates CLI tool](https://github.com/AgentOps-AI/tokencost)
- [Human-in-the-Loop patterns for AI Agents (2026)](https://myengineeringpath.dev/genai-engineer/human-in-the-loop/)
- [AI Content Pipeline Anti-Patterns: Quality Failure Modes (2026)](https://www.digitalapplied.com/blog/ai-content-pipeline-anti-patterns-quality-failure-modes-2026)
- [Claude Vision API capabilities (Anthropic)](https://platform.claude.com/docs/en/build-with-claude/vision)
- [PyMuPDF documentation (2026)](https://pymupdf.readthedocs.io/en/latest/)

---

*Feature research for: CLI pipeline bullets → vídeo narrado (slides + voz + subtítulos)*
*Researched: 2026-05-25*
