import logging

import click

from . import db

logger = logging.getLogger(__name__)


@click.command()
def clean():
    """Delete expired unconfirmed users and expired sessions."""
    with db.pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE confirmation_token_expires_at < NOW()")
            users = cursor.rowcount
            cursor.execute("DELETE FROM sessions WHERE expires_at < NOW()")
            sessions = cursor.rowcount
    logger.info("Deleted %d expired unconfirmed users and %d expired sessions", users, sessions)
