FROM python:3.15-alpine3.24

# The app runs as this user. The host's ./Ovi mount must be writable by
# the same UID for admin uploads to work.
ARG APP_UID=1000
ARG APP_GID=1000
RUN addgroup -g "$APP_GID" store && adduser -D -H -u "$APP_UID" -G store store

WORKDIR /app
COPY ./app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# The code stays owned by root, so the app user can't modify it.
COPY ./app/ .

USER store
ENTRYPOINT ["./entrypoint.sh"]
