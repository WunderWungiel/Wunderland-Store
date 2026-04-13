import bcrypt
from psycopg.errors import UniqueViolation

from ..database import pool

def generate_password(password):
    password = password.encode('utf-8')
    salt = bcrypt.gensalt()

    password_hash = bcrypt.hashpw(password, salt)
    return password_hash.decode('utf-8')


def get_user(user_id=None, username=None, email=None):

    query = "SELECT * FROM users"
    where_clauses = []
    params = []

    if user_id is not None:
        where_clauses.append("id = %s")
        params.append(user_id)

    if username is not None:
        where_clauses.append("username = %s")
        params.append(username)

    if email is not None:
        where_clauses.append("email = %s")
        params.append(email)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def confirm_user(email):

    query = "UPDATE users SET confirmed = true WHERE email = %s"
    params = [email]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)


def register(email, user_password, username):

    query = "INSERT INTO users (email, username, password, confirmed) VALUES (%s, %s, %s, %s) RETURNING id, email, username"
    params = [email, generate_password(user_password), username, False]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(query, params)
            except UniqueViolation:
                return None

            return cursor.fetchone()


def change_password(user_id, password):

    password_hash = generate_password(password)
    query = "UPDATE users SET password = %s WHERE id = %s"
    params = (password_hash, user_id)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

def check_credentials(email, password):

    query = "SELECT password FROM users WHERE email = %s"
    params = [email]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()

    if not result:
        return False

    password_hash = result['password'].encode('utf-8')
    password = password.encode('utf-8')

    return bcrypt.checkpw(password, password_hash)
