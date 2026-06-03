# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system libraries only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY apex/ ./apex/
COPY configs/ ./configs/
COPY pyproject.toml ./

# Create data directories
RUN mkdir -p /app/data /app/logs

# Non-root user for security
RUN useradd -m -u 1000 apex && chown -R apex:apex /app
USER apex

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "apex.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
