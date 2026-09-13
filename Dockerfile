FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY frontend/requirements.txt /tmp/frontend-requirements.txt

RUN pip install --upgrade pip && \
    pip install -r /tmp/backend-requirements.txt -r /tmp/frontend-requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY start.sh /app/start.sh

RUN chmod +x /app/start.sh && mkdir -p /tmp/leadpilot-chroma

EXPOSE 8501

CMD ["/app/start.sh"]
