import os
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
from markdown import markdown
from flask import current_app
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

uri = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}:{config['database']['port']}/{config['database']['name']}"
pool = ConnectionPool(uri, kwargs={"row_factory": dict_row})


def _format_content(results):

    total = results[0]['total'] if results else 0

    for i, result in enumerate(results):

        result['category'] = {
            'id': result['category_id'],
            'name': result.pop('category_name'),
            'type_id': result.pop('category_type_id'),
        }

        result['platform'] = {
            'id': result['platform_id'],
            'name': result.pop('platform_name'),
        } if result['platform_id'] is not None else None

        result['screenshots'] = [
            f"{result['screenshot_prefix']}{n}.jpg"
            for n in range(1, result['screenshot_count'] + 1)
        ]

        result['content_type'] = get_content_type_by_id(
            result['category']['type_id']
        )

        result['rating'] = int(result['rating'])

        result.pop('total')

        results[i] = result

    return results, total


def get_item(content_id):
    if content_id is None:
        return None
    results, _ = get_content(content_id=content_id)
    return results[0] if results else None


def get_one_news(news_id):
    if news_id is None:
        return None
    results, _ = get_news(news_id=news_id)
    return results[0] if results else None


def get_content_type_by_id(type_id):
    query = "SELECT * FROM content_types WHERE id = %s"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (type_id,))
            return cursor.fetchone()


def get_content_type_by_name(name):
    query = "SELECT * FROM content_types WHERE name = %s"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (name,))
            return cursor.fetchone()


def get_content_type_by_prefix(prefix):
    query = "SELECT * FROM content_types WHERE prefix = %s"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (prefix,))
            return cursor.fetchone()


def get_category(category_id):
    if category_id is None:
        return None
    results = get_categories(category_id=category_id)
    return results[0] if results else None


def get_platform(platform_id):
    if platform_id is None:
        return None
    results = get_platforms(platform_id=platform_id)
    return results[0] if results else None


def get_content(content_id=None, content_type_id=None, category_id=None, platforms=None, search=None, limit=None, offset=None, start=None):

    PLATFORM_TREE_CTE = """
        WITH RECURSIVE platform_tree AS (
            SELECT id, parent_id FROM platforms WHERE id = ANY(%s)
            UNION ALL
            SELECT parent.id, parent.parent_id
            FROM platforms parent
            JOIN platform_tree ON parent.id = platform_tree.parent_id
        )
    """

    query = """
        SELECT
            content.*,
            category.name AS category_name,
            category.type_id AS category_type_id,
            platform.name AS platform_name,
            COALESCE(ROUND(AVG(ratings.rating)), 0) AS rating,
            COUNT(*) OVER() AS total
        FROM content
        LEFT JOIN categories AS category ON content.category_id = category.id
        LEFT JOIN platforms AS platform ON content.platform_id = platform.id
        LEFT JOIN ratings ON content.id = ratings.content_id
    """

    where_clauses = ["content.visible = TRUE"]
    params = []

    if platforms is not None:
        query = PLATFORM_TREE_CTE + query
        where_clauses.append("(content.platform_id IN (SELECT id FROM platform_tree) OR content.platform_id IS NULL)")
        params.append(platforms)

    if content_id is not None:
        where_clauses.append("content.id = %s")
        params.append(content_id)

    if content_type_id is not None:
        where_clauses.append("category.type_id = %s")
        params.append(content_type_id)

    if category_id is not None:
        where_clauses.append("content.category_id = %s")
        params.append(category_id)

    if search is not None:
        where_clauses.append("content.title ILIKE %s")
        params.append(f"%{search}%")

    if start is not None:
        where_clauses.append("content.id >= %s")
        params.append(start)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " GROUP BY content.id, category.name, category.type_id, platform.name"
    query += " ORDER BY content.updated_at DESC, content.id DESC"

    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    if offset is not None:
        query += " OFFSET %s"
        params.append(offset)

    print(query, params)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return _format_content(cursor.fetchall())


def get_legacy_content_id(old_id, content_type_id):

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT new_id FROM content_legacy WHERE old_id = %s AND type_id = %s",
                (old_id, content_type_id)
            )
            result = cursor.fetchone()
            return result['new_id'] if result else None


def rate(rating, content_id, user_id):

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO ratings (content_id, rating, user_id) VALUES (%s, %s, %s)
                ON CONFLICT (content_id, user_id) DO UPDATE SET rating = EXCLUDED.rating
            """, (content_id, rating, user_id))


def increment_counter(content_id):

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content SET counter = counter + 1 WHERE id = %s",
                (content_id,)
            )


def get_categories(category_id=None, content_type_id=None, platform_id=None):
    where_clauses = []
    params = []

    if platform_id is not None:
        query = """
            SELECT DISTINCT category.* FROM categories AS category
            JOIN content ON category.id = content.category_id
        """
        where_clauses.append("content.platform_id = %s")
        params.append(platform_id)
    else:
        query = "SELECT * FROM categories AS category"

    if category_id is not None:
        where_clauses.append("category.id = %s")
        params.append(category_id)

    if content_type_id is not None:
        where_clauses.append("category.type_id = %s")
        params.append(content_type_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY name"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def get_platforms(platform_id=None):

    query = "SELECT * FROM platforms"
    where_clauses = []
    params = []

    if platform_id is not None:
        where_clauses.append("id = %s")
        params.append(platform_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY name"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def get_content_types():

    query = "SELECT * FROM content_types ORDER BY name ASC"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()


def get_news(news_id=None, limit=None, offset=None):
    query = "SELECT * FROM news"
    where_clauses = []
    params = []

    if news_id is not None:
        where_clauses.append("id = %s")
        params.append(news_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY news.created_at DESC, news.id DESC"

    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    if offset is not None:
        query += " OFFSET %s"
        params.append(offset)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    results = []

    for row in rows:
        file_path = os.path.join(current_app.static_folder, "content", "news", row['file'])

        if not os.path.isfile(file_path):
            continue

        with open(file_path, "r") as f:
            html_content = markdown(f.read())

        results.append({
            'id': row['id'],
            'title': row['title'],
            'content': html_content,
            'date': datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).strftime("%a, %d %b %Y %H:%M:%S GMT")
        })

    return results, len(results)

def generate_password(password):
    password = password.encode('utf-8')
    salt = bcrypt.gensalt()

    password_hash = bcrypt.hashpw(password, salt)
    return password_hash.decode('utf-8')


def get_session(token):

    query = "SELECT sessions.*, users.id, users.username, users.email, users.role FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = %s AND sessions.expires_at > NOW()"
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


def confirm_user(user_id):

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
