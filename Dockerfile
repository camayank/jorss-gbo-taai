# =============================================================================
# Jorss-Gbo CPA Lead Platform - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production image
# Usage:
#   docker build -t jorss-gbo:latest .
#   docker run -p 8000:8000 --env-file .env.production jorss-gbo:latest
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim as production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy application code
COPY src/ ./src/
COPY database/ ./database/

# Create data directories
RUN mkdir -p /app/data /app/logs /app/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT="production"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Expose port
EXPOSE 8000

# Default command - run with uvicorn
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# -----------------------------------------------------------------------------
# Stage 3: Development - Full development environment
# -----------------------------------------------------------------------------
FROM production as development

USER root

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install dev dependencies
COPY requirements-dev.txt* ./
RUN if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

USER appuser

# Development mode with hot reload
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
