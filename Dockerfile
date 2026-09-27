# Imagen de la API (Fly.io). El procesamiento de vídeo NO corre aquí, sino en Modal (deploy/modal_app.py);
# la API solo necesita ffprobe para validar las subidas.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias primero (capa cacheada mientras pyproject.toml no cambie).
COPY pyproject.toml README.md ./
RUN python -c "import tomllib; p = tomllib.load(open('pyproject.toml', 'rb'))['project']; \
print('\n'.join(p['dependencies'] + p['optional-dependencies']['modal']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY src ./src
COPY configs ./configs
COPY migrations ./migrations
RUN pip install --no-deps -e . \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/data && chown app /app/data
USER app

EXPOSE 8080
CMD ["smartcuts", "api", "--host", "0.0.0.0", "--port", "8080"]
