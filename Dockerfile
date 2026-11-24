FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRADELAB_HOST=0.0.0.0 \
    TRADELAB_NEWS_ARCHIVE=1 \
    TRADELAB_NEWS_DIR=/app/data/news \
    TRADELAB_BUZZ_DIR=/app/data/buzz \
    TRADELAB_DVOL_DIR=/app/data/dvol \
    TRADELAB_COLLECT_DIR=/app/data/collect

WORKDIR /app

# Anthropic SDK for the Claude Haiku 5.5 provider (core/ai_news.py); everything else is the standard library.
RUN pip install --no-cache-dir anthropic==2.13.0

COPY server.py ./
COPY core ./core
COPY ui ./ui

RUN useradd --system --uid 10001 --create-home app \
    && chown -R app:app /app

USER app
EXPOSE 8770

CMD ["python", "server.py"]
