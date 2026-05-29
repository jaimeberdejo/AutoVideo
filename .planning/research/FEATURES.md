# Feature Research

**Domain:** Guided multi-step creation wizard (Streamlit UI) sobre pipeline CLI de vídeo narrado existente (v1.60.0)
**Researched:** 2026-05-29
**Confidence:** HIGH para Streamlit UX patterns y dependencias en pipeline; MEDIUM para OpenAI Audio timestamps (limitación documentada); MEDIUM para audio enhancement (pedalboard/noisereduce bien documentados pero complejidad de integración a validar)

---

## Feature Landscape

### Table Stakes (Los usuarios los dan por supuestos)

Features que se asumen presentes en cualquier wizard guiado. Su ausencia hace el producto incompleto o frustrante.

| Feature | Por qué se espera | Complejidad | Notas / Dependencias en pipeline |
|---------|-------------------|-------------|----------------------------------|
| **Wizard de 6 fases con barra de progreso** | Los wizards sin indicador de posición generan ansiedad en el usuario; es la convención de facto en cualquier flujo multi-step | BAJA | Implementar con `st.session_state["phase"]` (int 1–6) + stepper visual custom (HTML/CSS via `st.markdown`). Streamlit nativo no tiene un componente stepper, pero la comunidad tiene patrones bien establecidos. |
| **Gating obligatorio por fase (no avanzar sin confirmar)** | El punto de valor central del studio: el usuario controla cada checkpoint. Avanzar sin confirmación destruye la confianza | BAJA | Botón "Confirmar y continuar" en `disabled=True` hasta que la fase produce output válido. Estado gateado en `st.session_state`. No requiere cambios al pipeline — el pipeline CLI ya tiene checkpoints en `workdir/`. |
| **Navegación "Editar fase anterior"** | Los wizards sin retroceso fuerzan empezar desde cero; expectativa universal en formularios multi-paso | MEDIA | Navegar atrás es limpiar el `phase` en session state. El riesgo: el pipeline ya tiene checkpoints idempotentes en `workdir/`; retroceder a Fase 2 no borra `script.json` automáticamente — necesita invalidar checkpoints descendientes manualmente. Implementar `invalidate_from(phase)` que elimina archivos de checkpoint de fases posteriores. |
| **Feedback de progreso durante operaciones largas (render, TTS, montaje)** | Sin feedback el usuario asume que el app se colgó. Esperas silenciosas > 3s requieren indicación visual | MEDIA | `st.status` + `st.spinner` para mostrar etapas. El pipeline CLI escribe logs en stderr via `rich`; capturar con `subprocess.Popen` + `stdout=PIPE` y alimentar a `st.status` en tiempo real (threading en Streamlit: `st.fragment` para aislar la zona de progreso). |
| **Preview de slides como thumbnails** | El usuario debe ver qué va a aprobar antes de confirmar; no se puede pedir confirmación de algo no visible | BAJA | `st.image` nativo de Streamlit; las PNGs ya están en `workdir/slides/`. Grid de columnas con `st.columns(N)`. No requiere nuevas etapas. |
| **Preview y descarga del vídeo final** | El usuario espera ver el resultado dentro de la misma interfaz antes de descargar | BAJA | `st.video(open("output.mp4","rb").read())` + `st.download_button`. Funciona con archivos locales. Limitación: vídeos >200MB pueden tener latencia en el buffer del navegador; el caso de uso normal (5–15 min, H.264) estará bien. |
| **Selección de proveedor de voz (ElevenLabs / OpenAI / Grabación propia)** | El usuario con distintas cuentas de API espera elegir su proveedor; es el equivalente visual de `--voice` en CLI | BAJA | `st.radio` o `st.selectbox`. Condicionalmente renderizar campos de configuración (voice_id para ElevenLabs, voz para OpenAI). Mapea directamente al flag `--voice` del CLI. |
| **Subida de archivos de usuario (slides, audio)** | Los modos `hybrid`/`manual` requieren que el usuario aporten assets; la UI necesita `st.file_uploader` | BAJA | `st.file_uploader(type=["pdf","png","jpg","mp3","wav","m4a"])`. Guardar a `workdir/` antes de llamar al pipeline. Límite 200MB por defecto en Streamlit; configurable con `server.maxUploadSize`. |
| **Subtítulos on/off y quemado opcional** | Control básico sobre el output final; es un flag simple (`--burn-subs`) que el usuario espera ver en la UI | BAJA | `st.checkbox("Quemar subtítulos en vídeo")`. Mapea 1:1 a `--burn-subs`. Sin lógica nueva. |

### Differentiators (Ventaja competitiva de v2.0.0)

Features que convierten el CLI en un Studio guiado de calidad diferencial.

| Feature | Propuesta de valor | Complejidad | Notas / Dependencias en pipeline |
|---------|-------------------|-------------|----------------------------------|
| **Auto-generación de bullets desde un tema (Claude)** | Elimina la barrera de entrada para usuarios que no tienen bullets preparados; el usuario solo describe el tema | MEDIA | Nueva llamada a Claude (storyboard stage extendida o etapa propia: `BulletGenerator`). Prompt: "Dado el tema X y duración Y minutos, genera N bullets concretos". Output → `st.data_editor` editable. Dependencia: `anthropic` SDK (ya disponible). Necesita nueva etapa o sub-etapa antes de `storyboard`. |
| **Revisión interactiva del guion con variaciones por slide** | Permite al usuario editar el texto de narración por slide y pedir variaciones de Claude sin salir de la UI | ALTA | `st.text_area` por slide (editable), botón "Pedir variación" que lanza llamada Claude con el guion de esa slide como contexto. Requiere lógica de loop: editar → re-validar presupuesto WPM → actualizar `script.json`. Dependencia: `script.json` en `workdir/` + `anthropic` SDK. |
| **Verificador visual de slides con feedback por slide (ok/warning/fail)** | Muestra el informe JSON de Claude Vision en la UI con color-coding; el usuario ve exactamente qué slide tiene problemas | MEDIA | El `verification_report.json` ya existe en el pipeline. La UI lo lee y presenta con `st.columns`: thumbnail + badge de color (verde/amarillo/rojo) + texto de issues. Botón "Re-subir slides" para iterar. No requiere cambios al pipeline — solo lectura + presentación del JSON existente. |
| **Re-upload de slides tras verificación con re-ejecución del verificador** | Cierra el loop de calidad en la UI: el usuario corrige y vuelve a verificar sin salir del studio | MEDIA | `st.file_uploader` → reemplaza archivos en `workdir/slides_user/` → invoca `verify_slides` stage aislada → actualiza `verification_report.json` → refresh de la UI. Requiere que las etapas del pipeline sean invocables de forma aislada (ya posible por diseño idempotente). |
| **Mejora automática de audio subido (denoise + normalize)** | Para grabaciones de micrófono del usuario, un solo botón eleva la calidad significativamente | ALTA | Nueva integración: `noisereduce` (espectral gating stationary + non-stationary) + `pedalboard` (Spotify) para compresión + ganancia, seguido de `ffmpeg loudnorm`. Pipeline: bytes from `st.file_uploader` → soundfile.read() → noisereduce.reduce_noise() → pedalboard chain → soundfile.write() → presenta waveform antes/después con `st.audio`. Dependencias nuevas: `noisereduce>=3.0`, `pedalboard>=0.9`. |
| **Selección de música de fondo + control de nivel** | Añadir atmósfera al vídeo con un solo archivo y un slider de volumen | ALTA | `st.file_uploader(type=["mp3","wav"])` + `st.slider("Volumen música", 0, 100, 30)`. Internamente: FFmpeg `sidechaincompress` para ducking (reducción automática cuando hay voz) + `afade` para intro/outro. El filtro `sidechaincompress` es nativo en FFmpeg; configuración: `threshold=0.02, ratio=4, attack=200ms, release=1000ms`. Requiere nueva lógica en la etapa `assemble`. |
| **Selector de transiciones entre slides** | Control visual de la experiencia de visionado; diferencia el resultado de un cut seco vs una presentación pulida | BAJA | `st.selectbox(["Sin transición", "Crossfade suave (0.3s)", "Crossfade largo (0.7s)"])`. Mapea al parámetro `--crossfade-duration` ya implementado en FFmpeg assemble. Sin nueva lógica. |
| **OpenAI Audio como tercer proveedor TTS** | Amplía opciones de voz para usuarios con créditos OpenAI; voces distintas a ElevenLabs | MEDIA | Nueva etapa `voice_openai.py` usando `openai.audio.speech.create(model="gpt-4o-mini-tts", voice="alloy")`. **Limitación crítica:** OpenAI TTS no devuelve word-level timestamps (confirmado; a diferencia de ElevenLabs que usa `/with-timestamps`). Workaround: post-procesar con WhisperX o Whisper API para alineación (añade latencia y coste). Alternativa más simple: usar OpenAI Whisper transcription (`response_format="verbose_json"`, `timestamp_granularities=["word"]`) sobre el audio generado. Dependencia nueva: `openai>=1.x` SDK. **Nota:** Este workaround es necesario para subtítulos sincronizados; si el usuario no necesita subtítulos, OpenAI TTS es plug-and-play. |
| **Thumbnails de slides interactivos (click para ver full-size)** | Mejora la revisión de slides antes de aprobar; ver en miniatura no es suficiente para detectar texto mal renderizado | MEDIA | `streamlit-image-gallery` o implementación custom con `st.image` + modal vía `st.dialog` (añadido en Streamlit 1.32+). Click en thumbnail → modal con imagen a escala completa. |
| **Indicadores de coste estimado por fase** | El usuario necesita saber cuánto va a gastar en LLM + TTS antes de confirmar cada fase con API calls | MEDIA | Extender el estimador de coste existente (`cost_estimator.py`) para ser invocable por la UI. Mostrar con `st.metric` (tokens Claude + coste ElevenLabs en chars). Se puede calcular offline antes de la llamada. |

### Anti-Features (Explícitamente fuera de scope)

Features que parecen buenas para un Studio pero crean problemas concretos.

| Anti-Feature | Por qué se pide | Por qué es problemático | Alternativa en este proyecto |
|--------------|-----------------|------------------------|------------------------------|
| **Multi-usuario / auth** | Para uso en equipo o como SaaS | El Studio es `localhost`, single-user por diseño; añadir auth duplicaría la complejidad. Streamlit Cloud multi-tenant requiere manejo de sessions totalmente distinto | Single-user local; desplegar múltiples instancias si se necesita multi-usuario |
| **Editing post-producción en la UI (timeline, corte)** | Los usuarios avanzados quieren ajuste fino tras el montaje | Esto es un editor de vídeo no-lineal — un producto diferente. La complejidad sería 10x el scope actual | Los assets intermedios (`audio/`, `slides/`, `subs/`) quedan accesibles en `workdir/` para cualquier editor externo |
| **Real-time preview durante generación (streaming de vídeo parcial)** | Algunos usuarios quieren ver el vídeo generarse progresivamente | FFmpeg no genera vídeo reproducible de forma incremental en el caso de uso (concat de imágenes); añadiría websockets y complejidad de buffer | `st.status` con progreso por etapa + thumbnails de slides ya generadas |
| **Auto-advance entre fases sin confirmación humana** | Para usuarios que quieren máxima automatización | Destruye el valor central del Studio: el human-check obligatorio. La CLI ya tiene L4 para eso | El modo L4 del CLI headless cubre ese caso |
| **Historial de proyectos / gestión de workdirs múltiples** | Para retomar proyectos anteriores y gestionar vídeos pasados | Requiere una capa de base de datos o índice de workdirs; no es el alcance del Studio guiado | El usuario gestiona `workdir/` manualmente; cada sesión es una carpeta; extensión futura |
| **Generación de imágenes IA para slides** | Los usuarios de herramientas SaaS esperan imágenes en sus slides | Decisión de diseño explícita (v1.60.0): solo SVG + código. Los workflows con imágenes IA no son reproducibles ni editorialmente consistentes | Iconos SVG (Lucide/Heroicons) inline en las templates HTML |
| **Edición del theme.yaml vía GUI de paleta de colores** | Color picker para no-técnicos | El usuario objetivo es técnico; un color picker visual tiene coste de implementación desproporcionado | Edición directa de `theme.yaml` con `st.code_editor` o `st.text_area` prellenado; la IA ya propone un tema coherente |
| **Modo "grabación en vivo" dentro del browser (st.audio_input)** | Streamlit 1.37+ tiene `st.audio_input`; parece conveniente | `st.audio_input` captura en el navegador con compresión WebM/Opus que puede degradar la calidad de la grabación; sounddevice/soundfile es superior para la cadena WhisperX | Subida de archivo WAV grabado externamente; el modo `record` vía CLI es más confiable para calidad de alineación |

---

## Feature Dependencies

```
[Fase 1 — Contenido]
    ├── MANUAL: st.text_input(tema) + st.number_input(duración)
    ├── AUTO: Claude BulletGenerator → st.data_editor(bullets editable)
    └── GATING: bullets no vacíos + duración > 0
              └── desbloquea Fase 2

[Fase 2 — Guion + Slides]
    ├── requiere: bullets (Fase 1 confirmada)
    ├── invoca: pipeline stages storyboard → timing → scriptwriter
    ├── presenta: st.text_area por slide (editable) + indicador WPM
    ├── bucle: "Pedir variación" → Claude → actualiza st.text_area
    └── GATING: usuario aprueba guion completo
              └── desbloquea Fase 3

[Fase 3 — Diapositivas]
    ├── modo AUTO: invoca slides_auto stage → PNGs → grid thumbnails → revisión
    │   ├── bucle: "Variación de diseño" → re-ejecuta slide_N → actualiza thumbnail
    │   └── GATING: usuario aprueba todas las slides
    ├── modo UPLOAD: st.file_uploader(pdf/png) → workdir/slides_user/
    │   ├── invoca: verify_slides stage (Claude Vision)
    │   ├── presenta: verification_report.json → badge ok/warning/fail por slide
    │   ├── bucle: re-upload → re-verificar
    │   └── GATING: sin slides con status "fail"
    └── desbloquea Fase 4

[Fase 4 — Voz]
    ├── selección: ElevenLabs | OpenAI Audio | Grabación propia
    ├── ElevenLabs: voice_id config → invoca voice_elevenlabs stage → timings.json (timestamps nativos)
    ├── OpenAI Audio: voice config → invoca voice_openai stage → audio → Whisper post-alineación → timings.json
    ├── Grabación propia: st.file_uploader(wav/mp3) → opcional: botón "Mejorar audio" (noisereduce + pedalboard) → WhisperX align → timings.json
    └── GATING: timings.json presente y válido
              └── desbloquea Fase 5

[Fase 5 — Extras]
    ├── subtítulos: st.checkbox on/off + st.checkbox burn-subs
    ├── música: st.file_uploader(mp3/wav) + st.slider(nivel 0–100) → FFmpeg sidechaincompress ducking
    ├── transiciones: st.selectbox(ninguna/crossfade 0.3s/0.5s/0.7s)
    └── GATING: siempre (no requiere acción; el usuario confirma opciones)
              └── desbloquea Fase 6

[Fase 6 — Ensamblaje]
    ├── invoca: assemble stage (FFmpeg) → qa stage
    ├── progress: st.status con etapas en tiempo real
    ├── presenta: st.video(output.mp4) + st.download_button
    └── GATING: QA sin fail crítico

[Navegación hacia atrás]
    └── requiere: invalidate_from(phase) → elimina checkpoints de workdir/ desde esa fase

[Mejora de audio (botón)]
    └── requiere: soundfile + noisereduce + pedalboard (nuevas deps)
    └── es independiente del proveedor de voz (solo para modo grabación propia)

[Música de fondo]
    └── requiere: Fase 6 (assemble) — se añade como nuevo argumento a la etapa
    └── FFmpeg sidechaincompress ya documentado; requiere extensión de assemble.py

[OpenAI Audio sin timestamps]
    └── requiere: post-alineación con Whisper API o WhisperX local → crea timings.json
    └── si el usuario no necesita subtítulos: timings.json = duración proporcional simple (sin word-level)
```

### Notas de dependencias clave

- **BulletGenerator requiere nueva sub-etapa Claude:** La Fase 1 (auto-bullets) no tiene equivalente en el pipeline v1.60.0. Necesita una nueva función/stage que llame a Claude antes que `storyboard`. La llamada es ligera (sin visión, sin imágenes); complejidad baja.
- **Invalidación de checkpoints es crítica para la navegación hacia atrás:** Streamlit reruns la página entera en cada interacción. Si el usuario vuelve a Fase 2 y reaprueba un guion distinto, `script.json` debe regenerarse y todos los archivos posteriores (`timings.json`, `audio/`, `subs/`, `output.mp4`) deben invalidarse. Sin esto, el usuario ve un vídeo con el guion anterior.
- **OpenAI Audio TTS no devuelve word timestamps:** Confirmado en la API actual. Para subtítulos sincronizados es necesario un paso de post-alineación (Whisper API o WhisperX local). Si no se necesitan subtítulos, OpenAI TTS es inmediato de integrar.
- **Mejora de audio (denoise+normalize) es una nueva dependencia de runtime:** `noisereduce` y `pedalboard` no están en el stack v1.60.0. Son librerías puras Python (sin binarios del sistema); añadir al `pyproject.toml` como dependencias opcionales del grupo `[record]` o `[studio]`.
- **Música de fondo extiende assemble.py:** No es una etapa nueva; es un argumento adicional a la etapa existente. FFmpeg `sidechaincompress` ya está documentado y disponible en FFmpeg >=3.1.
- **st.fragment aisla zonas de progreso:** Para operaciones largas (render Playwright, TTS ElevenLabs, FFmpeg), usar `@st.fragment` para que el indicador de progreso se actualice sin reruns completos. Esto es estable desde Streamlit 1.37.

---

## MVP Definition

### Launch With (v2.0.0) — Studio guiado funcional

Lo mínimo para que el Studio guiado tenga valor como superficie primaria de trabajo.

- [ ] **Wizard de 6 fases con gating obligatorio** — es el concepto central; sin él no hay Studio
- [ ] **Indicador de fase (stepper visual)** — el usuario necesita saber dónde está
- [ ] **Fase 1: entrada de tema + duración + auto-bullets Claude** — el flujo de onboarding
- [ ] **Fase 2: revisión editable del guion por slide** — el principal punto de control de calidad
- [ ] **Fase 3: thumbnails de slides para revisión + modo upload con verificador** — approve/iterate
- [ ] **Fase 4: selector de proveedor de voz (ElevenLabs + OpenAI Audio + subida propia)** — tabla stakes
- [ ] **Fase 5: controles de extras (subtítulos, música, transiciones)** — completeness
- [ ] **Fase 6: barra de progreso de ensamblaje + preview + descarga** — el cierre del loop
- [ ] **Navegación hacia atrás con invalidación de checkpoints** — sin esto el Studio es un callejón sin salida
- [ ] **Feedback de progreso en tiempo real (st.status)** — sin esto parece roto

### Add After Validation (v2.x)

Features a añadir una vez validado que el Studio guiado funciona end-to-end.

- [ ] **Mejora automática de audio subido (denoise + normalize)** — valor alto para modo grabación propia; dependencia nueva; validar demanda primero
- [ ] **Thumbnails full-size al click (modal)** — mejora la revisión de slides; baja complejidad una vez el grid está implementado
- [ ] **Indicadores de coste estimado por fase** — muy valorado; requiere que `cost_estimator.py` sea callable desde la UI

### Future Consideration (v2.1+)

Features a diferir hasta validar el Studio.

- [ ] **Historial de proyectos** — requiere índice de workdirs; diferir hasta que sea pedido explícitamente
- [ ] **Edición del theme.yaml visual** — color picker; diferir; el usuario técnico puede editar YAML directamente
- [ ] **Export .pptx desde la UI** — botón adicional; la lógica ya existe; diferir hasta demanda

---

## Feature Prioritization Matrix

| Feature | Valor Usuario | Coste Implementación | Prioridad |
|---------|--------------|---------------------|-----------|
| Wizard 6 fases + gating | ALTO | BAJO | P1 |
| Stepper visual / indicador de fase | ALTO | BAJO | P1 |
| Auto-bullets desde tema (Claude) | ALTO | MEDIO | P1 |
| Edición guion en UI (texto + variaciones) | ALTO | ALTO | P1 |
| Thumbnails slides + revisión | ALTO | BAJO | P1 |
| Verificador slides: badge ok/warning/fail | ALTO | BAJO | P1 |
| Selector proveedor de voz | ALTO | BAJO | P1 |
| OpenAI Audio TTS + post-alineación | MEDIO | ALTO | P1 |
| Progreso en tiempo real (st.status) | ALTO | MEDIO | P1 |
| Preview vídeo + descarga | ALTO | BAJO | P1 |
| Navegación hacia atrás + invalidación checkpoints | ALTO | MEDIO | P1 |
| Controles extras (subtítulos, transiciones) | MEDIO | BAJO | P1 |
| Música de fondo (ducking FFmpeg) | MEDIO | ALTO | P2 |
| Mejora automática de audio (denoise) | MEDIO | ALTO | P2 |
| Thumbnails full-size al click (modal) | MEDIO | BAJO | P2 |
| Indicadores de coste por fase | MEDIO | MEDIO | P2 |
| Historial de proyectos | BAJO | ALTO | P3 |
| Color picker para theme.yaml | BAJO | ALTO | P3 |

**Clave de prioridad:**
- P1: Imprescindible para lanzar v2.0.0 Studio Guiado
- P2: Añadir tras validar el Studio guiado funciona end-to-end
- P3: Diferir hasta v2.1+ o hasta demanda explícita

---

## Competitor Feature Analysis

| Feature | Synthesia | HeyGen | Descript | Nuestro Studio v2.0.0 |
|---------|-----------|--------|----------|-----------------------|
| Wizard guiado multi-paso | No (pantalla única) | Parcial (3 pasos) | No (editor tipo DAW) | Sí — 6 fases con gates |
| Human-check obligatorio entre fases | No (fully automated) | No | No | Sí — diferenciador clave |
| Generación de bullets desde tema | Sí (vía prompt) | No | No | Sí |
| Edición interactiva del guion | Sí | Sí | Sí | Sí |
| Pedir variaciones al LLM in-place | No | No | No | Sí — diferenciador |
| Verificador visual de slides (IA) | No | No | No | Sí — diferenciador |
| Mejora automática de audio subido | No | No | Parcial (enhance) | Sí (denoise + normalize) |
| OpenAI Audio como proveedor | No | No | No | Sí |
| Música de fondo con ducking automático | No | Sí (básico) | Sí | Sí (sidechaincompress) |
| Preview en la UI antes de descargar | Sí | Sí | Sí | Sí |
| Control total del código (local) | No (SaaS) | No (SaaS) | No (SaaS) | Sí — ventaja diferencial |
| Privacidad (todo local) | No | No | No | Sí — sin envío a cloud excepto LLM/TTS APIs |

---

## UX Behavior Expectations — Detalles Concretos por Feature

Esta sección es complementaria a la tabla de features y responde directamente a la pregunta de investigación. Documenta el comportamiento UX esperado tal como lo observa el usuario.

### Gating por fase y navegación hacia atrás

**Comportamiento esperado:** El botón "Siguiente fase" aparece deshabilitado (`disabled=True`) hasta que la fase produce output válido. Cuando el usuario hace clic en una fase anterior en el stepper, se muestra un diálogo de confirmación ("¿Editar esta fase descartará el trabajo posterior. ¿Continuar?"). Al confirmar, se limpian los checkpoints de `workdir/` desde esa fase hacia adelante y se navega atrás. El stepper muestra fases completadas (checkmark), fase activa (resaltada), fases futuras (grises). Las fases no se pueden saltarse.

**Patrón Streamlit:** `st.session_state["phase"]` como entero 1–6. El stepper es un `st.markdown` con HTML custom o columnas de iconos. El diálogo de confirmación usa `st.dialog` (disponible desde Streamlit 1.32). `invalidate_from(phase_n)` elimina archivos de workdir: si `n<=2` → elimina `script.json`, `slides/`, `timings.json`, `audio/`, `subs/`, `output.mp4`; si `n==3` → elimina `slides/`, `timings.json`, `audio/`, `subs/`, `output.mp4`; etc.

### Generación de bullets desde tema con aprobar/editar

**Comportamiento esperado:** El usuario escribe el tema (ej. "Introducción a los transformers") y la duración. Al hacer clic en "Generar bullets", aparece un spinner, y a continuación se muestra un `st.data_editor` con los bullets propuestos (una fila por bullet, editable en línea). El usuario puede añadir, borrar o editar bullets directamente en la tabla. Al hacer clic en "Aprobar bullets", se guardan en sesión y se habilita el paso a Fase 2.

**Patrón Streamlit:** `st.data_editor(pd.DataFrame({"bullet": bullets_list}))` — edición in-line nativa. La llamada a Claude es síncrona envuelta en `st.spinner`. El DataFrame editado se lee en `st.session_state["bullets"]` para pasarlo al pipeline.

### Loop de revisión de guion (editar / variaciones / iterar)

**Comportamiento esperado:** Tras generar el guion, se muestra una card por slide con: número de slide, duración asignada, presupuesto de palabras, y un `st.text_area` prellenado con el texto del guion. Al editar el texto, se recalcula automáticamente el WPM estimado en tiempo real (callback `on_change`). Un botón "Pedir variación a Claude" abre un formulario: "¿Qué quieres cambiar?" → el usuario escribe la instrucción → Claude reescribe esa slide → el `st.text_area` se actualiza. La iteración puede repetirse indefinidamente por slide. Cuando el usuario está conforme con todas las slides, hace clic en "Aprobar guion completo" → Fase 3.

**Patrón Streamlit:** Loop de slides con `for slide in script.slides: with st.expander(f"Slide {n}: {slide.title}"):`. El botón "Variación" es local a cada expander. Estado de edición por slide en `st.session_state["script_edits"][n]`. Los cambios manuales y las variaciones convergen en el mismo `text_area`.

### Verificador visual de slides (badge por slide)

**Comportamiento esperado:** Tras subir slides y ejecutar el verificador, se muestra una fila por slide con: thumbnail en miniatura (120×68px), badge de color (verde "OK" / amarillo "AVISO" / rojo "FALLO"), y los issues/sugerencias expandibles. Las slides con "FALLO" bloquean el avance (el botón de confirmar permanece deshabilitado). El usuario puede hacer clic en el badge para ver el detalle completo. Hay un botón "Re-subir slides" que abre el uploader de nuevo.

**Patrón Streamlit:** Leer `verification_report.json` (Pydantic model ya existe). Para cada slide: `col1, col2, col3 = st.columns([1, 2, 5])` → col1: `st.image(thumb_path, width=120)`, col2: badge HTML via `st.markdown`, col3: issues text. El badge se implementa con `st.markdown("<span style='background:#dc3545...'>FALLO</span>", unsafe_allow_html=True)`.

### Selección de proveedor de voz (UX)

**Comportamiento esperado:** `st.radio(["ElevenLabs", "OpenAI Audio", "Grabación propia"])`. Al seleccionar ElevenLabs: muestra campo para `voice_id` (o selector de voces si se llama al listado de la API). Al seleccionar OpenAI Audio: muestra `st.selectbox` con las 9 voces disponibles (alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer) + nota sobre limitación de timestamps ("Los subtítulos se generarán mediante post-alineación automática"). Al seleccionar Grabación propia: muestra `st.file_uploader` por slide o un uploader masivo + botón de mejora automática.

### Botón de mejora automática de audio

**Comportamiento esperado:** Tras subir un archivo de audio, aparece un botón "Mejorar calidad de audio". Al hacer clic: spinner "Analizando ruido…" → "Eliminando ruido…" → "Normalizando nivel…" → "Listo". Se muestran dos reproductores de audio (`st.audio`) lado a lado: "Original" y "Mejorado". El usuario puede escuchar ambos y elegir cuál usar. Un botón "Usar audio mejorado" confirma la selección.

**Implementación:** `noisereduce.reduce_noise(y=data, sr=rate, stationary=True)` para entornos controlados; `stationary=False` para ruido variable. Después, `pedalboard.Compressor(threshold_db=-20, ratio=4)` + `pedalboard.Gain(gain_db=6)`. Finalmente, un paso de loudnorm vía FFmpeg (ya disponible). El procesamiento puede tardar 2–10 segundos; `st.spinner` es suficiente.

### Música de fondo: selección + control de nivel

**Comportamiento esperado:** `st.file_uploader("Música de fondo", type=["mp3","wav","ogg"])` + `st.slider("Volumen de la música (%)", 0, 100, 30)`. Un preview del audio subido con `st.audio`. Nota informativa: "El volumen se reducirá automáticamente cuando haya narración (ducking)". El nivel del slider mapea a la ganancia inicial antes del ducking (ej. 30% → `-10.5dB` antes del sidechain).

**Implementación FFmpeg:** `sidechaincompress=threshold=0.02:ratio=4:attack=200:release=1000` con la voz como sidechain y la música como señal comprimida. El slider de nivel aplica un filtro `volume=X` a la música antes del sidechain. `afade=t=in:st=0:d=2` y `afade=t=out:st={end-2}:d=2` para entradas/salidas suaves.

### Progreso durante operaciones largas

**Comportamiento esperado:** Para cada operación larga (render Playwright ~2–15s por slide, TTS ElevenLabs ~3–8s por slide, FFmpeg montaje ~10–60s), el usuario ve: (1) un `st.status` expandido mostrando las sub-etapas completadas con checkmarks, (2) el número de slide actual ("Generando slide 3 de 8..."), (3) tiempo transcurrido. Las operaciones no bloquean el navegador (se usan threads con `st.fragment` para updates parciales).

**Patrón Streamlit:** `with st.status("Generando slides...", expanded=True) as status: status.update(label=f"Slide {i}/{n}", state="running")`. Para progreso granular: capturar stdout de subprocess con `Popen(stdout=PIPE)` y actualizar un `st.empty()` placeholder en un thread.

---

## Sources

- [Streamlit Session State — docs.streamlit.io](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state) — HIGH confidence
- [Streamlit Fragments (st.fragment) — docs.streamlit.io](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment) — HIGH confidence; disponible desde Streamlit 1.37
- [Streamlit st.status — docs.streamlit.io](https://docs.streamlit.io/develop/api-reference/status/st.status) — HIGH confidence
- [Streamlit st.video — docs.streamlit.io](https://docs.streamlit.io/develop/api-reference/media/st.video) — HIGH confidence
- [Streamlit Button behavior and callbacks](https://docs.streamlit.io/develop/concepts/design/buttons) — HIGH confidence; patrón `disabled=` confirmado
- [streamlit-wizard — PyPI / GitHub](https://github.com/archydeberker/streamlit-wizard) — MEDIUM confidence; patrón de referencia, no necesariamente la librería a usar
- [Streamlit Wizard Form — Andrew Carson](https://blog.streamlit.io/streamlit-wizard-and-custom-animated-spinner-2dcd52cccc65) — MEDIUM confidence
- [Streamlit threading docs](https://docs.streamlit.io/develop/concepts/design/multithreading) — HIGH confidence
- [OpenAI TTS API — No word timestamps](https://community.openai.com/t/openai-tts-transcription-time-stamps/1257285) — MEDIUM confidence; confirmado por múltiples fuentes de la comunidad; workaround con Whisper documentado
- [OpenAI Text-to-Speech guide](https://developers.openai.com/api/docs/guides/text-to-speech) — HIGH confidence; modelos y voces verificados
- [noisereduce — PyPI / GitHub](https://github.com/timsainb/noisereduce) — HIGH confidence; spectral gating stationary + non-stationary
- [pedalboard — Spotify / GitHub](https://github.com/spotify/pedalboard) — HIGH confidence; compresión + ganancia; producción Spotify
- [FFmpeg sidechaincompress filter (ducking)](https://ffmpeg.org/ffmpeg-filters.html) — HIGH confidence; filtro nativo FFmpeg
- [FFmpeg afade filter](https://ffmpeg.org/ffmpeg-filters.html) — HIGH confidence; nativo FFmpeg
- [Streamlit file_uploader — docs.streamlit.io](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader) — HIGH confidence; límite 200MB por defecto

---

*Feature research for: v2.0.0 Studio Guiado — Streamlit wizard sobre pipeline CLI existente (v1.60.0)*
*Researched: 2026-05-29*
