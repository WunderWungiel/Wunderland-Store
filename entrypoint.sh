#!/bin/sh

gunicorn --workers 8 --bind 0.0.0.0:80 main:app
