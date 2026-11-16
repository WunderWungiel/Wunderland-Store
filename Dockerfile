FROM python:3.15-alpine3.24

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The app runs as this user. The host's ./content directory must be writable by
# the same UID for admin uploads to work. Compose passes APP_UID/APP_GID from .env.
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
