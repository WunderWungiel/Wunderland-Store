import os

from flask import Flask, send_from_directory

from lib import config, api_blueprint, auth_blueprint, store_blueprint, applist_blueprint, qtstore_blueprint, news_blueprint, nnhub_blueprint, submissions_blueprint

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = config["SECRET_KEY"]
app.config['SECURITY_PASSWORD_SALT'] = app.config['SECRET_KEY']
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, "content", "uploads")

if config["PROXY"]:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

app.register_blueprint(api_blueprint)
app.register_blueprint(auth_blueprint)
app.register_blueprint(store_blueprint)
app.register_blueprint(applist_blueprint)
app.register_blueprint(qtstore_blueprint)
app.register_blueprint(news_blueprint)
app.register_blueprint(nnhub_blueprint)
app.register_blueprint(submissions_blueprint)

@app.route("/robots.txt")
def _robots():
    return send_from_directory(app.static_folder, "robots.txt")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=7000)