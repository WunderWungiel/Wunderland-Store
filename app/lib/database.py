import os
from datetime import datetime

from psycopg import connect, sql
from psycopg.rows import dict_row
from markdown import markdown
from flask import current_app

from . import config

uri = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}/{config['database']['name']}"
connection = connect(uri, row_factory=dict_row)

def format_results(results):

    formatted_results = {}

    for row in results:
        formatted_results[row['id']] = {
            'id': row['id'],
            'title': row['title'],
            'file': row['file'],
            'category': get_category(row['category']),
            'description': row['description'],
            'publisher': row['publisher'],
            'version': row['version'],
            'platform': get_platform(row['platform']) if row['platform'] is not None else None,
            'icon': row['icon'],
            'rating': get_rating(row['id']),
            'addon_message': row['addon_message'],
            'addon_file': row['addon_file'],
            'uid': row['uid'],
            'screenshots': [f"{row['screenshot_prefix']}{i}.jpg" for i in range(1, row['screenshot_count'] + 1)]
        }

    return formatted_results

def get_content(id=None, type_id=None, category_id=None, platforms=None):

    where_clauses = ["visible = TRUE"]
    params = []

    if platforms is not None:
        query = """
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id
                FROM platforms
                WHERE id = ANY(%s)

                UNION ALL

                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id
            )
            SELECT * FROM content
        """
        where_clauses.append("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)")
        params.append(platforms)

    else:
        query = "SELECT * FROM apps"

    if id is not None:
        where_clauses.append("id = %s")
        params.append(id)

    if category_id is not None:
        where_clauses.append("category = %s")
        params.append(category_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY id DESC"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return format_results(cursor.fetchall()) if id is not None else cursor.fetchone()

def get_rating(content_id):

    query = "SELECT COALESCE(ROUND(AVG(rating)), 0) as rating FROM rating WHERE content_id = %s"
    params = [content_id]

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return int(cursor.fetchone()['rating'])

def rate(rating, user_id, content_id):

    query = """
        INSERT INTO rating (content_id, rating, user_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (content_id, user_id)
        DO UPDATE SET rating = EXCLUDED.rating
    """
    params = (content_id, rating, user_id)

    with connection.cursor() as cursor:
        cursor.execute(query, params)

    connection.commit()

def get_categories(platform_id=None):

    if platform_id is not None:
        query = """
            SELECT DISTINCT category.* FROM categories AS category
            JOIN content ON category.id = content.category_id
            WHERE content.platform = %s
        """
        params = [platform_id]
    else:
        query = "SELECT * FROM categories"
        params = []

    query += " ORDER BY name"

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

    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall() if platform_id is not None else cursor.fetchone()

def get_category(category_id):

    query = "SELECT * FROM categories WHERE id=%s"
    params = [category_id]

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()

def search(search_query, platform_id=None):

    where_clauses = ["visible = TRUE"]
    params = []

    if platform_id is not None:
        query = """
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id
                FROM platforms
                WHERE id = %s

                UNION ALL

                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id
            )
            SELECT * FROM content
        """

        where_clauses.append("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)")
        params.append(platform_id)

    else:
        query = "SELECT * FROM {}"

    where_clauses.append("LOWER(title) LIKE %s")
    params.append(f"%{search_query.lower()}%")

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY title"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return format_results(cursor.fetchall())

def increment_counter(content_id):

    query = "UPDATE content SET visited_counter=visited_counter + 1 WHERE id=%s"
    params = [content_id]

    with connection.cursor() as cursor:
        cursor.execute(query, params)

    connection.commit()

def get_news(news_id=None):

    query = "SELECT * FROM news"
    where_clauses = []
    params = []

    if news_id is not None:
        where_clauses.append("id = %s")
        params.append(news_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY id DESC"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        results = cursor.fetchall()

    formatted_results = []

    for row in results:
        file_path = os.path.join(current_app.static_folder, "content", "news", row['file'])

        if not os.path.isfile(file_path):
            continue

        f = open(file_path, "r")
        markdown_content = f.read()
        html_content = markdown(markdown_content)
        f.close()

        file_timestamp = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(file_timestamp).strftime("%a, %d %b %Y %H:%M:%S GMT")

        formatted_results.append(
            {
                'id': row['id'],
                'title': row['title'],
                'content': html_content,
                'date': file_date
            }
        )

    if news_id is not None and results:
        return formatted_results[0]

    return formatted_results

def get_content_types():

    query = "SELECT * FROM content_types"

    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()

def get_content_type(name=None, prefix=None):

    query = "SELECT * FROM content_types"
    where_clauses = []
    params = []

    if name is not None:
        where_clauses.append("name = %s")
        params.append(name)

    if prefix is not None:
        where_clauses.append("prefix = %s")
        params.append(prefix)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()
