# ── Build ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS build
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
# git is nodig omdat truenas_api_client niet op PyPI staat en via
# git+https geïnstalleerd wordt (zie pyproject.toml).
RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY src ./src
RUN pip install --prefix=/install .

# ── Runtime (hardened) ─────────────────────────────────────────────────────
# Slank image, niet-root, met DejaVu-fonts (nodig voor de tekstrendering) en
# tzdata (voor de kop-tijdstempel in de eigen tijdzone).
FROM python:3.12-slim
RUN apt-get update \
  && apt-get install -y --no-install-recommends fonts-dejavu-core tzdata \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd -g 10001 app \
  && useradd -u 10001 -g app -M -s /usr/sbin/nologin app \
  && mkdir -p /data && chown app:app /data
COPY --from=build /install /usr/local

USER app
ENV PYTHONUNBUFFERED=1 \
    KD_DATA_DIR=/data \
    KD_TZ=Europe/Amsterdam \
    KD_HTTP_PORT=8000
VOLUME /data
EXPOSE 8000

# De scheduler raakt elke tick $KD_DATA_DIR/heartbeat aan; als dat bestand
# ouder dan ~2 minuten is, is er iets mis en faalt de healthcheck. Gebruikt
# de env var (met /data als fallback) i.p.v. een hardcoded pad, zodat een
# afwijkende KD_DATA_DIR (mét bijbehorende volume-mount) de healthcheck niet
# stilzwijgend tegen het verkeerde pad laat controleren.
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
  CMD test "$(( $(date +%s) - $(stat -c %Y "${KD_DATA_DIR:-/data}/heartbeat" 2>/dev/null || echo 0) ))" -lt 150 || exit 1

CMD ["python", "-m", "kindle_dashboard.main"]
