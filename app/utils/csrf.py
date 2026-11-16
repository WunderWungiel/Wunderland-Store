import hmac
import secrets

from flask import flash, redirect, request, session, url_for

FIELD_NAME = 'csrf_token'


def generate_token():
    """Return this session's CSRF token, creating it on first use."""
    token = session.get(FIELD_NAME)
    if not token:
        token = secrets.token_urlsafe(32)
        session[FIELD_NAME] = token
    return token


def is_valid(token):
    expected = session.get(FIELD_NAME)
    if not expected or not token or not token.isascii():
        return False
    return hmac.compare_digest(expected, token)


def protect():
    """Reject POST requests whose form token doesn't match the session."""
    if request.method != 'POST':
        return None

    if is_valid(request.form.get(FIELD_NAME)):
        return None

    flash("Your session has expired. Please try again.", "danger")
    if request.url_rule and 'GET' in request.url_rule.methods:
        return redirect(request.script_root + request.full_path.rstrip('?'))
    return redirect(url_for('store.root'))
