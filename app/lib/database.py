import os
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from markdown import markdown
from flask import current_app

from . import config

uri = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}:{config['database']['port']}/{config['database']['name']}"
pool = ConnectionPool(uri, kwargs={"row_factory": dict_row})

CONTENT_SELECT = """
    SELECT
        content.*,
        category.name AS category_name,
        category.type_id AS category_type_id,
        platform.name AS platform_name,
        COALESCE(ROUND(AVG(rating.rating)), 0) AS rating,
        COUNT(*) OVER() AS total
    FROM content
    LEFT JOIN categories AS category ON content.category_id = category.id
    LEFT JOIN platforms AS platform ON content.platform = platform.id
    LEFT JOIN rating ON content.id = rating.content_id
"""

CONTENT_SELECT_WITH_PLATFORM_TREE = """
    WITH RECURSIVE platform_tree AS (
        SELECT id, parent_id FROM platforms WHERE id = ANY(%s)
        UNION ALL
        SELECT parent.id, parent.parent_id
        FROM platforms parent
        JOIN platform_tree ON parent.id = platform_tree.parent_id
    )
""" + CONTENT_SELECT

CONTENT_GROUP_BY = " GROUP BY content.id, category.name, category.type_id, platform.name"


def _format_content(results):

    total = results[0]['total'] if results else 0

    for i, result in enumerate(results):

        result['category'] = {
            'id': result['category_id'],
            'name': result.pop('category_name'),
            'type_id': result.pop('category_type_id'),
        }

        result['platform'] = {
            'id': result['platform'],
            'name': result.pop('platform_name'),
        } if result['platform'] is not None else None

        result['screenshots'] = [
            f"{result['screenshot_prefix']}{n}.jpg"
            for n in range(1, result['screenshot_count'] + 1)
        ]

        result['content_type'] = get_content_type(type_id=result['category']['type_id'])

        result['rating'] = int(result['rating'])

        result.pop('total')

        results[i] = result

    return results, total


def get_one_content(content_id):
    results, _ = get_content(content_id=content_id)
    return results[0] if results else None


def get_one_news(news_id):
    results, _ = get_news(news_id=news_id)
    return results[0] if results else None


def get_content_type(type_id=None, name=None, prefix=None):
    results = get_content_types(type_id=type_id, name=name, prefix=prefix)
    return results[0] if results else None


def get_category(category_id):
    results = get_categories(category_id=category_id)
    return results[0] if results else None


def get_platform(platform_id):
    results = get_platforms(platform_id=platform_id)
    return results[0] if results else None


def get_content(content_id=None, content_type_id=None, category_id=None, platforms=None, limit=None, offset=None):

    where_clauses = ["content.visible = TRUE"]
    params = []

    if platforms is not None:
        query = CONTENT_SELECT_WITH_PLATFORM_TREE
        where_clauses.append(
            "(content.platform IN (SELECT id FROM platform_tree) OR content.platform IS NULL)")
        params.append(platforms)
    else:
        query = CONTENT_SELECT

    if content_id is not None:
        where_clauses.append("content.id = %s")
        params.append(content_id)

    if content_type_id is not None:
        where_clauses.append("category.type_id = %s")
        params.append(content_type_id)

    if category_id is not None:
        where_clauses.append("content.category_id = %s")
        params.append(category_id)

    where = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query += where
    query += CONTENT_GROUP_BY
    query += " ORDER BY content.title"

    if None not in (limit, offset):
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return _format_content(cursor.fetchall())


def search(search_query, platform_id=None, limit=None, offset=None):
    where_clauses = ["content.visible = TRUE", "LOWER(content.title) LIKE %s"]
    params = [f"%{search_query.lower()}%"]

    if platform_id is not None:
        query = CONTENT_SELECT_WITH_PLATFORM_TREE.replace("ANY(%s)", "%s")
        where_clauses.append(
            "(content.platform IN (SELECT id FROM platform_tree) OR content.platform IS NULL)")
        params.insert(0, platform_id)
    else:
        query = CONTENT_SELECT

    where = " WHERE " + " AND ".join(where_clauses) if where_clauses else None

    query += where
    query += CONTENT_GROUP_BY
    query += " ORDER BY content.id DESC"

    if None not in (limit, offset):
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return _format_content(cursor.fetchall())


def get_legacy_content_id(old_id, content_type_id):

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT new_id FROM content_legacy WHERE old_id = %s AND type_id = %s",
                [old_id, content_type_id]
            )
            result = cursor.fetchone()
            return result['new_id'] if result else None


def rate(rating, content_id, user_id):

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO rating (content_id, rating, user_id) VALUES (%s, %s, %s)
                ON CONFLICT (content_id, user_id) DO UPDATE SET rating = EXCLUDED.rating
            """, [content_id, rating, user_id])


def increment_counter(content_id):

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE content SET counter = counter + 1 WHERE id = %s",
                [content_id]
            )


def get_categories(category_id=None, content_type_id=None, platform_id=None):
    where_clauses = []
    params = []

    if platform_id is not None:
        query = """
            SELECT DISTINCT category.* FROM categories AS category
            JOIN content ON category.id = content.category_id
        """
        where_clauses.append("content.platform = %s")
        params.append(platform_id)
    else:
        query = "SELECT * FROM categories"

    if category_id is not None:
        where_clauses.append("category.id = %s")
        params.append(category_id)

    if content_type_id is not None:
        column = "category.type_id" if platform_id is not None else "type_id"
        where_clauses.append(f"{column} = %s")
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
    params = []

    if platform_id is not None:
        query += " WHERE id = %s"
        params.append(platform_id)

    query += " ORDER BY name"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def get_content_types(type_id=None, name=None, prefix=None):
    where_clauses = []
    params = []

    if type_id is not None:
        where_clauses.append("id = %s")
        params.append(type_id)

    if name is not None:
        where_clauses.append("name = %s")
        params.append(name)

    if prefix is not None:
        where_clauses.append("prefix = %s")
        params.append(prefix)

    query = "SELECT * FROM content_types"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def get_news(news_id=None, limit=None, offset=None):
    query = "SELECT * FROM news"
    params = []

    if news_id is not None:
        query += " WHERE id = %s"
        params.append(news_id)

    query += " ORDER BY id DESC"

    if limit is not None and offset is not None:
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    results = []

    for row in rows:
        file_path = os.path.join(
            current_app.static_folder, "content", "news", row['file'])

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
