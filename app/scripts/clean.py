#!/usr/bin/env python3
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils import db

def clean():
    with db.pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE confirmation_token_expires_at < NOW()")
            cursor.execute("DELETE FROM sessions WHERE expires_at < NOW()")

if __name__ == "__main__":
    clean()
    db.pool.close()
