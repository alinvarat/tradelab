FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRADELAB_HOST=0.0.0.0 \
    TRADELAB_NEWS_ARCHIVE=1 \
    TRADELAB_NEWS_DIR=/app/data/news \
    TRADELAB_BUZZ_DIR=/app/data/buzz

WORKDIR /app

COPY server.py ./
COPY core ./core
COPY ui ./ui

RUN useradd --system --uid 10001 --create-home app \
    && chown -R app:app /app

USER app
EXPOSE 8770

CMD ["python", "server.py"]
