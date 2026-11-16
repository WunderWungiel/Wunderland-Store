#!/usr/bin/env python3
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils import db

logger = logging.getLogger("clean")

def clean():
    with db.pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE confirmation_token_expires_at < NOW()")
            users = cursor.rowcount
            cursor.execute("DELETE FROM sessions WHERE expires_at < NOW()")
            sessions = cursor.rowcount
    logger.info("Deleted %d expired unconfirmed users and %d expired sessions", users, sessions)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    clean()
    db.pool.close()
