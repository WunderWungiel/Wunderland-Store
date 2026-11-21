import os
import secrets
import stat
from copy import deepcopy
from functools import lru_cache
from datetime import datetime, timezone, timedelta

import bcrypt
from markdown import markdown
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import CONTENT_DIR, DATABASE

# Each worker owns a pool; keep idle connections low and cap concurrent queries.
pool = ConnectionPool(min_size=1, max_size=4, kwargs={
    **DATABASE,
    # Without it, connecting to an unreachable host waits on the OS TCP timeout.
    "connect_timeout": 5,
    "row_factory": dict_row,
})

VALID_SORT_FIELDS = {
    "updated_at": {"column": "content.updated_at", "label": "Updated"},
    "created_at": {"column": "content.created_at", "label": "Created"},
    "id": {"column": "content.id", "label": "ID"},
    "title": {"column": "content.title", "label": "Title"},
    "rating": {"column": "rating", "label": "Rating"}
}


def _format_content(results):
    total = results[0]['total'] if results else 0

    for i, result in enumerate(results):
        result['category'] = {
            'id': result.pop('category_id'),
            'name': result.pop('category_name'),
            'type_id': result.pop('category_type_id'),
        }

        result['platforms'] = [
            {'id': platform[0], 'name': platform[1]}
            for platform in (result.pop('platforms') or [])
        ]

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


def get_items(content_ids):
    if not content_ids:
        return []
    content_ids = [int(content_id) for content_id in content_ids if content_id is not None]
    if not content_ids:
        return []
    results, _ = get_content(content_ids=content_ids)
    by_id = {row['id']: row for row in results}
    # Explicit ID lists retain their order and repeated IDs, as individual lookups did.
    return [deepcopy(by_id[content_id]) for content_id in content_ids if content_id in by_id]


def get_one_news(news_id):
    if news_id is None:
        return None
    results, _ = get_news(news_id=news_id)
    return results[0] if results else None


def get_content_type_by_id(type_id):
    return next((row for row in get_content_types() if row['id'] == type_id), None)


def get_content_type_by_name(name):
    return next((row for row in get_content_types() if row['name'] == name), None)


def get_content_type_by_prefix(prefix):
    return next((row for row in get_content_types() if row['prefix'] == prefix), None)


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


def prefix_in_use(prefix):
    query = "SELECT 1 FROM content WHERE screenshot_prefix = %s OR icon = %s LIMIT 1"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, [prefix, f"{prefix}.png"])
            return cursor.fetchone() is not None


def upload(title, category_id, publisher, version, icon, screenshot_prefix, screenshot_count, file=None, latest_url=None, description=None, addon_text=None, addon_file=None, uid=None, platforms=None):
    
    query = """
        INSERT INTO content (
            title, file, latest_url, category_id, description, publisher, 
            version, icon, screenshot_prefix, screenshot_count, 
            addon_text, addon_file, uid
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    params = (title, file, latest_url, category_id, description, publisher, version, icon, screenshot_prefix, screenshot_count, addon_text, addon_file, uid)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()

            if platforms:
                cursor.executemany(
                    "INSERT INTO content_platforms (content_id, platform_id) VALUES (%s, %s)",
                    [(result['id'], platform_id) for platform_id in platforms]
                )

    return result


def get_content(content_id=None, content_type_id=None, category_id=None, platforms=None, search=None, title=None, limit=None, offset=None, start=None, sort_by="updated_at", sort_order="DESC", exclude_content_id=None, random_order=False, content_ids=None, uid=None, updated_since=None):

    sort_fields = {key: value["column"] for key, value in VALID_SORT_FIELDS.items()}

    query = """
        SELECT
            content.*,
            category.name AS category_name,
            category.type_id AS category_type_id,
            content_platform_data.platforms,
            COALESCE(content_rating.rating, 0) AS rating,
            content_rating.rating_average,
            content_rating.rating_count,
            COUNT(*) OVER() AS total
        FROM content
        LEFT JOIN categories AS category ON content.category_id = category.id
        LEFT JOIN LATERAL (
            SELECT ARRAY_AGG(DISTINCT (platform.id, platform.name)) AS platforms
            FROM content_platforms
            JOIN platforms AS platform ON content_platforms.platform_id = platform.id
            WHERE content_platforms.content_id = content.id
        ) AS content_platform_data ON TRUE
        LEFT JOIN LATERAL (
            SELECT ROUND(AVG(ratings.rating)) AS rating,
                   AVG(ratings.rating) AS rating_average,
                   COUNT(*) AS rating_count
            FROM ratings
            WHERE ratings.content_id = content.id
        ) AS content_rating ON TRUE
    """

    where_clauses = ["content.visible = TRUE"]
    params = []

    if platforms is not None:
        where_clauses.append("""
            (EXISTS (
                SELECT 1 FROM content_platforms cp2
                WHERE cp2.content_id = content.id
                AND cp2.platform_id = ANY(%s)
            ) OR NOT EXISTS (
                SELECT 1 FROM content_platforms cp3
                WHERE cp3.content_id = content.id
            ))
        """)
        params.append(platforms)

    if content_id is not None:
        where_clauses.append("content.id = %s")
        params.append(content_id)

    if content_ids is not None:
        where_clauses.append("content.id = ANY(%s)")
        params.append(content_ids)

    if exclude_content_id is not None:
        where_clauses.append("content.id <> %s")
        params.append(exclude_content_id)

    if content_type_id is not None:
        where_clauses.append("category.type_id = %s")
        params.append(content_type_id)

    if category_id is not None:
        where_clauses.append("content.category_id = %s")
        params.append(category_id)

    if search is not None:
        where_clauses.append("content.title ILIKE %s")
        # PostgreSQL LIKE uses backslash to escape pattern metacharacters.
        search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{search}%")

    if title is not None:
        where_clauses.append("content.title = %s")
        params.append(title)

    if start is not None:
        where_clauses.append("content.id >= %s")
        params.append(start)

    if uid is not None:
        # UIDs are stored as 0x plus 8 hex digits, in either case.
        where_clauses.append("lower(content.uid) = lower(%s)")
        params.append(uid)

    if updated_since is not None:
        where_clauses.append("content.updated_at > %s")
        params.append(updated_since)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    sort_column = sort_fields.get(sort_by, "content.updated_at")
    sort_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
    if random_order:
        query += " ORDER BY random()"
    else:
        query += f" ORDER BY {sort_column} {sort_order}"
        if sort_column != "content.id":
            query += ", content.id DESC"

    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    if offset is not None:
        query += " OFFSET %s"
        params.append(offset)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return _format_content(cursor.fetchall())


def get_rating_distribution(content_id):
    """The number of ratings per star value (1-5) of a content item; stars nobody gave are left out."""
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rating, COUNT(*) AS count FROM ratings WHERE content_id = %s GROUP BY rating",
                (content_id,)
            )
            return {row['rating']: row['count'] for row in cursor.fetchall()}


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
            cursor.execute("""
                INSERT INTO content_stats (content_id, visited) VALUES (%s, 1)
                ON CONFLICT (content_id) DO UPDATE SET visited = content_stats.visited + 1
            """, (content_id,))


def get_categories(category_id=None, content_type_id=None, platform_id=None, only_with_content=False,
                   with_counts=False):
    """Categories ordered by type and name, each with its content_type.

    Without with_counts, a platform_id lists only categories with visible content for
    that platform, as only_with_content does for any platform. With with_counts, each
    row gets content_count (visible items, for platform_id if given), and only
    only_with_content leaves out the empty ones.
    """
    where_clauses = []
    params = []

    # Visible content of the category, on platform_id if given (untagged content runs anywhere).
    content_clause = """
        content.category_id = category.id
        AND content.visible = TRUE
    """
    content_params = []
    if platform_id is not None:
        content_clause += """
            AND (EXISTS (
                SELECT 1 FROM content_platforms cp2
                WHERE cp2.content_id = content.id
                AND cp2.platform_id = %s
            ) OR NOT EXISTS (
                SELECT 1 FROM content_platforms cp3
                WHERE cp3.content_id = content.id
            ))
        """
        content_params.append(platform_id)

    query = """
        SELECT category.*,
               jsonb_build_object(
                   'id', content_types.id,
                   'name', content_types.name,
                   'prefix', content_types.prefix,
                   'show_categories', content_types.show_categories,
                   'show_icons', content_types.show_icons
               ) AS content_type
    """

    if with_counts:
        query += f"""
               , category_counts.content_count
            FROM categories AS category
            JOIN content_types ON category.type_id = content_types.id
            CROSS JOIN LATERAL (
                SELECT COUNT(*) AS content_count FROM content WHERE {content_clause}
            ) AS category_counts
        """
        params.extend(content_params)
        if only_with_content:
            where_clauses.append("category_counts.content_count > 0")
    else:
        query += """
            FROM categories AS category
            JOIN content_types ON category.type_id = content_types.id
        """
        if only_with_content or platform_id is not None:
            where_clauses.append(f"EXISTS (SELECT 1 FROM content WHERE {content_clause})")
            params.extend(content_params)

    if category_id is not None:
        where_clauses.append("category.id = %s")
        params.append(category_id)

    if content_type_id is not None:
        where_clauses.append("category.type_id = %s")
        params.append(content_type_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY category.type_id ASC, category.name ASC"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


@lru_cache(maxsize=2)
def _get_reference_rows(table):
    # These tables change only during maintenance; restart workers to refresh.
    queries = {
        'platforms': "SELECT * FROM platforms ORDER BY name",
        'content_types': "SELECT * FROM content_types ORDER BY name ASC",
    }
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(queries[table])
            return cursor.fetchall()


def get_platforms(platform_id=None):
    rows = _get_reference_rows('platforms')
    if platform_id is not None:
        rows = [row for row in rows if row['id'] == platform_id]
    return deepcopy(rows)


def get_content_types():
    return deepcopy(_get_reference_rows('content_types'))


@lru_cache(maxsize=128)
def _render_news(file_path, mtime_ns):
    # The timestamp is part of the cache key, so edits invalidate rendered HTML.
    with open(file_path, "r") as source:
        return markdown(source.read())


def get_news(news_id=None, limit=None, offset=None):
    """News, newest first, as (rows, total).

    Rows whose Markdown file is missing are left out, but total still counts them, so a
    page can come back short.
    """
    query = "SELECT *, COUNT(*) OVER() AS total FROM news"
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

    total = rows[0]['total'] if rows else 0
    results = []

    for row in rows:
        file_path = os.path.join(CONTENT_DIR, "news", row['file'])

        try:
            file_stat = os.stat(file_path)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(file_stat.st_mode):
            continue

        html_content = _render_news(file_path, file_stat.st_mtime_ns)

        results.append({
            'id': row['id'],
            'title': row['title'],
            'content': html_content,
            'created_at': row['created_at'],
            # RFC 1123, for the RSS feed and the templates.
            'date': row['created_at'].astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        })

    return results, total


def get_sitemap_entries():
    """IDs and timestamps for the sitemap, without get_content's aggregation.

    Returns (items, news): visible items with updated_at and whether they have
    screenshots, and news rows with created_at. News whose file is missing is left
    out, as get_news does, since its page would be a 404.
    """
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, updated_at, screenshot_count > 0 AS has_screenshots
                FROM content
                WHERE visible = TRUE
                ORDER BY id
            """)
            items = cursor.fetchall()
            cursor.execute("SELECT id, file, created_at FROM news ORDER BY id")
            news = cursor.fetchall()

    news = [row for row in news if os.path.isfile(os.path.join(CONTENT_DIR, "news", row['file']))]
    return items, news


def generate_password(password):
    password = password.encode('utf-8')
    salt = bcrypt.gensalt()

    password_hash = bcrypt.hashpw(password, salt)
    return password_hash.decode('utf-8')


def get_session(token):

    query = "SELECT users.id, users.username, users.email, users.role, sessions.token, sessions.user_id, sessions.expires_at FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = %s AND sessions.expires_at > NOW()"
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


def create_session(user_id):

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    query = "INSERT INTO sessions (user_id, token, expires_at) VALUES (%s, %s, %s)"
    params = [user_id, token, expires_at]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

    return token


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


def delete_user(user_id):

    query = "DELETE FROM users WHERE id = %s"
    params = [user_id]

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)


def change_password(user_id, password, current_token=None):

    password_hash = generate_password(password)
    query = "UPDATE users SET password = %s WHERE id = %s"
    params = (password_hash, user_id)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            cursor.execute(
                "DELETE FROM sessions WHERE user_id = %s AND token IS DISTINCT FROM %s",
                (user_id, current_token)
            )


def check_credentials(email, password):

    if len(password.encode('utf-8')) > 72:
        return None

    user = get_user_by_email(email)

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return None

    return user
