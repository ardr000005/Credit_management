# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# wait-for-db script
COPY <<'EOF' /wait-for-db.py
import time
import os
from urllib.parse import urlparse
import psycopg2
from psycopg2 import OperationalError

def wait_for_db():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not set")
        return
    parsed = urlparse(db_url)
    conn_params = {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'user': parsed.username,
        'password': parsed.password,
        'dbname': parsed.path[1:] if parsed.path else 'postgres'
    }
    print("Waiting for PostgreSQL...")
    while True:
        try:
            conn = psycopg2.connect(**conn_params)
            conn.close()
            print("PostgreSQL is ready!")
            break
        except OperationalError:
            print("PostgreSQL not ready, retrying in 2s...")
            time.sleep(2)

if __name__ == "__main__":
    wait_for_db()
EOF

RUN chmod +x /wait-for-db.py

EXPOSE 8000
CMD ["gunicorn", "credit_system.wsgi:application", "--bind", "0.0.0.0:8000"]