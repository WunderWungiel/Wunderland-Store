from flask import Flask

from lib import auth_blueprint, store_blueprint, applist_blueprint, qtstore_blueprint, news_blueprint

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = "m5g0450yjbn409j4054yj5"
app.config['SECURITY_PASSWORD_SALT'] = app.config['SECRET_KEY']

app.register_blueprint(auth_blueprint)
app.register_blueprint(store_blueprint)
app.register_blueprint(applist_blueprint)
app.register_blueprint(qtstore_blueprint)
app.register_blueprint(news_blueprint)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=7000)
