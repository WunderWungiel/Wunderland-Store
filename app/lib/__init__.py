import psycopg
from psycopg.rows import dict_row

from .config import config

uri = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}/{config['database']['name']}"
connection = psycopg.connect(uri, row_factory=dict_row)

from .api import api as api_blueprint
from .store import store as store_blueprint
