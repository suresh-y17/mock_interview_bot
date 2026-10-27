# Optional container build. Render/Railway do not need this (they read run.sh),
# but Fly.io, Google Cloud Run and plain `docker run` do.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The database is created and seeded on first boot, so no build-time DB is needed.
EXPOSE 8000
CMD ["bash", "run.sh"]
