from flask import Blueprint

# JSON API for native clients, registered under /api/v1. It is stateless: no
# cookie session, no session token lookup and no CSRF check (see app.py).
api = Blueprint('api', __name__)
