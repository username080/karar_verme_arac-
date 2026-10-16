FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/data/choices.db \
    PORT=8767

RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /data \
    && chown app:app /data

WORKDIR /srv
COPY app/ /srv/app/

VOLUME /data
EXPOSE 8767
USER app

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8767'), timeout=2)"]

CMD ["python", "app/server.py"]
