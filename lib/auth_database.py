import bcrypt
import psycopg2.extras

from .database import conn, build_query

def _generate_password(user_password):
    user_password = user_password.encode('utf-8')
    salt = bcrypt.gensalt()

    hashed_password = bcrypt.hashpw(user_password, salt)
    return hashed_password.decode('utf-8')

def get_user(id=None, username=None, email=None):
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_query = "SELECT * FROM users"
    conditions = {"active": True}

    if email:
        conditions["email"] = email
    elif username:
        conditions["username"] = username
    elif id:
        conditions["id"] = int(id)
    else:
        raise TypeError

    query, query_params = build_query(base_query, conditions)

    cursor.execute(query, query_params)
    
    result = cursor.fetchone()
    cursor.close()

    return result if result else None

def get_user_id(username=None, email=None):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_query = "SELECT id FROM users"
    conditions = {}
    if username:
        conditions["username"] = username
    elif email:
        conditions["email"] = email
    else:
        raise TypeError
    
    query, query_params = build_query(base_query, conditions)

    cursor.execute(query, query_params)
    result = cursor.fetchone()
    cursor.close()

    return result['id'] if result else None

def get_user_email(id=None, username=None):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_query = "SELECT email FROM users"
    conditions = {}
    if id:
        conditions["id"] = id
    elif username:
        conditions["username"] = username
    else:
        raise TypeError

    query, query_params = build_query(base_query, conditions)

    cursor.execute(query, query_params)
    result = cursor.fetchone()
    cursor.close()

    return result['email'] if result else None

def confirm_user(email):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET confirmed=true WHERE email=%s", (email,))
    conn.commit()

def email_exists(email):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))

    result = cursor.fetchone()
    cursor.close()
    
    return True if result else False

def username_exists(username):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))

    result = cursor.fetchone()
    cursor.close()
    
    return True if result else False

def register(email, user_password, username):

    hashed_password = _generate_password(user_password)

    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (email, password, username, confirmed) VALUES (%s, %s, %s, false)", (email, hashed_password, username))
    cursor.close()

    conn.commit()

def change_password(id, new_password):

    hashed_password = _generate_password(new_password)

    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, id))

    conn.commit()


def check_credentials(email, user_password):
    if not email_exists(email):
        return False

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT password FROM users WHERE email=%s AND active=true", (email,))
    
    result = cursor.fetchone()
    cursor.close()

    hashed_password = result["password"].encode('utf-8')
    user_password = user_password.encode('utf-8')

    return bcrypt.checkpw(user_password, hashed_password)