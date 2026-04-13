from datetime import datetime

from flask import Flask, g, session, render_template, send_from_directory
import humanize

from lib import database as db
from lib import config, applist, auth, legacy, store, qtstore
from lib.auth import database as auth_db
from lib.auth.routes import session_logout

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = config['secret_key']
app.config['SECURITY_PASSWORD_SALT'] = app.config['SECRET_KEY']

if config['proxy']:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

app.register_blueprint(applist)
app.register_blueprint(auth)
app.register_blueprint(legacy)
app.register_blueprint(store)
app.register_blueprint(qtstore)

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
def before_request():
    session.permanent = True

    platform_id = session.get('platform_id')

    if platform_id:
        g.platform = db.get_platform(platform_id)
        if not g.platform: 
            session['platform_id'] = None
    else:
        g.platform = None

    user_id = session.get('user_id')
    g.user = None

    if not user_id:
        session_logout()
    else:
        user = auth_db.get_user(user_id=user_id)

        if user:
            user.pop('password', None)
            g.user = user

if not config['allow_indexing']:
    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=config['port'])
