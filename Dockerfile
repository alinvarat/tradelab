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

# curl + certificates for the Claude Code installer (Claude Haiku 5.5 on the owner's Max plan, core/ai_news.py)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home app \
    && chown app:app /app

USER app
ENV PATH=/home/app/.local/bin:$PATH \
    DISABLE_AUTOUPDATER=1
# Claude Code CLI for the app user; the build fails if it does not run. Auth comes only from the runtime env.
RUN curl -fsSL https://claude.ai/install.sh | bash && claude --version

COPY --chown=app:app server.py ./
COPY --chown=app:app core ./core
COPY --chown=app:app ui ./ui

EXPOSE 8770

CMD ["python", "server.py"]
