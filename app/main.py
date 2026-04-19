from datetime import datetime

from flask import Flask, g, session, send_from_directory
import humanize
import atexit
import logging

from utils import config
from utils import db
from utils.blueprints import auth, client, legacy, qtstore, store

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = config['secret_key']
app.config['SECURITY_PASSWORD_SALT'] = app.config['SECRET_KEY']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if config['proxy']:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

app.register_blueprint(auth)
app.register_blueprint(client)
app.register_blueprint(legacy)
app.register_blueprint(store)
app.register_blueprint(qtstore)


atexit.register(db.pool.close)


@app.template_filter('naturalsize')
def naturalsize_filter(size):
    return humanize.naturalsize(size)


@app.context_processor
def utility_processor():
    return dict(
        now=datetime.now(),
        get_content_types=db.get_content_types
    )


@app.before_request
def load_global_data():
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


if not config['allow_indexing']:
    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=config['port'])
