FROM python:3.11-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get purge -y curl && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app
COPY . .

RUN uv sync && \
    uv --directory ./mcp_servers/lme_price sync && \
    uv --directory ./mcp_servers/mining_news sync && \
    uv --directory ./mcp_servers/mineral_pdf sync && \
    uv --directory ./apps/daily_agent sync

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uv", "--directory", "./apps/daily_agent", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
