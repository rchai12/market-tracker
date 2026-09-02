FROM python:3.11-slim AS base

WORKDIR /app

# Runtime OS deps only (tini for PID 1, curl for health checks).
# build-essential is installed in the pip layer below and purged afterward.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies only (no app code yet).
# build-essential compiles C extensions (e.g. lightgbm on ARM); remove it after pip
# so gcc does not stay in the final image.
COPY pyproject.toml .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir . \
    && pip cache purge \
    && apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Ensure local packages are importable
ENV PYTHONPATH=/app

# Create non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --no-create-home appuser

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
