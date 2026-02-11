import bcrypt
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from .. import connection

def _generate_password(user_password):
    user_password = user_password.encode('utf-8')
    salt = bcrypt.gensalt()

    hashed_password = bcrypt.hashpw(user_password, salt)
    return hashed_password.decode('utf-8')


def get_user(id=None, username=None, email=None):

    query = sql.SQL("SELECT * FROM users")
    where_clauses = [sql.SQL("active = true")]
    params = []

    if email is not None:
        where_clauses.append(sql.SQL("email = %s"))
        params.append(email)
    if username is not None:
        where_clauses.append(sql.SQL("username = %s"))
        params.append(username)
    if id is not None:
        where_clauses.append(sql.SQL("id = %s"))
        params.append(id)

    if where_clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()

    return result

def confirm_user(email):

    query = sql.SQL("UPDATE users SET confirmed=true WHERE email=%s")
    params = (email,)

    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    cursor.close()

def email_exists(email):

    query = sql.SQL("SELECT * FROM users WHERE email=%s")
    params = (email,)

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()
    
    return True if result else False

def username_exists(username):

    query = sql.SQL("SELECT * FROM users WHERE username=%s")
    params = (username,)

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()
    
    return True if result else False

def register(email, user_password, username):

    hashed_password = _generate_password(user_password)
    query = sql.SQL("INSERT INTO users (email, password, username, confirmed) VALUES (%s, %s, %s, false)")
    params = (email, hashed_password, username)

    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    cursor.close()

def change_password(id, new_password):

    hashed_password = _generate_password(new_password)
    query = sql.SQL("UPDATE users SET password=%s WHERE id=%s")
    params = (hashed_password, id)

    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    cursor.close()

def check_credentials(email, user_password):
    if not email_exists(email):
        return False

    query = sql.SQL("SELECT password FROM users WHERE email=%s AND active=true")
    params = (email,)

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    
    result = cursor.fetchone()
    cursor.close()

    hashed_password = result["password"].encode('utf-8')
    user_password = user_password.encode('utf-8')

    return bcrypt.checkpw(user_password, hashed_password)
