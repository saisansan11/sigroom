FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Install build/runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, deterministic dependency install
RUN pip install --no-cache-dir uv

COPY pyproject.toml .

# Install dependencies including gunicorn
RUN uv pip install --system --no-cache \
    "django>=5.2,<5.3" \
    "psycopg[binary]>=3.2" \
    "python-dotenv>=1.0" \
    "django-htmx>=1.19" \
    "argon2-cffi>=23" \
    "whitenoise>=6.8" \
    "gunicorn>=22.0"

COPY . .

# Collect static files into STATIC_ROOT
RUN DJANGO_SECRET_KEY=dummy-for-build python manage.py collectstatic --noinput

EXPOSE 8080

CMD exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 2 \
    --timeout 60
