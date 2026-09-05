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

# ติดตั้ง dependencies ทั้งหมดจาก pyproject.toml เป็นแหล่งความจริงเดียว — ห้าม hardcode
# รายชื่อแพ็กเกจซ้ำในไฟล์นี้ (เคยทำให้ image ขาด qrcode/django-storages/pillow ทั้งที่
# โค้ดใช้งานจริง เพราะสองรายการคลาดกัน) · gunicorn ระบุแยกเพราะใช้เฉพาะใน container
RUN uv pip install --system --no-cache -r pyproject.toml "gunicorn>=22.0"

COPY . .

# Collect static files into STATIC_ROOT
RUN DJANGO_SECRET_KEY=dummy-for-build python manage.py collectstatic --noinput

EXPOSE 8080

CMD exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 2 \
    --timeout 60
