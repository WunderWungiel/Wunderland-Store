from datetime import datetime

from flask import Flask, session, render_template, send_from_directory
import humanize

from lib import database as db
from lib import config, api_blueprint, store_blueprint
from lib.applist import applist_blueprint
from lib.auth import auth_blueprint, database as auth_db
from lib.qtstore import qtstore_blueprint
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

app.register_blueprint(api_blueprint)
app.register_blueprint(store_blueprint)
app.register_blueprint(applist_blueprint)
app.register_blueprint(auth_blueprint)
app.register_blueprint(qtstore_blueprint)

@app.context_processor
def utility_processor():

    def get_natural_size(size):
        return humanize.naturalsize(size)

    def get_user(user_id):
        user = auth_db.get_user(user_id)
        user.pop('password', None)
        return user

    return dict(now=datetime.now(), get_platform=db.get_platform, get_user=get_user, get_natural_size=get_natural_size, get_content_types=db.get_content_types)

@app.before_request
def check_platform_id():
    session.permanent = True

    platform_id = session.get('platform')
    if not platform_id:
        session['platform'] = None
    user_id = session.get('user_id')

    if not user_id:
        session_logout()
        return
    else:
        user = auth_db.get_user(id=user_id)
        if user['banned']:
            session_logout()
            return render_template("auth/banned.html", reason=user['banned_reason'])

@app.route("/robots.txt")
def robots():
    return send_from_directory(app.static_folder, "robots.txt")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=config['port'])
