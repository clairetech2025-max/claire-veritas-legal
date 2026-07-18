FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    VERITAS_PUBLIC_DEMO=1 \
    VERITAS_DEMO_MODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN python -m venv /app/.venv \
    && /app/.venv/bin/pip install --upgrade pip \
    && /app/.venv/bin/pip install -r requirements-web.txt

RUN chmod +x /app/start.sh

EXPOSE 7860
CMD ["/app/start.sh"]
