# ============================================================
# Stage 1: builder — install system deps and Python packages
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system build dependencies (cached unless this layer changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first — this layer is cached until requirements.txt changes
COPY requirements.txt .

# Install into a separate prefix so we can copy it cleanly to the runtime stage
RUN pip install --prefix=/install -r requirements.txt


# ============================================================
# Stage 2: runtime — lean final image with no build tools
# ============================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install only the runtime system libraries needed by psycopg2 (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy source code (changes here don't invalidate the pip cache above)
COPY . .

# Expose port
EXPOSE 8000

# Set the entrypoint script
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
