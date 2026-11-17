import os

# The app trusts X-Forwarded-* headers, so only the reverse proxy should reach it.
# The Docker image sets GUNICORN_BIND to listen on all of the container's interfaces.
bind = os.environ.get("GUNICORN_BIND") or "127.0.0.1:8000"
# Each request can hold two of the pool's four database connections.
workers = int(os.environ.get("WEB_CONCURRENCY", 8))
worker_class = "gthread"
threads = 2
# The app user has no home directory for the control socket, and nothing uses gunicornc.
control_socket_disable = True
