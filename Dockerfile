FROM python:3.11-slim

# 1. ติดตั้ง System Dependencies (รวม cron สำหรับ CRONJOBS)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libffi-dev \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 2. ตั้งค่า Directory และ User
RUN useradd -m -u 1000 django && \
    mkdir -p /app /app/staticfiles /app/dog_images && \
    chown -R django:django /app

WORKDIR /app

# 3. ติดตั้ง Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn  

# 4. Copy โปรเจกต์
COPY --chown=django:django . .

# 5. ตั้งค่าสิทธิ์และ Entrypoint
RUN chmod +x /app/entrypoint.sh
USER django

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "findmydog.wsgi:application"]