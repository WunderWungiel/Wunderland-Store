#!/bin/sh

# Each request can hold two of the pool's four database connections.
exec gunicorn --workers 8 --worker-class gthread --threads 2 --bind 0.0.0.0:80 main:app
