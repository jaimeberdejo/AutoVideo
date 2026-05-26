# Imagen base: Playwright pineado a la versión de playwright en uv.lock (1.60.0).
# Mismatch de tag = browsers no encontrados en runtime.
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

# Deps de sistema: FFmpeg (montaje de vídeo) + Poppler (fallback pdf2image en ingesta).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Binario uv para instalación reproducible de dependencias.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copiar manifiestos primero para cachear la capa de dependencias.
COPY pyproject.toml uv.lock ./

# Instalación reproducible desde el lock; sin dev deps y sin el extra 'record'
# (el extra 'record' con ~2GB de deps de ML es solo para modo grabacion — ver README).
RUN uv sync --frozen --no-dev

# Copiar el código fuente del proyecto.
COPY src ./src

# Asegurar que el Chromium pineado del paquete está disponible
# (la imagen base ya lo trae; este paso garantiza coincidencia con playwright 1.60.0).
RUN uv run playwright install chromium

# Las claves de API se inyectan en runtime vía variables de entorno o .env montado:
#   docker run -e ANTHROPIC_API_KEY=... -e ELEVENLABS_API_KEY=... ...
# NUNCA se hornean en la imagen (ver threat_model T-07-02).

ENTRYPOINT ["uv", "run", "avideo"]
CMD ["--help"]
