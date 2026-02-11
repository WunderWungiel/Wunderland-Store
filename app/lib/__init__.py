import psycopg2

from .config import config

connection = psycopg2.connect(database=config["database"]['name'],
    host=config["database"]['host'],
    user=config["database"]['user'],
    password=config["database"]['password']
)

from .api import api as api_blueprint
from .store import store as store_blueprint
from .news import news as news_blueprint
