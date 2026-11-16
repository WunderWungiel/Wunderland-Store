import atexit
import logging
from datetime import datetime

from flask import Flask, g, render_template, request, session, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
import humanize

from utils import config
from utils import csrf
from utils import db
from utils import utils
from utils.blueprints import auth, client, legacy, qtstore, store

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = config['secret_key']
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app.register_blueprint(auth)
app.register_blueprint(client)
app.register_blueprint(legacy)
app.register_blueprint(store)
app.register_blueprint(qtstore)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

atexit.register(db.pool.close)


@app.template_filter('naturalsize')
def naturalsize_filter(size):
    return humanize.naturalsize(size)


@app.template_filter('nl2br')
def nl2br_filter(text):
    return utils.nl2br(text)


@app.context_processor
def utility_processor():
    return dict(
        now=datetime.now(),
        csrf_token=csrf.generate_token,
        get_content_types=db.get_content_types
    )


@app.before_request
def load_global_data():
    if request.endpoint == 'static':
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


app.before_request(csrf.protect)


# Device clients parse these responses, so leave their errors untouched.
XML_BLUEPRINTS = ('client', 'qtstore')


@app.errorhandler(404)
def not_found(e):
    # Missing static files (icons, screenshots) don't need a full page.
    if request.blueprint in XML_BLUEPRINTS or request.endpoint == 'static':
        return e
    return render_template(
        'error.html',
        title="Page not found",
        message="The page you are looking for does not exist or has been removed.",
        show_navigation=True
    ), 404


@app.errorhandler(500)
def internal_error(e):
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
