FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY public ./public
RUN pip install --no-cache-dir .

EXPOSE 8000
# Uygulamaya yalnızca compose ağındaki Caddy ulaşır; bu yüzden X-Forwarded-For'a güvenilir
# (istek sınırı gerçek istemci IP'sini görsün).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
