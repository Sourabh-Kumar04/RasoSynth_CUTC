# Multi-stage build for production optimization
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Create working directory
WORKDIR /app

# Copy README first (required for package metadata)
COPY README.md ./

# Copy and install dependencies (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 app \
    && useradd -m -u 1000 -g app app

# Copy uv binary to system-wide location accessible by non-root users
COPY --from=builder /root/.local/bin/uv /usr/local/bin/uv
RUN chmod +x /usr/local/bin/uv

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
RUN chmod -R a+rX /app/.venv

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create working directory
WORKDIR /app

# Copy source code
COPY --chown=app:app . .

# Create outputs directory with proper permissions
RUN mkdir -p /app/outputs && chown -R app:app /app

# Switch to non-root user
USER app

# Expose port
EXPOSE 8000

# Health check with proper start delay
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with production settings
CMD ["uv", "run", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--limit-concurrency", "100"]