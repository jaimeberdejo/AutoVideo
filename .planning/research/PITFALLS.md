# Pitfalls Research

**Domain:** Pipeline Python para vídeo narrado — slides HTML→PNG (Playwright), voz ElevenLabs/WhisperX, montaje FFmpeg, storyboard/guion con API Anthropic
**Researched:** 2026-05-25
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

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Usar duración WPM estimada en el montaje (sin medir con ffprobe) | Evitar llamada a ffprobe por slide | Deriva de timing acumulada, vídeo desincronizado | Nunca — ffprobe es trivial |
| Un solo pase de loudnorm | Evitar segundo pase FFmpeg | Audio con volumen inconsistente slide a slide | Nunca en producción |
| No validar timestamps de ElevenLabs antes de generar SRT | Código más simple | Subtítulos congelados sin error visible | Solo en prototipo local, nunca en pipeline automatizado |
| JSON prompting sin Structured Outputs | Menos setup inicial | JSONDecodeError intermitente en producción | Solo en prototipo; migrar antes de producción |
| Checkpoints basados en existencia del fichero (sin validar contenido) | Implementación más rápida | Estado corrupto tras fallo parcial | Solo en etapas sin llamadas a APIs externas |
| Todo en un solo Dockerfile | Despliegue más simple | Imagen de 10+ GB; WhisperX mezcla con Playwright | Aceptable en prototipo; separar antes de distribuir |

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

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Playwright instancia de navegador por slide | Pipeline tarda 5-10 min solo en screenshots | Reutilizar una sola instancia de Browser/Context para todas las slides del mismo run | A partir de 5 slides, el overhead de lanzar Chromium cada vez es > 30 s |
| WhisperX en CPU sin optimización | Transcribir 2 min de audio tarda 10+ min | Usar `compute_type="int8"` en CPU; GPU para producción | En CPU sin int8, escala O(n) con la duración del audio |
| Llamadas Claude en serie para todas las slides del guion | El guion de 10 slides tarda 3-5 min (latencia de red acumulada) | Generar el guion de todas las slides en una sola llamada; solo paralelizar si el guion es > 4000 tokens | A partir de 15+ slides si se generan en serie |
| FFmpeg concatenando imágenes individuales sin GOP adecuado | El seeking en el vídeo final es impreciso y lento | Fijar `-g fps*2` (p.ej. `-g 50` para 25 fps) para keyframes cada 2 s | No rompe, pero seeking impreciso afecta a reproductores web |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Loguear el contenido del guion (narración) en logs de debug | Filtración de contenido propietario si los logs son accesibles | Loguear solo metadatos (longitud del guion, número de palabras), nunca el texto completo |
| Guardar `ANTHROPIC_API_KEY` y `ELEVENLABS_API_KEY` en el código o en `config.yaml` commiteado | Compromiso de las API keys y cargos no autorizados | Leer exclusivamente de variables de entorno en runtime; añadir `config.yaml` y `.env` al `.gitignore` |
| Incluir el contexto de entrada (`.pptx`, `.pdf`) en el workdir sin restricción de acceso | El workdir puede contener documentos confidenciales | Documentar que el workdir debe estar fuera del repositorio; añadir `workdir/` al `.gitignore` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Pipeline sin progreso visible (silencio total durante síntesis de voz) | El usuario no sabe si el proceso está corriendo o se ha colgado | Usar `rich.Progress` con barra de progreso por etapa y logging de eventos clave |
| Abortar el pipeline sin guardar el checkpoint de la etapa en curso | El usuario pierde el trabajo de la etapa parcialmente completada y paga la API de nuevo | Capturar `KeyboardInterrupt` y `SIGTERM`, guardar el estado parcial antes de salir |
| Error de API (ElevenLabs 429) sin mensaje claro + sugerencia de acción | El usuario recibe un stack trace y no sabe qué hacer | Interceptar errores de API conocidos y devolver mensajes de error accionables: "Límite de crédito ElevenLabs alcanzado. Verifica tu saldo en elevenlabs.io" |
| El `--dry-run` no estima el coste con detalle por etapa | El usuario no puede presupuestar el coste antes de ejecutar | El dry-run debe desglosar: tokens Anthropic (storyboard + guion + verificador), caracteres ElevenLabs, y tiempo estimado de WhisperX |

---

## "Looks Done But Isn't" Checklist

- [ ] **Generación de slides:** El PNG tiene el tamaño correcto (1920x1080) y el texto usa la fuente del tema, no la fuente de fallback del sistema — verificar con `identify slide_01.png` (ImageMagick) o inspeccionando el PNG con PIL.
- [ ] **Timestamps ElevenLabs:** La secuencia de timestamps es estrictamente creciente y no hay grupos de palabras con el mismo timestamp — verificar con la función de validación antes de generar el SRT.
- [ ] **Montaje FFmpeg:** Los streams de audio y vídeo del fichero final tienen la misma duración total — verificar con `ffprobe -v error -show_entries stream=codec_type,duration`.
- [ ] **Idempotencia:** Ejecutar el pipeline dos veces sobre el mismo workdir produce el mismo vídeo sin llamar a APIs externas en la segunda ejecución — verificar con mocks de requests en los tests.
- [ ] **Docker + Playwright:** El PNG generado dentro del contenedor tiene el mismo aspecto que el generado en local — comparar visualmente o con hash MD5 de píxeles con la misma imagen de Docker.
- [ ] **Subtítulos SRT:** El primer y último subtítulo coinciden con el inicio y fin del audio — reproducir el vídeo con subtítulos y verificar el primer y último bloque.
- [ ] **Loudness:** El audio del vídeo final mide entre -18 y -14 LUFS integrado — verificar con `ffmpeg -i output.mp4 -filter:a loudnorm=print_format=json -f null -`.

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

---

## Sources

- [ElevenLabs: Speech Timestamp Stagnation Bug (issue #607)](https://github.com/elevenlabs/elevenlabs-python/issues/607)
- [ElevenLabs: API Reference - Text-to-Speech with Timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)
- [WhisperX: Word-level timestamp inaccuracy vs MFA (issue #1247)](https://github.com/m-bain/whisperX/issues/1247)
- [WhisperX: Digits/symbols get no word-level timestamps (issue #1372)](https://github.com/m-bain/whisperX/issues/1372)
- [Playwright: Screenshot fails if fonts cannot be loaded (issue #35972)](https://github.com/microsoft/playwright/issues/35972)
- [Playwright: How to wait for font loading in tests](https://testautomationmastery.com/how-to-wait-for-font-loading-to-ensure-complete-page-load-in-playwright-tests/)
- [Playwright Docker: Missing browser libraries and font issues](https://getautonoma.com/blog/playwright-docker-guide)
- [Playwright Docker: Font rendering differences CI vs local](https://github.com/microsoft/playwright/issues/35143)
- [Playwright Official Docker docs](https://playwright.dev/docs/docker)
- [FFmpeg Audio Normalization: loudnorm two-pass guide](https://32blog.com/en/ffmpeg/ffmpeg-audio-normalization-loudnorm)
- [ffmpeg-normalize library (slhck)](https://github.com/slhck/ffmpeg-normalize)
- [FFmpeg xfade + acrossfade crossfade gist](https://gist.github.com/royshil/369e175960718b5a03e40f279b131788)
- [Anthropic: Structured Outputs documentation](https://docs.claude.com/en/docs/build-with-claude/structured-outputs)
- [Anthropic API Rate Limits and 429/529 handling](https://www.respan.ai/articles/anthropic-api-rate-limits)
- [WhisperX Docker GPU image (jim60105)](https://github.com/jim60105/docker-whisperX)
- [Audio-Video Sync testing pitfalls](https://www.testdevlab.com/blog/how-to-test-audio-video-sync)

---
*Pitfalls research for: pipeline Python vídeo narrado (Playwright + ElevenLabs + WhisperX + FFmpeg + Anthropic)*
*Researched: 2026-05-25*
