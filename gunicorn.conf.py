import os

# Each request can hold two of the pool's four database connections.
bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", 8))
worker_class = "gthread"
threads = 2
# The app user has no home directory for the control socket, and nothing uses gunicornc.
control_socket_disable = True
