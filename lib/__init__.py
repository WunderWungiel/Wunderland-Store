import psycopg2

from .config import config

conn = psycopg2.connect(database=config["DB_NAME"],
    host=config["DB_HOST"],
    user=config["DB_USER"],
    password=config["DB_PASS"]
)

from .api import api as api_blueprint
from .store import store as store_blueprint
from .auth import auth as auth_blueprint
from .applist import applist as applist_blueprint
from .qtstore import qtstore as qtstore_blueprint
from .news import news as news_blueprint
from .nnhub import nnhub as nnhub_blueprint
