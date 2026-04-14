from datetime import datetime, timedelta, timezone
import secrets

import bcrypt

from ..database import pool

def generate_password(password):
    password = password.encode('utf-8')
    salt = bcrypt.gensalt()

    password_hash = bcrypt.hashpw(password, salt)
    return password_hash.decode('utf-8')


def get_session(token):

    query = "SELECT sessions.*, users.username, users.email FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = %s AND sessions.expires_at > NOW()"
    params = [token]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def delete_session(token):

    query = "DELETE FROM sessions WHERE token = %s"
    params = [token]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)


def get_user_by_id(user_id):
    query = "SELECT * FROM users WHERE id = %s"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, [user_id])
            return cursor.fetchone()


def get_user_by_username(username):
    query = "SELECT * FROM users WHERE username = %s"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, [username])
            return cursor.fetchone()


def get_user_by_email(email):
    query = "SELECT * FROM users WHERE email = %s"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, [email])
            return cursor.fetchone()


def check_confirmation_token(confirmation_token):

    query = "SELECT * FROM users WHERE confirmation_token = %s"
    params = [confirmation_token]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def confirm(user_id):

    query = "UPDATE users SET confirmed = TRUE, confirmation_token = NULL, confirmation_token_expires_at = NULL WHERE id = %s"
    params = [user_id]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)


def login(email, password):

    user = get_user_by_email(email)

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return None

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    query = "INSERT INTO sessions (user_id, token, expires_at) VALUES (%s, %s, %s)"
    params = [user['id'], token, expires_at]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

    return {'token': token}


def register(email, password, username):

    confirmation_token = secrets.token_urlsafe(32)
    confirmation_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    query = "INSERT INTO users (email, username, password, confirmed, confirmation_token, confirmation_token_expires_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *"
    params = [email, username, generate_password(password), False, confirmation_token, confirmation_token_expires_at]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()

    if result:
        result.pop('password', None)

    return result


def change_password(user_id, password):

    password_hash = generate_password(password)
    query = "UPDATE users SET password = %s WHERE id = %s"
    params = (password_hash, user_id)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

def check_credentials(email, password):

    user = get_user_by_email(email)

    if not user:
        return False

    return bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
