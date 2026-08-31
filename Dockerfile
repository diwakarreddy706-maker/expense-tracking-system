# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system compilation & database dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies into wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir gunicorn && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels gunicorn

# Final Runtime Image
FROM python:3.11-slim

WORKDIR /app

# Install runtime database libraries and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    libmariadb3 \
    libjpeg62-turbo \
    zlib1g \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Create non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy application source code
COPY . /app

# Ensure directories exist and permissions are set
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=expense_tracking_core.settings.production

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health/ || exit 1

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn --config deploy/gunicorn/gunicorn.conf.py expense_tracking_core.wsgi:application"]
