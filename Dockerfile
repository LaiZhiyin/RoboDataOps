FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY app.py ./
COPY .streamlit ./.streamlit
COPY data/demo ./data/demo
COPY data/public_sample ./data/public_sample
COPY data/aloha_sample ./data/aloha_sample
COPY data/public_delivery ./data/public_delivery
RUN useradd --create-home --user-group robodataops && mkdir -p /app/var /app/data/derived && chown -R robodataops:robodataops /app
USER robodataops
ENV ROBODATAOPS_DEMO_MODE=1 PYTHONUNBUFFERED=1
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD curl --fail http://localhost:8501/_stcore/health || exit 1
CMD ["/app/.venv/bin/streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true"]
