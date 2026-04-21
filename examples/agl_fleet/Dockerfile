FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

ENV IGNITION_GATEWAY_URL=http://localhost:8088
ENV SIM_SITES=5
ENV SIM_UNITS=4
ENV SIM_INTERVAL_MS=500
ENV SIM_TICKS=0

ENTRYPOINT ["uv", "run", "agl-sim"]
