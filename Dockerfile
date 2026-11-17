FROM python:3.15-alpine3.24

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUNICORN_BIND=0.0.0.0:8000

# Default user for running the image directly; change it with --build-arg. The
# mounted content directory must be writable by this UID for admin uploads to work.
# Compose ignores it and runs as APP_UID/APP_GID from .env (user: in compose.yaml).
ARG APP_UID=1000
ARG APP_GID=1000
RUN addgroup -g "$APP_GID" store && adduser -D -H -u "$APP_UID" -G store store

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# The code stays owned by root, so the app user can't modify it.
COPY gunicorn.conf.py .
COPY wunderland/ wunderland/

USER store
EXPOSE 8000
CMD ["gunicorn", "wunderland.app:app"]
