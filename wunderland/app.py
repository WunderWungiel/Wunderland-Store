import atexit
import logging
from datetime import datetime

from flask import Flask, g, render_template, request, session, send_from_directory
from flask.sessions import SecureCookieSessionInterface
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
import humanize
import psycopg

from . import cli, csrf, db, helpers
from .blueprints import api, auth, client, legacy, qtstore, store
from .blueprints.api import error_response as api_error_response, is_api_request
from .config import CONTENT_DIR, config

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = config['secret_key']
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app.register_blueprint(api, url_prefix='/api/v1')
app.register_blueprint(auth)
app.register_blueprint(client)
app.register_blueprint(legacy)
app.register_blueprint(store)
app.register_blueprint(qtstore)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

atexit.register(db.pool.close)

app.cli.add_command(cli.clean)


# Uploaded files live outside the package but keep their old /static/content/ URLs,
# which device clients and old links rely on. This rule outranks the built-in /static/ one.
@app.route("/static/content/<path:filename>")
def content(filename):
    return send_from_directory(CONTENT_DIR, filename)


# Probed by the Docker healthchecks, whose timeout is 5s. The pool timeout bounds the
# wait for a connection and the statement timeout bounds the query, so a DB that is
# down or overloaded fails the probe instead of holding a worker thread. The statement
# timeout is enforced by the server, so it can't help if the server stops responding
# altogether. SET LOCAL lasts only until the pool commits on leaving the block.
@app.route("/healthz")
def healthz():
    headers = {"Content-Type": "text/plain", "Cache-Control": "no-store"}
    try:
        with db.pool.connection(timeout=2) as connection:
            connection.execute("SET LOCAL statement_timeout = '2s'")
            connection.execute("SELECT 1")
    except psycopg.Error as error:
        logger.warning("Health check failed: %s", error)
        return "db unavailable", 503, headers
    return "ok", 200, headers


@app.template_filter('naturalsize')
def naturalsize_filter(size):
    return humanize.naturalsize(size)


@app.template_filter('nl2br')
def nl2br_filter(text):
    return helpers.nl2br(text)


@app.context_processor
def utility_processor():
    return dict(
        now=datetime.now(),
        csrf_token=csrf.generate_token,
        get_content_types=db.get_content_types
    )


# Plain file endpoints: no session lookup, and a bare 404 for missing files.
FILE_ENDPOINTS = ('static', 'content')
# Health probes skip the session lookup too, so they don't hit the sessions table.
SESSIONLESS_ENDPOINTS = FILE_ENDPOINTS + ('healthz',)


def is_sessionless():
    # The JSON API is stateless: it neither reads nor sets the cookie session.
    return request.endpoint in SESSIONLESS_ENDPOINTS or is_api_request()


class SessionInterface(SecureCookieSessionInterface):
    """Don't refresh the permanent session cookie on sessionless requests.

    Otherwise every icon and stylesheet carries Set-Cookie and Vary: Cookie,
    which wastes bytes and keeps shared caches from storing them.
    """

    def should_set_cookie(self, app, session):
        if is_sessionless():
            return session.modified
        return super().should_set_cookie(app, session)


app.session_interface = SessionInterface()


@app.before_request
def load_global_data():
    if is_sessionless():
        return

    session.permanent = True

    platform_id = session.get('platform_id')
    if platform_id:
        g.platform = db.get_platform(platform_id)
        if not g.platform:
            session['platform_id'] = None
    else:
        g.platform = None

    token = session.get('token')
    if not token:
        g.user = None
        return

    user = db.get_session(token)
    if not user:
        session.pop('token', None)
        g.user = None
        return

    g.user = user


@app.before_request
def check_csrf():
    # API clients won't authenticate with the cookie, so there is nothing to forge.
    if is_sessionless():
        return None
    return csrf.protect()


# Device clients parse these responses, so leave their errors untouched.
XML_BLUEPRINTS = ('client', 'qtstore')


@app.errorhandler(HTTPException)
def http_error(e):
    # Every other HTTP error keeps Werkzeug's default page, except under the JSON API.
    if is_api_request():
        return api_error_response(e)
    return e


@app.errorhandler(404)
def not_found(e):
    if is_api_request():
        return api_error_response(e)
    # Missing static files (icons, screenshots) don't need a full page.
    if request.blueprint in XML_BLUEPRINTS or request.endpoint in FILE_ENDPOINTS:
        return e
    return render_template(
        'error.html',
        title="Page not found",
        message="The page you are looking for does not exist or has been removed.",
        show_navigation=True
    ), 404


@app.errorhandler(500)
def internal_error(e):
    if is_api_request():
        return api_error_response(e)
    if request.blueprint in XML_BLUEPRINTS:
        return e
    # No navigation: it queries the DB, which may be what failed.
    return render_template(
        'error.html',
        title="Server error",
        message="Something went wrong on our side. Please try again later.",
        show_navigation=False
    ), 500


if not config['allow_indexing']:
    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")
