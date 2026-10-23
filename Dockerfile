FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.0 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Optional build-only CA bundle for managed corporate/cloud proxies.
RUN --mount=type=secret,id=ca_bundle \
    if [ -f /run/secrets/ca_bundle ]; then \
      SSL_CERT_FILE=/run/secrets/ca_bundle uv sync --frozen --no-dev; \
    else uv sync --frozen --no-dev; fi
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
