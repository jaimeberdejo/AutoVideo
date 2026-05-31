# Ejemplo de demo — "Cómo crear tu primer presupuesto personal en 5 pasos"

Ejemplo completo para recorrer las 6 fases del Studio (`avideo studio` → http://localhost:8501).
Pensado para ~120 s, 5 slides, en español.

Ficheros:
- `bullets.yaml` — título + 5 bullets (formato exacto que consume el motor).
- `music_bed.mp3` — pista ambiental de 30 s (generada con ffmpeg) para probar la música de fondo en la Fase 5.

---

## Qué introducir en cada fase

### Fase 1 — Contenido
- **Tema:** `Cómo crear tu primer presupuesto personal en 5 pasos`
- **Duración objetivo:** `120` (segundos)
- **Bullets:** dos formas de probar —
  - **Opción A (manual):** copia los 5 bullets de `bullets.yaml` en el editor (uno por fila).
  - **Opción B (auto):** elige "Generar desde el tema" y deja que Claude los proponga; luego edítalos.
- **Aprobar** → debe escribir `workdir/bullets.yaml` y avanzar.

### Fase 2 — Guion
- Al entrar, se generan storyboard → timing → guion automáticamente (un spinner por etapa).
- Edita el texto de algún slide y pulsa guardar.
- Pulsa **"Pedir variación"** en un slide → debe re-generar **solo** el guion (no todo).
- **Aprobar guion**.

### Fase 3 — Diapositivas
- **Modo auto:** deja que la app las genere → aparecen miniaturas con badges QC (ok/warning/fail).
- (Alternativa: **subir** las tuyas en PNG/PDF → verificador Claude Vision.)
- **Aprobar diapositivas**.

### Fase 4 — Voz
- Recomendado: **ElevenLabs** u **OpenAI Audio** (ya tienes ambas claves).
  - Con OpenAI verás un paso extra de alineación (`whisper-1`) para los subtítulos — es lo esperado.
- (Opcional **grabaciones propias:** sube un `.wav`/`.mp3` por slide; prueba el botón **"Mejorar audio"** → compara antes/después → "Adoptar". Nota: el gate exige timestamps válidos, así que necesita voz real, no un tono.)
- Escucha los previews `st.audio` y **Aprobar voz**.

### Fase 5 — Extras
- **Subtítulos:** activa el toggle de quemado si quieres verlos en el vídeo.
- **Música de fondo:** sube `examples/demo-presupuesto/music_bed.mp3`, ajusta el **volumen** (~0.12) y el **fade**.
- **Crossfade:** prueba ~0.5 s.
- **Aprobar extras** (genera los subtítulos `.srt`/`.vtt`).

### Fase 6 — Ensamblaje
- Pulsa **"Montar vídeo"** → el progreso de FFmpeg avanza sin congelar la UI.
- Al acabar: reproductor `st.video`, botón de descarga del `output.mp4`, y métricas QA (desviación de duración + LUFS).

---

## Prueba de resiliencia (el fix del audit)
En cualquier fase, **recarga el navegador (F5)** — el wizard debe retomar exactamente donde estabas, reconstruyendo el estado desde `workdir/`.

## Alternativa headless (CLI, sin UI)
Sanity check del motor con el mismo ejemplo:
```
uv run avideo generate --bullets examples/demo-presupuesto/bullets.yaml --duration 120 --voice elevenlabs --slides-mode auto --level 4 --dry-run
```
(Quita `--dry-run` para generar de verdad.)
