# Pitfalls Research

**Domain:** Pipeline Python para vídeo narrado — slides HTML→PNG (Playwright), voz ElevenLabs/WhisperX, montaje FFmpeg, storyboard/guion con API Anthropic
**Researched:** 2026-05-25 (v1) / 2026-05-29 (v2.0.0 Studio Guiado addendum)
**Confidence:** HIGH (mayoría de pitfalls verificados contra repositorios oficiales, issues de GitHub y documentación actual)

---

## Critical Pitfalls

### Pitfall 1: Fuentes no cargadas al hacer screenshot con Playwright

**What goes wrong:**
Playwright toma el screenshot antes de que las fuentes web (Google Fonts, fuentes locales vía @font-face) terminen de cargarse. El resultado es que el texto se renderiza con la fuente de fallback (generalmente serif o sans-serif del sistema), produciendo slides con aspecto incorrecto. En algunos casos la llamada a `page.screenshot()` queda colgada indefinidamente si la petición de fuente falla en red.

**Why it happens:**
Los eventos `domcontentloaded` y `load` no esperan a que el subsistema de fuentes (`FontFace`) resuelva. Playwright da por lista la página cuando el DOM está parseado, no cuando las fuentes están pintadas. Además, en headless Chromium bajo Linux (Docker) faltan paquetes de fuentes del sistema, lo que fuerza fallback silencioso sin error.

**How to avoid:**
- Añadir `await page.wait_for_function("document.fonts.ready")` explícitamente antes de llamar a `screenshot()`.
- Instalar en el Dockerfile los paquetes de fuentes del sistema: `fonts-liberation`, `fonts-noto-core`, `fonts-noto-color-emoji`, `fonts-freefont-ttf`, y ejecutar `fc-cache -fv`.
- Usar fuentes autoprovisionadas (variables CSS o fuentes de sistema), no CDNs externas, para garantizar disponibilidad offline.
- Nunca confiar en fuentes de CDN en el pipeline: copiar los archivos de fuente al directorio de la slide y referenciarlos con rutas relativas en el HTML.
- Si se usan Google Fonts u otras fuentes externas en `theme.yaml`, descargarlas en `assets/fonts/` y servirlas localmente.

**Warning signs:**
- El texto en los PNG se ve diferente al preview en navegador local.
- El screenshot tarda más de 10 segundos en slides simples.
- Los PNG muestran texto con serif/sans incorrecto en CI pero no en local Mac.

**Phase to address:**
Fase de generación de slides (módulo Playwright). Verificar en el test de render de una slide con la fuente del tema.

---

### Pitfall 2: Gráficos JS no renderizados al tomar el screenshot

**What goes wrong:**
Las slides con gráficos generados por código (Chart.js, D3, Vega-Lite) muestran canvas en blanco o SVG vacío en el PNG. El gráfico existe en el DOM pero no ha completado su ciclo de animación/render.

**Why it happens:**
Las bibliotecas de gráficos basadas en canvas/SVG ejecutan el render en el siguiente tick del event loop o tras una animación de entrada (requestAnimationFrame). Playwright puede hacer el screenshot justo antes de que ese tick se procese. En modo headless la API de animaciones puede comportarse distinto al modo headed.

**How to avoid:**
- Deshabilitar todas las animaciones en el HTML generado: `* { animation: none !important; transition: none !important; }`.
- Añadir un selector estable al DOM (p.ej. `data-render-complete="true"`) que el propio código JS del gráfico establece al final del render, y esperar con `page.wait_for_selector('[data-render-complete]')`.
- Como alternativa simple: pasar `animations='disabled'` al llamar a `page.screenshot(animations='disabled')` (opción nativa de Playwright).
- Para gráficos por código (matplotlib, plotly exportado a SVG estático), preferir SVG inline en lugar de canvas: el SVG es síncrono y no requiere espera de render.

**Warning signs:**
- Canvas en blanco en PNG pero correcto al abrir el HTML en el navegador.
- Diferencias entre ejecuciones sucesivas del mismo HTML (flakiness).

**Phase to address:**
Fase de generación de slides `auto`. Documentar en `theme.yaml` la convención `data-render-complete`.

---

### Pitfall 3: Deriva de timing audio/slide (drift acumulado)

**What goes wrong:**
El vídeo final tiene sincronía correcta al inicio pero el audio llega tarde (o adelantado) respecto a la slide correspondiente al acercarse al final. Con 10 slides y desviaciones de ±50 ms por slide, el error acumulado puede superar 0.5 s — perceptible y molesto.

**Why it happens:**
La duración real del audio generado por ElevenLabs nunca coincide exactamente con la duración calculada por WPM. El modelo puede hablar más rápido o más lento según la puntuación, el idioma, las pausas entre frases y la voz seleccionada. Si el montaje usa la duración estimada (en vez de la duración real del fichero de audio) para calcular cuándo comienza cada slide, el error se acumula slide a slide.

**How to avoid:**
- **Medir la duración real** de cada `slide_XX.mp3` con `ffprobe -v quiet -show_entries format=duration` antes del montaje, nunca fiarse de la duración estimada por WPM.
- En el `concat` de FFmpeg, calcular el offset de cada slide a partir de la suma de duraciones reales de los audios anteriores, no de las estimaciones.
- Guardar las duraciones reales en `timings.json` como parte del checkpoint — ese fichero es la fuente de verdad del montaje.
- Ejecutar el QA de duración total (`duración_real vs objetivo`) y loguear la desviación por slide en el informe.

**Warning signs:**
- La última slide se corta antes de que acabe el audio, o el audio continúa sobre un frame negro.
- El QA reporta desviación acumulada > 5% de la duración objetivo.
- `ffprobe` sobre el vídeo final muestra streams de audio y vídeo con duraciones diferentes.

**Phase to address:**
Fase de montaje FFmpeg. El director de timing debe calcular presupuesto de palabras, pero el montador debe usar duraciones reales medidas con `ffprobe`.

---

### Pitfall 4: Calibración WPM inexacta para duración objetivo

**What goes wrong:**
El sistema reparte el presupuesto de palabras a 150 WPM. Claude escribe el guion con ese conteo. ElevenLabs sintetiza el audio y la duración real supera el objetivo en un 15-25%, obligando a cortar slides o producir un vídeo más largo de lo esperado.

**Why it happens:**
150 WPM es la velocidad de lectura estándar, pero ElevenLabs en español no habla a exactamente 150 WPM. La velocidad real depende de: la voz concreta, la densidad de consonantes/vocales del español, la puntuación (puntos, comas generan pausas), el `stability` y `similarity_boost` configurados, y el modelo (`eleven_multilingual_v2` vs Flash). Sin calibración empírica, la estimación por WPM puede tener un error del 10-20%.

**How to avoid:**
- Realizar una **calibración empírica** en la fase de setup: generar un texto de 100 palabras en español con la voz y configuración exacta que se usará en producción, medir la duración real del audio y calcular el WPM efectivo. Usar ese WPM como parámetro ajustado, no 150 como asunción.
- Añadir un **margen de seguridad configurable** (por defecto -10%) al presupuesto de palabras por slide para absorber variaciones.
- En el `--dry-run`, estimar duración con el WPM calibrado, no con el valor por defecto.
- Documentar en `config.yaml` el WPM efectivo medido junto a la voz y modelo usados.

**Warning signs:**
- Primer vídeo producido con duración real > 15% sobre el objetivo.
- ElevenLabs reporta `characters_used` mayor de lo esperado para el número de palabras.
- El QA de duración falla consistentemente en la misma dirección (siempre más largo, nunca más corto).

**Phase to address:**
Fase de director de timing y primer test de integración con ElevenLabs. La calibración debe hacerse antes de escribir el primer guion completo.

---

### Pitfall 5: Timestamps de ElevenLabs "congelados" (stagnation bug)

**What goes wrong:**
El endpoint `/v1/text-to-speech/{voice_id}/with-timestamps` devuelve timestamps en los que múltiples palabras consecutivas tienen el mismo `start` y `end` time, haciendo que la alineación sea inútil para sincronizar subtítulos con el audio.

**Why it happens:**
Bug documentado en el repositorio oficial de `elevenlabs-python` (issue #607). Ocurre especialmente con frases largas, ciertos patrones de puntuación y en el modelo `eleven_multilingual_v2`. No es determinista: la misma llamada puede producir timestamps correctos en un intento y congelados en otro.

**How to avoid:**
- **Validar los timestamps** devueltos antes de guardarlos: comprobar que la secuencia de `start` times es estrictamente creciente y que no hay grupos de más de 3 palabras con el mismo timestamp.
- Si la validación falla, reintentar la llamada (máximo 3 veces) antes de abortar.
- Partir los textos largos en frases (por `.`, `?`, `!`) y hacer llamadas independientes por frase, luego concatenar los timestamps aplicando el offset acumulado de duración.
- Tener `WhisperX` como fallback de alineación: si los timestamps de ElevenLabs no pasan validación tras reintentos, ejecutar alineación con WhisperX sobre el audio generado.

**Warning signs:**
- Múltiples palabras en el JSON de respuesta con `start == end` o con `start` idéntico al de la palabra anterior.
- Los subtítulos `.srt` generados muestran bloques de texto que permanecen en pantalla sin cambiar durante 2-5 segundos.

**Phase to address:**
Fase de síntesis de voz (ElevenLabs). Implementar la validación de timestamps antes de cualquier otro uso del JSON de respuesta.

---

### Pitfall 6: Crossfade audio/vídeo desincronizado en FFmpeg

**What goes wrong:**
Al usar `xfade` (vídeo) y `acrossfade` (audio) para las transiciones entre slides, el audio y el vídeo quedan desincronizados exactamente a partir de la primera transición. El vídeo avanza pero el audio va por detrás (o viceversa).

**Why it happens:**
`xfade` y `acrossfade` tienen comportamientos de duración distintos. Si se pasa el mismo valor de duración a ambos filtros, el resultado no es simétrico: `acrossfade` solapa exactamente D segundos de audio de ambos clips, pero `xfade` puede tratar la duración de forma diferente dependiendo de si los clips tienen el mismo framerate. En concreto, si se usa D=0.5 s para ambos, el audio puede necesitar D/2 para quedar alineado.

**How to avoid:**
- Probar el crossfade con un clip de test (dos slides de 3 s con audio diferente) y verificar la sincronía frame a frame antes de usarlo en producción.
- Documentar y fijar el par de valores `(xfade_duration, acrossfade_duration)` empíricamente verificados en el primer sprint de montaje.
- Si la sincronía es crítica, evitar crossfade de audio y hacer corte seco de audio mientras se mantiene crossfade visual suave — es más sencillo y predecible.
- Para crossfade activado, siempre medir la duración de los streams de audio y vídeo del resultado con `ffprobe` y comparar.

**Warning signs:**
- Streams de audio y vídeo con duración total diferente en `ffprobe` tras la concatenación.
- El audio de la última slide termina antes o después de que la imagen de la slide desaparezca.

**Phase to address:**
Fase de montaje FFmpeg. Dedicar un spike específico a validar el crossfade antes de integrar en el pipeline general.

---

### Pitfall 7: Normalización loudnorm en un solo pase — resultado no lineal

**What goes wrong:**
La normalización de loudness EBU R128 aplicada en un solo pase con `loudnorm` produce audio con ganancia que varía a lo largo del clip porque el filtro no ha visto el fichero completo al empezar. El resultado puede sonar con volumen inconstante slide a slide.

**Why it happens:**
`loudnorm` en modo single-pass usa AGC (control de ganancia automático) dinámico en tiempo real. No tiene acceso a los estadísticos del fichero completo (I, LRA, TP medidos) que se obtienen en el primer pase. Estos estadísticos son necesarios para una normalización lineal y uniforme.

**How to avoid:**
- Usar siempre **dos pases**: primer pase con `loudnorm=print_format=json` para extraer `input_i`, `input_lra`, `input_tp`; segundo pase con esos valores como parámetros `measured_I`, `measured_LRA`, `measured_tp`.
- Target de loudness: `-16 LUFS` (YouTube/streaming) o `-23 LUFS` (broadcast EBU R128). Para narración de presentaciones, `-16 LUFS` con `TP=-1.5` dB es el valor más seguro.
- Normalizar cada `slide_XX.mp3` individualmente antes del concat, no el audio del vídeo final, para evitar que un audio muy corto distorsione la medición global.
- Añadir `-ar 48000` al segundo pase para evitar que `loudnorm` resamplee a 192 kHz y devuelva audio a esa frecuencia.

**Warning signs:**
- El audio suena claramente más alto en unas slides que en otras.
- `ffprobe` reporta sample rate != 48000 Hz en el audio del vídeo final.
- El QA de loudness reporta diferencias > 3 LU entre slides.

**Phase to address:**
Fase de montaje FFmpeg / módulo de QA de audio.

---

### Pitfall 8: Quemado de subtítulos — deriva de framerate y paths

**What goes wrong:**
Los subtítulos quemados en el vídeo aparecen desplazados temporalmente (llegan antes o después de lo esperado) cuando el SRT fue generado asumiendo un framerate diferente al del vídeo de salida. Adicionalmente, FFmpeg falla silenciosamente al encontrar paths con caracteres especiales (dos puntos, espacios) en el filtro `subtitles=`.

**Why it happens:**
El filtro `subtitles=` de FFmpeg interpreta los timestamps del SRT en el timebase del vídeo. Si el vídeo está a 25 fps pero el SRT fue generado asumiendo 30 fps (o sin considerar el framerate), hay una desviación creciente. Además, FFmpeg interpreta los dos puntos `:` en rutas de Windows/Mac como separadores de parámetros de filtro, lo que corrompe silenciosamente el comando.

**How to avoid:**
- Generar el SRT usando timestamps en segundos decimales (no en frames) desde los timestamps de ElevenLabs/WhisperX — esto es independiente del framerate.
- Usar siempre rutas absolutas y escapar los dos puntos en paths al pasar al filtro: `subtitles='/path/to/file.srt':force_style='...'`.
- Fijar el framerate del vídeo de salida en `config.yaml` (por defecto 25 fps) y no variarlo — consistencia eliminará la mayoría de problemas de seeking.
- Para el GOP: usar `-g` igual a `fps * 2` (p.ej. `-g 50` para 25 fps) para seeking preciso sin archivo demasiado pesado.

**Warning signs:**
- Los subtítulos aparecen 1-2 palabras adelantados o retrasados respecto al audio.
- FFmpeg devuelve error de filtro al intentar quemar subtítulos sin mensaje claro de falla.

**Phase to address:**
Fase de montaje FFmpeg y generación de subtítulos SRT/VTT.

---

### Pitfall 9: Salida JSON de Claude no parseable — hallucinations de formato y truncado

**What goes wrong:**
Claude devuelve JSON que parece válido pero contiene: comillas sin escapar dentro de strings de texto del guion, texto en español con acentos que corrompen el JSON, o el JSON se trunca porque el guion generado supera el `max_tokens` configurado. El pipeline falla con `json.JSONDecodeError` en tiempo de ejecución.

**Why it happens:**
Aunque Anthropic ahora ofrece "Structured Outputs" (grammar-constrained generation), si se usa prompting manual con instrucción "devuelve JSON" sin el parámetro `betas=["output-128k-2025-02-19"]` y sin schema, Claude puede incluir texto de razonamiento antes del JSON, comentarios dentro del JSON, o truncar el objeto si llega al límite de tokens.

**How to avoid:**
- Usar la feature oficial de **Structured Outputs** de la API (disponible en Claude Sonnet 4.5+) con un JSON Schema Pydantic compilado — garantía matemática del formato, no solo prompting.
- Fijar `max_tokens` conservadoramente: para el guion completo de una presentación de 10 slides a 150 WPM x 120 s = ~300 palabras, el guion cabe en <2000 tokens de output. Dimensionar por presupuesto de palabras previo.
- Si se usa prompting manual (fallback): usar `response_format` con `type: "json_object"` y añadir en el system prompt la instrucción de responder únicamente con JSON sin texto adicional.
- Siempre validar el objeto parseado contra el schema Pydantic antes de usar los datos — captura hallucinations de contenido (campos faltantes, tipos incorrectos).
- En reintentos, loguear el mensaje de error de parseo + el texto crudo de respuesta para debugging.

**Warning signs:**
- `JSONDecodeError` en producción intermitente (no reproducible en dev).
- El JSON tiene el campo `</json>` o similar al final (Claude cerrando un bloque de código en vez de terminar el objeto).
- Los campos del storyboard tienen valores `null` donde se esperan strings.

**Phase to address:**
Fase de storyboard y guionista (primeras llamadas a Claude). Establecer el patrón de llamada + validación como base reutilizable para todas las llamadas LLM del pipeline.

---

### Pitfall 10: No-idempotencia del pipeline — trabajo duplicado y estado corrupto

**What goes wrong:**
Al re-ejecutar el pipeline tras un fallo a mitad, algunas etapas vuelven a ejecutarse desde cero (re-llamando a ElevenLabs, re-generando audio ya pagado) o, peor, etapas anteriores sobreescriben outputs que ya estaban correctos, corrompiendo el estado del `workdir`.

**Why it happens:**
Sin comprobación explícita de existencia del checkpoint antes de ejecutar la etapa, cada run del pipeline ejecuta todo de nuevo. Si una etapa falla a mitad (p.ej., FFmpeg termina después de 3 de 10 slides), el checkpoint de esa etapa puede quedar en estado parcial — existe el fichero pero está incompleto.

**How to avoid:**
- Cada etapa debe comprobar al inicio si su checkpoint de salida ya existe y está completo (validar estructura con Pydantic, no solo existencia del fichero).
- Implementar escritura atómica: escribir a un fichero temporal (`storyboard.json.tmp`) y renombrarlo a `storyboard.json` solo al completar la etapa íntegramente. Un fichero sin el sufijo `.tmp` es siempre un checkpoint válido.
- Las llamadas a APIs externas (ElevenLabs, Claude) deben ser la primera comprobación de idempotencia: si `audio/slide_03.mp3` existe y su tamaño > 0, no llamar a ElevenLabs para ese slide.
- Registrar en `state.json` el estado de cada etapa (`pending | running | done | failed`) con timestamp de última modificación para diagnóstico.
- Los tests de la etapa deben incluir un test de idempotencia: ejecutar la etapa dos veces seguidas y verificar que el resultado es idéntico y que las APIs no se llamaron la segunda vez.

**Warning signs:**
- El pipeline tarda el mismo tiempo la segunda ejecución que la primera, sin reutilizar nada.
- El coste de ElevenLabs aumenta linealmente con los reintentos.
- Aparecen ficheros `slide_03.mp3` y `slide_03_1.mp3` en el workdir.

**Phase to address:**
Fase de orquestador (implementar antes de cualquier llamada a API externa). Es la base sobre la que se construye todo el pipeline.

---

### Pitfall 11: WhisperX en Docker — imagen de 7-10 GB, CUDA no disponible, modelos no descargados

**What goes wrong:**
El Dockerfile que incluye WhisperX resulta en una imagen de 7-10 GB. En máquinas sin GPU NVIDIA (Mac con Apple Silicon, entornos CI normales), WhisperX falla con "Torch not compiled with CUDA enabled" o cae a CPU con velocidad x0.1. Los modelos de Whisper (large-v3: 3 GB) y wav2vec2 de alineación (300-500 MB) no están incluidos en la imagen y se descargan en el primer run, fallando si no hay acceso a internet en el entorno.

**Why it happens:**
WhisperX depende de `faster-whisper` (ctranslate2) y `torch`, que tienen dependencias CUDA pesadas. La instalación por defecto con `pip install whisperx` instala torch sin CUDA en muchos entornos. Los modelos se descargan de HuggingFace Hub en tiempo de ejecución, no en tiempo de build.

**How to avoid:**
- **Separar WhisperX en un servicio Docker independiente** del resto del pipeline. El contenedor principal (Playwright + FFmpeg) puede ser ligero (~2 GB). El contenedor de WhisperX solo se activa en modo `record`.
- En el Dockerfile de WhisperX, instalar torch con CUDA explícitamente: `pip install torch --index-url https://download.pytorch.org/whl/cu118`.
- Pre-descargar los modelos en tiempo de build con `RUN python -c "import whisperx; whisperx.load_model('large-v3', device='cpu')"` para que la imagen sea autosuficiente.
- Para Mac/CPU-only: usar el modelo `base` o `small` de Whisper (velocidad aceptable en CPU) y documentarlo en el README.
- Añadir en el `--dry-run` una comprobación de disponibilidad de CUDA y reportar el modo de ejecución esperado (GPU/CPU).

**Warning signs:**
- El build de Docker tarda más de 20 minutos en una máquina con buena conexión.
- El primer run en un entorno nuevo falla con `ConnectionError` al intentar descargar el modelo.
- WhisperX tarda > 5 minutos en transcribir 2 minutos de audio (indicador de que está en CPU sin optimización).

**Phase to address:**
Fase de empaquetado Docker (al final del roadmap, pero diseñar la separación de servicios desde el inicio para no tener que refactorizar el orquestador).

---

### Pitfall 12: Playwright en Docker — versión no alineada entre package y browsers instalados

**What goes wrong:**
La versión de Playwright en `pyproject.toml` no coincide con la versión usada durante `playwright install --with-deps` en el Dockerfile. Playwright devuelve error "could not find browser executable" porque los navegadores se instalaron para una versión diferente.

**Why it happens:**
`playwright install` instala los browsers para la versión de Playwright que está en el entorno en ese momento. Si el `pip install` posterior actualiza Playwright a una versión diferente, los browsers instalados quedan obsoletos. En Alpine Linux (musl libc) los browsers simplemente no funcionan porque los binarios de Chromium requieren glibc.

**How to avoid:**
- Usar la imagen oficial `mcr.microsoft.com/playwright/python:v1.XX.X-jammy` como base, donde la versión de la imagen coincide exactamente con la versión de Playwright instalada. Nunca usar Alpine.
- Pinear la versión de Playwright en `pyproject.toml` y en el FROM de la imagen a la misma versión: `playwright==1.49.0` y `FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy`.
- En desarrollo local, documentar que el desarrollador debe ejecutar `playwright install chromium` tras instalar las dependencias.
- Añadir un test de smoke en el pipeline de CI que renderice una slide HTML simple y compruebe que el PNG tiene dimensiones correctas.

**Warning signs:**
- Error "Executable doesn't exist at /root/.cache/ms-playwright/chromium-XXXX/chrome-linux/chrome" en el contenedor.
- Las imágenes PNG generadas en Docker son diferentes a las generadas en local Mac (fuentes del sistema distintas).
- El CI tarda 10+ minutos en la fase de build porque descarga browsers en cada run.

**Phase to address:**
Fase de empaquetado Docker. Definir el Dockerfile base en el primer sprint para que el entorno de desarrollo y el de producción sean idénticos desde el principio.

---

## Critical Pitfalls — v2.0.0 Studio Guiado Addendum

*Pitfalls específicos de envolver el pipeline existente en Streamlit, añadir OpenAI Audio TTS, mezcla de música de fondo con FFmpeg, y mejora automática de audio. Investigados: 2026-05-29.*

---

### Pitfall 13 (v2): Streamlit bloquea el hilo principal — FFmpeg/Playwright/TTS congelan la UI

**What goes wrong:**
Al llamar a las etapas del pipeline (render Playwright, síntesis TTS, montaje FFmpeg) directamente desde el hilo del script de Streamlit, la UI se congela completamente. No se puede actualizar ningún widget, barra de progreso, ni mostrar logs en tiempo real. El usuario ve una pantalla estática y no sabe si el proceso está corriendo o ha fallado. En algunos casos Streamlit interrumpe el proceso porque detecta inactividad.

**Why it happens:**
Streamlit ejecuta el script de Python en un único hilo síncrono. Cada widget interaction desencadena un full-script rerun desde la cima. Si una etapa del pipeline (p.ej. `ffmpeg` con 10 slides + audio) bloquea ese hilo durante 60-120 s, Streamlit no puede procesar ningún evento de UI durante ese tiempo — ni actualizaciones de progreso ni clics de botón.

**How to avoid:**
- Ejecutar las etapas del pipeline en un `ThreadPoolExecutor` con un único worker (el pipeline es secuencial, no necesita más). El hilo del script de Streamlit solo lanza la tarea y monitoriza el estado.
- Usar `add_script_run_ctx` de `streamlit.runtime.scriptrunner` en el thread para que los widgets creados desde el thread secundario tengan contexto de sesión válido.
- Usar `st.fragment` con `run_every=1` para un componente de progreso que se actualiza de forma autónoma leyendo el estado compartido en `st.session_state` sin ejecutar el script completo.
- Alternativamente, usar `subprocess.Popen` + `st.empty()` con bucle de polling en un fragment: leer `stdout`/`stderr` del proceso hijo y actualizar el placeholder cada segundo.
- Para el CLI headless existente: lanzar `avideo generate ...` como subproceso Popen con pipes y actualizar la UI con cada línea de salida Rich.

**Warning signs:**
- La UI se congela al pulsar "Ejecutar" y no responde hasta que el pipeline termina.
- `st.progress()` no avanza aunque el pipeline está corriendo.
- Streamlit muestra "Running..." en la pestaña del navegador durante minutos sin feedback.

**Phase to address:**
Fase UI Streamlit (fase base de v2.0.0). La arquitectura thread/fragment debe establecerse antes de conectar cualquier etapa del pipeline a la UI.

---

### Pitfall 14 (v2): `st.session_state` se pierde al recargar la página — wizard pierdo su posición

**What goes wrong:**
El usuario está en la Fase 3 del wizard (slides generadas, aprobadas, esperando ir a Fase 4), recarga el navegador accidentalmente o la pestaña se reconecta por inactividad. Todo `st.session_state` se destruye: el wizard vuelve a Fase 1, se pierde el `workdir` activo, y el usuario no tiene forma de retomar el proyecto.

**Why it happens:**
`st.session_state` está ligado al WebSocket entre el navegador y el servidor Streamlit. Un F5 o reconexión de pestaña crea una nueva sesión con estado vacío. No es persistencia — es memoria de proceso. En modo single-user local esto es especialmente doloroso porque no hay login que pueda recuperar la sesión.

**How to avoid:**
- Usar el filesystem como fuente de verdad del estado del wizard, no `st.session_state`. El `workdir` ya existe y tiene todos los checkpoints. Al iniciar la app, escanear los `workdir/` disponibles y ofrecer "Continuar proyecto" si hay un workdir con done-markers parciales.
- Guardar en `st.session_state` únicamente el ID del `workdir` activo (un string corto). Todo lo demás se reconstruye leyendo los checkpoints del disco.
- Al inicio del script, leer `workdir_id` desde un query param de URL (`st.query_params`) como mecanismo de recuperación: `?workdir=abc123` restaura el contexto sin fricción.
- No poner datos pesados (PNG, audio bytes, texto completo del guion) en `st.session_state`. Solo metadatos y el path del workdir.

**Warning signs:**
- El usuario reporta "se me fue al principio sin querer".
- `st.session_state` crece en memoria (señal de que se guardan datos pesados en lugar de referencias a disco).
- El wizard no ofrece opción de "retomar" al abrir la app con un workdir existente.

**Phase to address:**
Fase UI Streamlit — arquitectura de estado. Decidir el esquema de persistencia (workdir-first) antes de implementar el wizard.

---

### Pitfall 15 (v2): Full-script rerun ejecuta trabajo costoso de nuevo — Playwright/ElevenLabs re-invoqueados

**What goes wrong:**
Cada vez que el usuario hace clic en cualquier widget (un botón de "aprobar", un slider de ajuste), Streamlit re-ejecuta el script completo de arriba a abajo. Si el código que llama a `playwright.screenshot()` o `elevenlabs.synthesize()` está en el cuerpo principal del script sin guardia de checkpoint, esas llamadas se re-ejecutan en cada rerun, incurriendo en coste de API y latencia innecesarios.

**Why it happens:**
El modelo de ejecución de Streamlit es sin estado entre reruns por diseño. Cada rerun es un script ejecutado desde cero. Sin `@st.cache_data` o comprobación de checkpoint explícita, todas las llamadas costosas se ejecutan en cada interacción del usuario.

**How to avoid:**
- Nunca poner llamadas a etapas del pipeline directamente en el cuerpo del script. Siempre envolverlas en funciones decoradas con `@st.cache_data(show_spinner=False)` con los argumentos mínimos como cache key (p.ej. `workdir_id + stage_name`).
- Antes de lanzar una etapa, comprobar si el done-marker del workdir ya existe (`workdir.is_done(stage_name)`). Si existe, leer el checkpoint y mostrar el resultado sin re-ejecutar la etapa.
- La lógica de "¿debo ejecutar esta etapa?" debe estar completamente en el pipeline/orquestador, no en el código de la UI.
- Usar botones con `key` único por fase para que el clic de "Fase 2 → Aprobar" no triggere la lógica de "Fase 4 → Sintetizar voz".

**Warning signs:**
- El coste de ElevenLabs sube cada vez que el usuario interactúa con la UI después de sintetizar.
- Los logs muestran llamadas repetidas a la misma etapa sin que el done-marker haya desaparecido.
- La UI tarda varios segundos en responder a un simple clic de checkbox.

**Phase to address:**
Fase UI Streamlit — integración con checkpoints del pipeline. Establecer el patrón cache/checkpoint antes de conectar la primera etapa costosa.

---

### Pitfall 16 (v2): `st.file_uploader` pierde el archivo al siguiente rerun — música/audio de usuario desaparecen

**What goes wrong:**
El usuario sube un archivo de música de fondo (`background.mp3`) o una grabación propia. En el rerun siguiente (p.ej. al pulsar "Aplicar"), `st.file_uploader` devuelve `None` porque Streamlit no garantiza que el `UploadedFile` persista entre reruns si el widget no está presente en el script en ese punto. El archivo se pierde y el usuario tiene que subirlo de nuevo.

**Why it happens:**
`st.file_uploader` almacena el archivo como `BytesIO` en RAM de la sesión, no en disco. Si el widget desaparece del árbol de widgets durante un rerun (p.ej. porque la UI pasó a otra fase y el uploader ya no se renderiza), Streamlit lo elimina del estado. Además, archivos grandes (> 200 MB) pueden matar el proceso si se cargan en RAM directamente.

**How to avoid:**
- En cuanto el usuario sube un archivo, escribirlo inmediatamente a disco en el `workdir` del proyecto (`workdir/music/background.mp3`). No guardar `UploadedFile` en `st.session_state`.
- Limitar el tamaño de archivo aceptado con `st.file_uploader(... accept_multiple_files=False, type=["mp3","wav"], max_upload_size_mb=100)` (configurar `server.maxUploadSize` en `.streamlit/config.toml`).
- Para archivos de audio del usuario (grabaciones propias): guardar en `workdir/audio_user/slide_XX.wav` inmediatamente tras la subida.
- Una vez el archivo está en disco, mostrar un mensaje de confirmación con path relativo, y usar el path de disco en el resto del pipeline — nunca los bytes en memoria.

**Warning signs:**
- "El archivo de música desapareció" después de interaccionar con otro widget.
- `UploadedFile` es `None` en el segundo rerun aunque el usuario lo subió en el primero.
- El servidor de Streamlit se cae (OOM) al subir un MP3 de 300 MB.

**Phase to address:**
Fase UI — Fase 4 (Voz) y Fase 5 (Extras). Implementar el patrón "write-to-disk-on-upload" desde el primer uploader que se añada.

---

### Pitfall 17 (v2): OpenAI Audio TTS no devuelve timestamps — subtítulos requieren round-trip STT

**What goes wrong:**
Se usa OpenAI TTS (`tts-1` o `tts-1-hd`) para generar la narración. El audio se genera correctamente, pero la generación de subtítulos SRT/VTT falla porque la capa de subtítulos del pipeline espera timestamps a nivel de palabra (como los que provee ElevenLabs con `convert_with_timestamps()`). OpenAI TTS no devuelve ningún dato de timing — solo audio raw.

**Why it happens:**
La API de Text-to-Speech de OpenAI (`/v1/audio/speech`) devuelve exclusivamente el stream de audio (MP3/Opus/AAC/FLAC). No incluye `alignment` ni timestamps de ningún tipo. A diferencia de ElevenLabs, no existe un endpoint equivalente a `with-timestamps`. Esto es una limitación conocida y con feature request abierto en el foro de OpenAI desde 2023, sin resolución prevista.

**How to avoid:**
- Para OpenAI TTS, implementar un **paso de alineación forzada post-síntesis**: tras generar el audio, ejecutar WhisperX (o `openai.audio.transcriptions` con `response_format="verbose_json"` y `timestamp_granularities=["word"]`) sobre el audio generado para obtener timestamps a nivel de palabra.
- Usar `openai.audio.transcriptions.create(model="whisper-1", response_format="verbose_json", timestamp_granularities=["word"])` — el modelo `whisper-1` soporta word-level timestamps, aunque los nuevos modelos `gpt-4o-transcribe` NO los soportan.
- Documentar claramente en la UI que con OpenAI TTS los subtítulos requieren un paso adicional de transcripción (latencia +10-30 s por slide).
- Abstraer el proveedor de voz en una interfaz común `VoiceProvider` que devuelva siempre `SlideTimings` con `words` poblados, independientemente de si se usan ElevenLabs o OpenAI — la abstracción obliga a añadir el STT round-trip en el adaptador OpenAI.

**Warning signs:**
- `SlideTimings.words` es lista vacía para slides sintetizadas con OpenAI TTS.
- Los subtítulos SRT generados tienen un único bloque por slide (sin división en palabras).
- El pipeline falla con `IndexError` en la lógica de agrupación de subtítulos que asume words no vacíos.

**Phase to address:**
Fase v2.0.0 — Fase 4 (integración OpenAI Audio). Diseñar el adaptador con el round-trip STT desde el primer día, no como parche posterior.

---

### Pitfall 18 (v2): Límite de 4 096 caracteres por request de OpenAI TTS — guiones largos silenciosamente truncados

**What goes wrong:**
El guion de una slide supera 4 096 caracteres. La llamada a la API de OpenAI TTS trunca silenciosamente el texto (o devuelve error 400 dependiendo de la versión de SDK). El audio generado es más corto de lo esperado, el timing se desajusta, y el error no es evidente hasta que se revisa el vídeo final.

**Why it happens:**
`/v1/audio/speech` tiene un límite duro de 4 096 caracteres por request. Para una presentación de 10 min a 150 WPM, el guion completo tiene ~1 500 palabras (~9 000 caracteres). Si se pasa el guion completo en una sola llamada en lugar de dividirlo por slide, se supera el límite. Incluso por slide, una narración de 3 minutos en español puede acercarse a los 2 000-2 500 caracteres.

**How to avoid:**
- Añadir validación previa: si `len(text) > 4000`, partir en chunks respetando oraciones completas (split por `. `, `? `, `! `) y hacer una llamada por chunk, concatenando el audio resultante con FFmpeg (`concat` demuxer).
- Documentar en `config.yaml` el límite y añadir un warning en el `--dry-run` si algún slide excede el umbral.
- Preferir el reparto por slide (ya implementado) que mantiene el texto de cada narración bien por debajo del límite para duraciones típicas de slide (20-60 s → ~50-150 palabras → ~300-900 caracteres).

**Warning signs:**
- El audio de una slide termina abruptamente a mitad de frase.
- La duración medida por `ffprobe` es significativamente menor que la duración esperada por WPM.
- La API devuelve HTTP 400 con mensaje "text too long".

**Phase to address:**
Fase v2.0.0 — Fase 4 (integración OpenAI Audio). Añadir la validación en el adaptador OpenAI antes del primer test de integración.

---

### Pitfall 19 (v2): FFmpeg música de fondo — `amix` con `normalize=1` reduce el volumen de la narración 6 dB

**What goes wrong:**
Se mezcla la narración con la música de fondo usando `amix=inputs=2`. La narración suena 6 dB más baja de lo esperado, haciendo que la música compita con la voz aunque el nivel de música sea bajo. El problema persiste aunque se aplique loudnorm después.

**Why it happens:**
`amix` con el parámetro por defecto `normalize=1` aplica una ganancia de -6 dB a cada stream de entrada para evitar clipping al sumar dos señales — es un comportamiento por diseño del filtro para suma de potencias. Con `normalize=1`, ambas pistas (narración + música) se reducen 6 dB antes de mezclar, no solo la música. Esto destruye la narración que ya fue normalizada a -16 LUFS.

**How to avoid:**
- Usar siempre `amix=inputs=2:normalize=0` para desactivar la reducción automática de ganancia. Controlar los niveles manualmente con `volume=` en la cadena de filtros antes del `amix`.
- Patrón correcto: `[0:a]volume=1.0[narr];[1:a]volume=0.15[music];[narr][music]amix=inputs=2:normalize=0[out]` — la narración a nivel pleno, la música a ~15% (-16 dB).
- Aplicar loudnorm al track de música ANTES de mezclarlo para asegurar un nivel de partida consistente, no después de la mezcla.
- Para ducking dinámico, usar `sidechaincompress`: la narración es la señal sidechain que activa la compresión de la música cuando hay voz activa. Esto requiere un filtro más complejo pero produce resultados profesionales.

**Warning signs:**
- La narración suena más baja que la música aunque el volumen de música sea 0.1 en el filtro.
- El QA de loudness reporta -22 LUFS en el vídeo final cuando el objetivo es -16 LUFS.
- El audio suena "enterrado" en la música.

**Phase to address:**
Fase v2.0.0 — Fase 5 (música de fondo). Probar con un clip de test antes de integrar en el pipeline de montaje.

---

### Pitfall 20 (v2): FFmpeg loudnorm reaplica normalización sobre una mezcla ya normalizada — double-normalization artifacts

**What goes wrong:**
El pipeline ya aplica loudnorm en dos pases al final del montaje (Pitfall 7, mitigado en v1). Al añadir música de fondo, el desarrollador añade un paso de loudnorm sobre la mezcla narración+música. Si el pipeline ya tenía un paso de loudnorm al final, ahora hay dos normalizaciones en cadena: la primera sobre la narración sola, la segunda sobre la mezcla. El audio resultante suena con compresión excesiva y "bombeado" (pumping).

**Why it happens:**
Loudnorm en modo lineal (dos pases) es idempotente si se aplica una sola vez al audio final. Aplicarlo dos veces en cadena no produce el mismo resultado: la segunda pasada tiene estadísticos de entrada ya normalizados y puede introducir ganancia incorrecta, especialmente si LRA del primer pase difiere del objetivo del segundo. El resultado es un audio que sube y baja de volumen perceptiblemente.

**How to avoid:**
- Definir un único punto de normalización en el pipeline: el loudnorm final se aplica siempre sobre el archivo `output.mp4` completo (narración + música ya mezclados). No normalizar la narración sola antes de mezclar con música si se va a volver a normalizar después.
- Si se necesita controlar el nivel de la música antes de mezclar, usar `volume=` (ganancia lineal fija), no loudnorm — reservar loudnorm para el pase final único.
- Cuando el usuario activa música de fondo, el flag del pipeline debe saltarse el loudnorm de la narración individual y aplicarlo solo al final sobre la mezcla completa.
- Añadir un test que verifique que `qa_report.json` muestra exactamente dos pases de loudnorm (pass-1 + pass-2) y no más.

**Warning signs:**
- El audio suena con "pumping" o volumen inestable.
- Los logs muestran más de dos invocaciones de `loudnorm` en un mismo run.
- El QA de loudness pasa (LUFS dentro de rango) pero el audio subjetivamente suena mal.

**Phase to address:**
Fase v2.0.0 — Fase 5 (música de fondo). Revisar el grafo de procesamiento de audio completo antes de añadir el paso de música para identificar todos los puntos existentes de loudnorm.

---

### Pitfall 21 (v2): FFmpeg music fade — fade de entrada/salida desincronizado con el corte de narración

**What goes wrong:**
La música de fondo tiene un fade-in de 2 s al principio y un fade-out de 3 s al final. El fade-out empieza demasiado tarde (cuando la narración ya terminó) o demasiado pronto (corta la música mientras la última palabra del guion aún suena). El vídeo final tiene un silencio audible entre el final de la voz y el final de la música.

**Why it happens:**
El desarrollador calcula la duración del fade-out como `total_duration - fade_out_duration`, pero usa la duración objetivo en segundos (de `config.yaml`) en lugar de la duración real medida por `ffprobe` sobre el `output.mp4` ensamblado. Como el audio real tiene cross-fades y el QA puede ajustar la duración ligeramente, la posición del fade-out queda desfasada.

**How to avoid:**
- Calcular la posición del fade-out de música usando la duración real del vídeo final (`ffprobe output.mp4`), no la duración objetivo.
- Aplicar los fades de música como parte del último paso FFmpeg (el que mezcla narración + música), calculando `fade_out_start = actual_duration - fade_out_seconds` después de medir con `ffprobe`.
- Si loudnorm viene después de la mezcla, el fade debe aplicarse ANTES del loudnorm para que el silencio al final no distorsione la medición de loudness integrada.
- Para música en loop: usar `aloop` antes del fade para asegurar que la música dura al menos `actual_duration + fade_in + fade_out` segundos.

**Warning signs:**
- La música se corta bruscamente o se escucha un clic al final del vídeo.
- El fade-out empieza antes de que termine la última palabra de narración.
- La duración medida del vídeo final difiere en > 0.5 s de la duración objetivo.

**Phase to address:**
Fase v2.0.0 — Fase 5 (música de fondo). Incluir en el test de integración de música un assert sobre la duración del fade-out relativo a la duración real.

---

### Pitfall 22 (v2): Mejora de audio (denoise) antes de la alineación WhisperX — timestamps incorrectos

**What goes wrong:**
El usuario sube una grabación propia con ruido de fondo. La UI aplica `afftdn` o `arnndn` de FFmpeg para limpiar el audio. Después, se ejecuta WhisperX para alinear la narración. El proceso funciona, pero los timestamps de WhisperX para las palabras procesadas difieren hasta 200-400 ms de los del audio original sin procesar, causando subtítulos ligeramente desincronizados.

**Why it happens:**
Los denoisers de FFmpeg (especialmente `arnndn` con `mix` alto) introducen latencia de procesamiento y pueden alterar las características temporales del audio (ataques de consonantes, transiciones vocálicas). WhisperX usa modelos wav2vec2 de alineación forzada que son sensibles a estas características acústicas. Una reducción de ruido agresiva puede "suavizar" los ataques de consonantes que el alineador usa como anclas temporales, desplazando los timestamps resultantes.

**How to avoid:**
- Aplicar la mejora de audio (denoise + normalize) en un fichero de preview/escucha separado, pero ejecutar WhisperX sobre el audio **original sin procesar** para la alineación. Usar el audio mejorado solo para el vídeo final (sustituirlo después de obtener los timestamps).
- Si el ruido es tan severo que WhisperX falla en el audio original, aplicar un denoise suave (`arnndn mix=0.3`) en lugar de agresivo (`mix=1.0`) para preservar los ataques de las consonantes.
- Usar `afftdn` (FFT-based, más predecible) sobre `arnndn` (neural network, más agresivo) para audio de voz — los artefactos de `afftdn` son más controlables.
- Para normalización de volumen previa a WhisperX: preferir `loudnorm` lineal (dos pases) sobre compresión dinámica — la compresión modifica la dinámica temporal de forma que confunde al alineador.

**Warning signs:**
- Los timestamps de WhisperX difieren > 200 ms entre el audio original y el audio procesado.
- Las consonantes de inicio de palabra (p, t, k) aparecen con timestamps retrasados respecto a la escucha.
- El audio procesado suena "robótico" o con artefactos metálicos — señal de que el denoise fue demasiado agresivo.

**Phase to address:**
Fase v2.0.0 — Fase 4 (mejora de audio para grabaciones subidas). Definir el orden correcto en el diseño técnico: align-from-original, apply-enhancement-for-output.

---

### Pitfall 23 (v2): Mejora de audio sobre-procesada — artefactos en audio de narración limpia

**What goes wrong:**
El botón de "Mejora automática" aplica `afftdn` o `arnndn` con parámetros por defecto (agresivos) sobre una grabación que ya tiene buena calidad. El resultado suena robótico, con consonantes sibilantes distorsionadas (efecto "metallic speech") y con ringing en las transiciones entre voz y silencio. El usuario prefería el audio original.

**Why it happens:**
Los filtros de reducción de ruido de FFmpeg están diseñados para eliminar ruido estacionario (ventilador, AC) pero son agresivos por defecto. `afftdn` con `nr=12dB` (valor por defecto) aplica una reducción que en audio ya limpio elimina también las frecuencias más bajas de las fricativas y sibilantes (s, f, sh), produciendo los artefactos metálicos. `arnndn` con `mix=1.0` aplica el modelo RNN al 100%, que en audio sin ruido real sobreestima el "ruido" y degrada la claridad.

**How to avoid:**
- Hacer el paso de mejora **opcional y no destructivo**: el botón de "Mejora" en la UI debe mostrar un preview con el audio mejorado antes de aplicarlo, sin sobreescribir el original.
- Usar parámetros conservadores por defecto: `afftdn=nr=6:nf=-25` (reducción moderada) en lugar de los agresivos por defecto; `arnndn=mix=0.4` en lugar de `mix=1.0`.
- Añadir un selector de "intensidad" (suave/media/fuerte) que cambie los parámetros, con "suave" como default.
- Guardar el audio original en `workdir/audio_user/slide_XX_original.wav` antes de cualquier procesamiento, para permitir revertir.
- Informar al usuario en la UI si el audio ya mide dentro de un rango de LUFS razonable (-16 a -20 LUFS) y tiene SNR estimado > 20 dB, en cuyo caso la mejora probablemente no sea necesaria.

**Warning signs:**
- El usuario reporta que el audio suena "robótico" o "metálico" después de mejorar.
- Las sibilantes (s, z) suenan distorsionadas o ausentes.
- El nivel de LUFS del audio mejorado es diferente al del original (señal de que la normalización del denoise no es neutra).

**Phase to address:**
Fase v2.0.0 — Fase 4 (mejora de audio). Definir la UI de preview+parámetros antes de implementar el procesamiento.

---

### Pitfall 24 (v2): Edición interactiva del guion en la UI invalida checkpoints downstream sin borrar done-markers

**What goes wrong:**
El usuario edita el guion en la Fase 2 del wizard (un `st.text_area` por slide) y pulsa "Confirmar cambios". La UI guarda el guion editado en `workdir/script.json`. Pero los done-markers de fases posteriores (voice, assemble) siguen presentes en el workdir. El pipeline, al detectar esos done-markers, omite la re-síntesis de voz y el re-montaje, sirviendo el vídeo viejo generado con el guion anterior.

**Why it happens:**
El orquestador actual del pipeline respeta los done-markers de forma estricta (idempotencia es una feature, no un bug). No hay ningún mecanismo de "invalida los checkpoints downstream cuando X cambia". Al editar el guion desde la UI, los datos cambian pero el sistema de done-markers no sabe que los datos han cambiado — solo sabe si una etapa se ejecutó.

**How to avoid:**
- Al guardar cualquier cambio en la UI que modifique un checkpoint upstream, borrar explícitamente los done-markers de todas las etapas downstream antes de guardar el nuevo checkpoint. Por ejemplo, editar el guion debe borrar `.voice.done`, `.assemble.done`, etc.
- Implementar una función `invalidate_downstream(workdir, from_stage)` en el `WorkdirManager` que elimine todos los done-markers de las etapas posteriores a `from_stage`.
- En la UI, mostrar un warning visible: "Has editado el guion. Las etapas de Voz y Montaje se re-ejecutarán. Coste estimado adicional: X créditos ElevenLabs."
- Antes de guardar una edición, comparar el contenido nuevo con el checkpoint existente usando hash. Si son idénticos (el usuario no cambió nada realmente), no invalidar downstream.

**Warning signs:**
- El vídeo exportado tiene la narración antigua aunque el guion muestra el texto nuevo.
- `workdir/audio/slide_01.mp3` tiene una fecha de creación anterior a la última edición del guion.
- El QA de duración pasa pero el contenido de vídeo no coincide con el guion actual.

**Phase to address:**
Fase v2.0.0 — UI wizard (fases 2-3, donde el usuario puede editar). Implementar `invalidate_downstream` en `WorkdirManager` antes de construir cualquier widget de edición.

---

### Pitfall 25 (v2): Preview de vídeo en Streamlit carga el MP4 completo en RAM del proceso Python

**What goes wrong:**
La Fase 6 del wizard muestra un preview del vídeo final con `st.video()`. El vídeo es un MP4 de 200-500 MB. Al cargarlo con `st.video(open("output.mp4", "rb").read())`, Streamlit copia todos los bytes en RAM del proceso Python para servirlo al navegador. Con varios runs en la misma sesión, la RAM del servidor se agota y Streamlit se mata con OOM.

**Why it happens:**
`st.video()` acepta bytes o un path. Si se pasan bytes (la forma más obvia), Streamlit los guarda en memoria para servirlos vía HTTP. Si el vídeo es grande y hay múltiples reruns o el usuario ha generado varios vídeos en la sesión, la memoria se acumula. En Streamlit, los objetos de media no se liberan hasta que el garbage collector Python los recoge, lo que puede tardar mucho.

**How to avoid:**
- Pasar siempre un **path de string** a `st.video()` en lugar de bytes: `st.video(str(workdir.root / "output.mp4"))`. Streamlit sirve el fichero directamente desde disco sin copiarlo a RAM cuando se le da un path.
- Asegurarse de que `+faststart` está activo en el MP4 (ya lo está en el pipeline v1) para que el navegador pueda hacer streaming progresivo sin necesitar el fichero completo.
- Para el thumbnail de preview, usar el primer frame PNG de la primera slide (ya disponible en `workdir/slides/`) en lugar de generar un frame del vídeo.
- Añadir un límite de `maxUploadSize` y documentar que el preview de Streamlit no soporta vídeos > 500 MB bien.

**Warning signs:**
- El proceso de Python crece en RAM con cada preview del vídeo.
- `st.video()` tarda > 10 s en mostrar el player (señal de que está cargando los bytes completos antes de mostrarlo).
- El servidor de Streamlit se mata con OOM al cargar el segundo vídeo de la sesión.

**Phase to address:**
Fase v2.0.0 — Fase 6 (preview y descarga). Decidir el patrón de preview antes de implementar el widget de vídeo.

---

### Pitfall 26 (v2): Runs concurrentes desde el mismo browser o dos pestañas — workdir compartido corrompe el estado

**What goes wrong:**
El usuario (o un script de test) abre dos pestañas del wizard en el mismo `localhost`. Ambas sesiones Streamlit apuntan al mismo `workdir/` porque el ID de proyecto es el mismo. Una sesión está en Fase 3 renderizando slides mientras la otra retrocede a Fase 2 y modifica `script.json`. Los done-markers se corrompen y el pipeline produce un vídeo con slides de una sesión y audio de la otra.

**Why it happens:**
Streamlit crea una sesión WebSocket independiente por pestaña, pero ambas sesiones leen/escriben en el mismo directorio del filesystem. No hay locking de ficheros. El WorkdirManager actual no tiene mecanismo de lock. En la práctica, esto solo ocurre cuando el usuario abre dos pestañas del mismo proyecto — pero es suficientemente probable para causar corrupción de estado.

**How to avoid:**
- Usar un `workdir` por sesión Streamlit: incluir un `session_id` (UUID generado al iniciar la sesión) en el nombre del `workdir` si es un proyecto nuevo. Proyectos existentes se retoman con su workdir original pero solo desde una sesión a la vez.
- Implementar un **lockfile** (`workdir/.lock`) con `fcntl.flock` (Unix) o `msvcrt.locking` (Windows) al inicio de cualquier etapa del pipeline. Si el lock no se puede adquirir, mostrar en la UI: "Este proyecto está siendo ejecutado en otra sesión."
- Para la UI de single-user local, documentar claramente que solo se puede tener una sesión activa por proyecto.

**Warning signs:**
- Done-markers de etapas posteriores aparecen mientras una etapa anterior está aún ejecutándose.
- El vídeo final mezcla narración de un guion con slides de otro guion.
- `workdir/script.json` tiene un timestamp de modificación posterior a `workdir/.voice.done`.

**Phase to address:**
Fase v2.0.0 — UI base. Implementar el lockfile junto con el WorkdirManager antes de exponer la UI al usuario.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Usar duración WPM estimada en el montaje (sin medir con ffprobe) | Evitar llamada a ffprobe por slide | Deriva de timing acumulada, vídeo desincronizado | Nunca — ffprobe es trivial |
| Un solo pase de loudnorm | Evitar segundo pase FFmpeg | Audio con volumen inconsistente slide a slide | Nunca en producción |
| No validar timestamps de ElevenLabs antes de generar SRT | Código más simple | Subtítulos congelados sin error visible | Solo en prototipo local, nunca en pipeline automatizado |
| JSON prompting sin Structured Outputs | Menos setup inicial | JSONDecodeError intermitente en producción | Solo en prototipo; migrar antes de producción |
| Checkpoints basados en existencia del fichero (sin validar contenido) | Implementación más rápida | Estado corrupto tras fallo parcial | Solo en etapas sin llamadas a APIs externas |
| Todo en un solo Dockerfile | Despliegue más simple | Imagen de 10+ GB; WhisperX mezcla con Playwright | Aceptable en prototipo; separar antes de distribuir |
| Guardar estado del wizard solo en `st.session_state` (sin respaldo en disco) | Código más simple | Estado perdido al recargar la página | Nunca para proyectos de > 2 min de pipeline |
| Pasar bytes de vídeo a `st.video()` en lugar de path | Una línea de código | OOM en sesiones largas con vídeos > 200 MB | Nunca para vídeos > 50 MB |
| Omitir `invalidate_downstream` al editar un checkpoint | Implementación más rápida | Vídeo final out-of-sync con el guion editado | Nunca si la UI permite edición |
| Usar `amix` con `normalize=1` (default) para mezcla narración+música | Comportamiento por defecto | -6 dB en narración, mezcla desequilibrada | Nunca — usar `normalize=0` siempre |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ElevenLabs API | Asumir que todos los timestamps son válidos directamente | Validar que la secuencia de `start` times es estrictamente creciente antes de usar |
| ElevenLabs API | Pasar el guion completo de todas las slides en una sola llamada | Llamar por slide o por frase; controlar el offset acumulado de timestamps |
| Playwright | Llamar a `screenshot()` sin esperar `document.fonts.ready` | `await page.wait_for_function("document.fonts.ready")` + `animations='disabled'` |
| FFmpeg | Pasar el mismo valor a `xfade` y `acrossfade` asumiendo que son equivalentes | Verificar empíricamente con un clip de test que audio y vídeo quedan sincronizados |
| FFmpeg | Usar rutas con espacios o dos puntos en el filtro `subtitles=` | Usar rutas absolutas escapando `:` como `\:` en el string del filtro |
| Anthropic API | No configurar `max_tokens` y recibir respuestas truncadas | Estimar el máximo de tokens de output por presupuesto de palabras y fijar `max_tokens` con margen |
| WhisperX | Instalar sin especificar CUDA y obtener torch CPU | Instalar torch con `--index-url https://download.pytorch.org/whl/cu118` y verificar `torch.cuda.is_available()` |
| OpenAI TTS | Asumir que devuelve timestamps como ElevenLabs | No hay timestamps en OpenAI TTS — añadir paso STT round-trip con `whisper-1` para obtenerlos |
| OpenAI TTS | Pasar el guion completo de una presentación en una sola llamada | Límite de 4 096 chars/request — dividir por slide (ya < 900 chars en la mayoría de casos) |
| Streamlit + pipeline | Llamar a etapas costosas directamente en el cuerpo del script | Envolver en `@st.cache_data` + comprobación de done-marker antes de cada etapa |
| Streamlit `st.file_uploader` | Guardar `UploadedFile` en `st.session_state` | Escribir a disco inmediatamente en `workdir/` y guardar solo el path |
| FFmpeg `amix` | Usar `normalize=1` (default) al mezclar narración + música | Siempre `normalize=0`; controlar niveles con `volume=` antes del `amix` |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Playwright instancia de navegador por slide | Pipeline tarda 5-10 min solo en screenshots | Reutilizar una sola instancia de Browser/Context para todas las slides del mismo run | A partir de 5 slides, el overhead de lanzar Chromium cada vez es > 30 s |
| WhisperX en CPU sin optimización | Transcribir 2 min de audio tarda 10+ min | Usar `compute_type="int8"` en CPU; GPU para producción | En CPU sin int8, escala O(n) con la duración del audio |
| Llamadas Claude en serie para todas las slides del guion | El guion de 10 slides tarda 3-5 min (latencia de red acumulada) | Generar el guion de todas las slides en una sola llamada; solo paralelizar si el guion es > 4000 tokens | A partir de 15+ slides si se generan en serie |
| FFmpeg concatenando imágenes individuales sin GOP adecuado | El seeking en el vídeo final es impreciso y lento | Fijar `-g fps*2` (p.ej. `-g 50` para 25 fps) para keyframes cada 2 s | No rompe, pero seeking impreciso afecta a reproductores web |
| Streamlit full-script rerun en cada widget interaction | Lag de 2-5 s en cada clic durante una sesión con workdir cargado | `@st.cache_data` para lecturas de checkpoint; `st.fragment` para actualizaciones parciales | A partir del primer widget que triggera lectura de disco o llamada a API |
| Preview de PNG de slides cargando todos los frames en RAM | Uso de RAM sube a 500 MB+ en sesiones con muchas slides | Cargar solo el thumbnail de la slide activa; usar `st.image` con path, no bytes | A partir de 15+ slides de 1920x1080 PNG (~3-5 MB cada una) |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Loguear el contenido del guion (narración) en logs de debug | Filtración de contenido propietario si los logs son accesibles | Loguear solo metadatos (longitud del guion, número de palabras), nunca el texto completo |
| Guardar `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY` y `OPENAI_API_KEY` en el código o en `config.yaml` commiteado | Compromiso de las API keys y cargos no autorizados | Leer exclusivamente de variables de entorno en runtime; añadir `config.yaml` y `.env` al `.gitignore` |
| Incluir el contexto de entrada (`.pptx`, `.pdf`) en el workdir sin restricción de acceso | El workdir puede contener documentos confidenciales | Documentar que el workdir debe estar fuera del repositorio; añadir `workdir/` al `.gitignore` |
| Streamlit expuesto en `0.0.0.0` por defecto | La UI local es accesible desde la red local; en entornos compartidos puede exponer datos y API keys | Forzar `server.address = "127.0.0.1"` en `.streamlit/config.toml`; nunca exponer en producción sin autenticación |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Pipeline sin progreso visible (silencio total durante síntesis de voz) | El usuario no sabe si el proceso está corriendo o se ha colgado | Usar `rich.Progress` con barra de progreso por etapa y logging de eventos clave |
| Abortar el pipeline sin guardar el checkpoint de la etapa en curso | El usuario pierde el trabajo de la etapa parcialmente completada y paga la API de nuevo | Capturar `KeyboardInterrupt` y `SIGTERM`, guardar el estado parcial antes de salir |
| Error de API (ElevenLabs 429) sin mensaje claro + sugerencia de acción | El usuario recibe un stack trace y no sabe qué hacer | Interceptar errores de API conocidos y devolver mensajes de error accionables: "Límite de crédito ElevenLabs alcanzado. Verifica tu saldo en elevenlabs.io" |
| El `--dry-run` no estima el coste con detalle por etapa | El usuario no puede presupuestar el coste antes de ejecutar | El dry-run debe desglosar: tokens Anthropic (storyboard + guion + verificador), caracteres ElevenLabs u OpenAI TTS, y tiempo estimado de WhisperX |
| Wizard que avanza sin confirmar que el usuario ha revisado el contenido | El usuario se da cuenta de un error solo en el vídeo final | Mostrar un checkbox explícito de "He revisado este contenido" antes de cada transición de fase |
| Edición del guion que no muestra el coste de re-síntesis | El usuario edita una palabra y no sabe que esto re-genera todos los audios | Mostrar estimación de créditos adicionales al guardar cualquier edición del guion |
| Botón de "Mejora de audio" sin preview | El usuario aplica el denoise y el resultado suena peor | Reproducir el audio mejorado en un `st.audio` antes de confirmar; guardar el original para revertir |

---

## "Looks Done But Isn't" Checklist

- [ ] **Generación de slides:** El PNG tiene el tamaño correcto (1920x1080) y el texto usa la fuente del tema, no la fuente de fallback del sistema — verificar con `identify slide_01.png` (ImageMagick) o inspeccionando el PNG con PIL.
- [ ] **Timestamps ElevenLabs:** La secuencia de timestamps es estrictamente creciente y no hay grupos de palabras con el mismo timestamp — verificar con la función de validación antes de generar el SRT.
- [ ] **Montaje FFmpeg:** Los streams de audio y vídeo del fichero final tienen la misma duración total — verificar con `ffprobe -v error -show_entries stream=codec_type,duration`.
- [ ] **Idempotencia:** Ejecutar el pipeline dos veces sobre el mismo workdir produce el mismo vídeo sin llamar a APIs externas en la segunda ejecución — verificar con mocks de requests en los tests.
- [ ] **Docker + Playwright:** El PNG generado dentro del contenedor tiene el mismo aspecto que el generado en local — comparar visualmente o con hash MD5 de píxeles con la misma imagen de Docker.
- [ ] **Subtítulos SRT:** El primer y último subtítulo coinciden con el inicio y fin del audio — reproducir el vídeo con subtítulos y verificar el primer y último bloque.
- [ ] **Loudness:** El audio del vídeo final mide entre -18 y -14 LUFS integrado — verificar con `ffmpeg -i output.mp4 -filter:a loudnorm=print_format=json -f null -`.
- [ ] **OpenAI TTS + subtítulos:** Los subtítulos de slides sintetizadas con OpenAI TTS tienen `words` no vacíos — verificar en `timings.json` que todos los slides tienen al menos 1 word timing.
- [ ] **Streamlit + checkpoint:** Editar el guion y recargar la UI muestra el guion editado, no el original, Y los done-markers de fases posteriores han sido eliminados — verificar `ls workdir/.*.done` después de guardar una edición.
- [ ] **Música de fondo:** El vídeo final con música tiene la narración claramente inteligible y la música no domina — verificar con auriculares a volumen normal.
- [ ] **Streamlit session persistence:** Recargar la página en Fase 3 ofrece opción de "Continuar proyecto" y no vuelve a Fase 1 — verificar con F5 en el navegador.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fuentes no cargadas en screenshots existentes | MEDIUM | Re-ejecutar solo la etapa de slides (checkpoint reanudable), tras corregir la espera de fuentes |
| Timestamps ElevenLabs congelados (audio ya generado) | LOW | El audio es correcto; solo se regeneran los timestamps usando WhisperX como fallback de alineación |
| Deriva de timing en vídeo ya montado | LOW | Re-ejecutar solo la etapa de montaje con `timings.json` corregido (usando ffprobe); no requiere re-generar audio |
| JSON Claude no parseable (etapa de storyboard o guion) | LOW | Reintentar la llamada (máximo 3 veces con backoff); si falla, escribir el JSON manualmente en el workdir y continuar |
| Imagen Docker con versión de Playwright incorrecta | HIGH | Reconstruir imagen con versión pineada correcta; no hay recovery en runtime |
| Audio de WhisperX transcrito con timestamps incorrectos | MEDIUM | Re-ejecutar WhisperX con modelo mayor (medium/large) o segmentar el audio antes de alinear |
| Checkpoints downstream no invalidados tras edición en UI | MEDIUM | Ejecutar `invalidate_downstream` manualmente borrando los done-markers posteriores; re-ejecutar pipeline desde la etapa afectada |
| Audio de música sobre-procesado (denoise agresivo) | LOW | El audio original está en `slide_XX_original.wav`; restaurar y re-procesar con parámetros más suaves |
| OpenAI TTS audio sin timestamps (subtítulos vacíos) | LOW | Ejecutar el paso STT round-trip con `whisper-1` sobre el audio generado; actualizar `timings.json` |
| double-normalization artifacts (pumping) | MEDIUM | Identificar el punto duplicado de loudnorm en el grafo de procesamiento; desactivar uno; re-montar |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fuentes no cargadas en Playwright | Fase: Generación de slides `auto` | Test de render con fuente del tema; comparar PNG con referencia |
| Gráficos JS no renderizados | Fase: Generación de slides `auto` | Test de render con slide que incluye gráfico; no debe haber canvas en blanco |
| Deriva de timing audio/slide | Fase: Montaje FFmpeg | QA de duración: comparar duración real vs objetivo; assert diferencia < 5% |
| Calibración WPM inexacta | Fase: Director de timing + primer test ElevenLabs | Script de calibración; documentar WPM efectivo en config |
| Timestamps ElevenLabs congelados | Fase: Síntesis de voz (ElevenLabs) | Validación automática de timestamps antes de guardar checkpoint |
| Crossfade desincronizado FFmpeg | Fase: Montaje FFmpeg | Spike de crossfade con clip de test; verificar streams con ffprobe |
| Loudnorm single-pass inconsistente | Fase: Montaje FFmpeg / QA de audio | Verificar LUFS del audio final con ffmpeg loudnorm en modo medición |
| Quemado de subtítulos desfasado | Fase: Montaje FFmpeg + generación SRT | Reproducción manual del primer y último subtítulo del vídeo de salida |
| JSON Claude no parseable | Fase: Storyboard (primeras llamadas LLM) | Tests con Pydantic schema validation + test de idempotencia con mock de API |
| No-idempotencia del pipeline | Fase: Orquestador (fase base del roadmap) | Test de doble ejecución sobre workdir existente; assert que APIs no se llaman en el segundo run |
| WhisperX Docker pesado / CUDA | Fase: Empaquetado Docker | Verificar tamaño de imagen; smoke test de transcripción en CI |
| Playwright versión no alineada en Docker | Fase: Empaquetado Docker | Test de smoke de screenshot en el contenedor; verificar que la imagen usa la misma versión pineada |
| Streamlit bloqueo hilo principal (v2) | v2 — Fase UI base | Test manual: interactuar con un widget durante un run de pipeline; la UI debe responder |
| session_state perdido al recargar (v2) | v2 — Fase UI base (arquitectura de estado) | Test: F5 en Fase 3; verificar que la app ofrece "Continuar proyecto" |
| Full-script rerun re-ejecuta etapas (v2) | v2 — Fase UI + integración checkpoints | Test: interactuar con un widget después de fase de voz; verificar que ElevenLabs no se vuelve a llamar |
| file_uploader pierde archivo al rerun (v2) | v2 — Fase 4 (Voz) y Fase 5 (Extras) | Test: subir audio, interactuar con otro widget, verificar que el archivo sigue disponible |
| OpenAI TTS sin timestamps (v2) | v2 — Fase 4 (OpenAI Audio adapter) | Test de integración: sintetizar un slide con OpenAI TTS, verificar que `timings.words` no está vacío |
| OpenAI TTS límite 4096 chars (v2) | v2 — Fase 4 (OpenAI Audio adapter) | Test unitario: verificar que textos > 4000 chars se parten antes de la llamada API |
| amix normalize=1 reduce narración -6dB (v2) | v2 — Fase 5 (música de fondo) | Test de mezcla: medir LUFS de narración antes y después de `amix`; deben ser iguales |
| double-normalization pumping (v2) | v2 — Fase 5 (música de fondo) | Revisar grafo de procesamiento; assert que loudnorm se invoca exactamente dos veces en cualquier run |
| Music fade mal calculado sobre duración objetivo (v2) | v2 — Fase 5 (música de fondo) | Test: medir duración real del vídeo con música; verificar que el fade-out empieza en `real_duration - fade_out_s` |
| Denoise antes de WhisperX — timestamps incorrectos (v2) | v2 — Fase 4 (mejora audio grabaciones) | Test: comparar timestamps de WhisperX sobre audio original vs procesado; diferencia < 100 ms |
| Denoise sobre-agresivo — artefactos (v2) | v2 — Fase 4 (mejora audio grabaciones) | Escucha manual del preview antes de confirmar; parámetros conservadores por defecto |
| Edición guion invalida downstream sin borrar done-markers (v2) | v2 — Fase 2 (wizard guion editable) | Test: editar una palabra, verificar que `.voice.done` y `.assemble.done` fueron eliminados |
| Preview vídeo carga MP4 completo en RAM (v2) | v2 — Fase 6 (preview y descarga) | Test de memoria: medir RAM de proceso Streamlit antes y después de preview; no debe crecer > 50 MB |
| Runs concurrentes corrompen workdir (v2) | v2 — Fase UI base (lockfile) | Test: abrir dos pestañas del mismo proyecto; la segunda debe mostrar "proyecto en uso" |

---

## Sources

- [ElevenLabs: Speech Timestamp Stagnation Bug (issue #607)](https://github.com/elevenlabs/elevenlabs-python/issues/607)
- [ElevenLabs: API Reference - Text-to-Speech with Timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)
- [WhisperX: Word-level timestamp inaccuracy vs MFA (issue #1247)](https://github.com/m-bain/whisperX/issues/1247)
- [WhisperX: Digits/symbols get no word-level timestamps (issue #1372)](https://github.com/m-bain/whisperX/issues/1372)
- [Playwright: Screenshot fails if fonts cannot be loaded (issue #35972)](https://github.com/microsoft/playwright/issues/35972)
- [Playwright: How to wait for font loading in tests](https://testautomationmastery.com/how-to-wait-for-font-loading-to-ensure-complete-page-render-in-playwright-tests/)
- [Playwright Docker: Missing browser libraries and font issues](https://getautonoma.com/blog/playwright-docker-guide)
- [Playwright Official Docker docs](https://playwright.dev/docs/docker)
- [FFmpeg Audio Normalization: loudnorm two-pass guide](https://32blog.com/en/ffmpeg/ffmpeg-audio-normalization-loudnorm)
- [ffmpeg-normalize library (slhck)](https://github.com/slhck/ffmpeg-normalize)
- [Anthropic: Structured Outputs documentation](https://docs.claude.com/en/docs/build-with-claude/structured-outputs)
- [Streamlit: Threading in Streamlit — official docs](https://docs.streamlit.io/develop/concepts/design/multithreading)
- [Streamlit: st.fragment — official docs](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
- [Streamlit: session_state reset on page reload (issue #5529)](https://github.com/streamlit/streamlit/issues/5529)
- [Streamlit: file_uploader large file kills server (issue #9218)](https://github.com/streamlit/streamlit/issues/9218)
- [Streamlit: ThreadPoolExecutor missing ScriptRunContext](https://discuss.streamlit.io/t/thread-threadpoolexecutor-8-0-missing-scriptruncontext/39044)
- [Streamlit: Non-blocking async progress bar (issue #9310)](https://github.com/streamlit/streamlit/issues/9310)
- [OpenAI: Text-to-Speech API docs — no timestamps](https://platform.openai.com/docs/guides/text-to-speech)
- [OpenAI community: Timestamped Captions for TTS API (feature request)](https://community.openai.com/t/timestamped-captions-for-tts-api-feature-request/538339)
- [OpenAI: Speech-to-text with word-level timestamps (whisper-1)](https://platform.openai.com/docs/guides/speech-to-text/timestamps)
- [OpenAI TTS pricing — tts-1 vs tts-1-hd](https://developers.openai.com/api/docs/pricing)
- [FFmpeg: amix normalize parameter — official filter docs](https://ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg: sidechaincompress for ducking (mailing list discussion, Nov 2024)](https://ffmpeg.org/pipermail/ffmpeg-user/2024-November/058872.html)
- [FFmpeg: afftdn denoise filter docs](https://ayosec.github.io/ffmpeg-filters-docs/8.0/Filters/Audio/afftdn.html)
- [FFmpeg: arnndn noise reduction by example](https://ffmpegbyexample.com/examples/97155ill/audio_noise_reduction_using_arnndn/)
- [WhisperX forced alignment system — DeepWiki](https://deepwiki.com/m-bain/whisperX/3.3-forced-alignment-system)

---
*Pitfalls research for: pipeline Python vídeo narrado (Playwright + ElevenLabs + WhisperX + FFmpeg + Anthropic) + v2.0.0 Studio Guiado (Streamlit UI + OpenAI Audio TTS + FFmpeg music ducking + audio enhancement)*
*Researched: 2026-05-25 (v1) / 2026-05-29 (v2.0.0 addendum)*
