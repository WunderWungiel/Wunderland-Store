import os
from datetime import datetime

from psycopg import connect, sql
from psycopg.rows import dict_row
from markdown import markdown
from flask import current_app

from . import config

uri = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}/{config['database']['name']}"
connection = connect(uri, row_factory=dict_row)

def format_results(results, content_type_name):

    formatted_results = {}

    for row in results:
        formatted_results[row['id']] = {
            "id": row['id'],
            "title": row['title'],
            "file": row['file'],
            "category": get_category(row['category'], content_type_name),
            "description": row['description'],
            "publisher": row['publisher'],
            "version": row['version'],
            "platform": get_platform(row['platform']) if row['platform'] is not None else None,
            "image1": row['image1'],
            "image2": row['image2'],
            "image3": row['image3'],
            "image4": row['image4'],
            "img": os.path.join(content_type_name, row['img']),
            "content_type": get_content_type(content_type_name),
            "rating": get_rating(row['id'], content_type_name),
            "addon_message": row['addon_message'],
            "addon_file": row['addon_file'],
            "uid": row['uid'],
            "screenshots": [image for image in (
                row['image1'],
                row['image2'],
                row['image3'],
                row['image4']
            ) if image]
        }

    return formatted_results

def get_content(id=None, category_id=None, content_type_name=None, platform_id=None):

    where_clauses = [sql.SQL("visible = TRUE")]
    params = []

    if platform_id is not None:
        query = sql.SQL("""
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id
                FROM platforms
                WHERE id = %s

                UNION ALL

                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id    
            )
            SELECT * FROM {}
        """).format(sql.Identifier(content_type_name))

        where_clauses.append(sql.SQL("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)"))
        params.append(platform_id)

    else:
        query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(content_type_name))

    if id is not None:
        where_clauses.append(sql.SQL("id = %s"))
        params.append(id)
    if category_id is not None:
        where_clauses.append(sql.SQL("category = %s"))
        params.append(category_id)

    if where_clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)

    query += sql.SQL(" ORDER BY id DESC")

    cursor = connection.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()

    if not results:
        return None

    results = format_results(results, content_type_name)

    if id is not None:
        return results.get(id)
    else:
        return results

def get_rating(content_id, content_type_name):
    
    table = f"{content_type_name}_rating"
    query = sql.SQL("SELECT COALESCE(ROUND(AVG(rating)), 0) as rating FROM {} WHERE content_id=%s").format(sql.Identifier(table))

    cursor = connection.cursor()
    cursor.execute(query, (content_id,))
    result = cursor.fetchone()
    cursor.close()

    return int(result['rating'])

def rate(rating, user_id, content_id, content_type_name):

    table = f"{content_type_name}_rating"
    query = sql.SQL("""
        INSERT INTO {} (content_id, user_id, rating)
        VALUES (%s, %s, %s)
        ON CONFLICT (content_id, user_id)
        DO UPDATE SET rating = EXCLUDED.rating
    """).format(sql.Identifier(table))
    params = (content_id, user_id, rating)

    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    cursor.close()

def get_categories(content_type_name):

    table = f"{content_type_name}_categories"
    query = sql.SQL("SELECT * FROM {} ORDER by name").format(sql.Identifier(table))

    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return results

def get_platforms():

    query = sql.SQL("SELECT * FROM platforms ORDER by name")

    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return results

def get_platform(platform_id):
    
    query = sql.SQL("SELECT * FROM platforms WHERE id=%s")
    params = (platform_id,)

    cursor = connection.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()

    return result

def get_category(category_id, content_type_name):
    
    table = f"{content_type_name}_categories"
    query = sql.SQL("SELECT * FROM {} WHERE id=%s").format(sql.Identifier(table))
    params = (category_id,)

    cursor = connection.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()

    return result

def search(search_query, databases=None, platform_id=None):

    if not databases:
        databases = ("apps", "games", "themes")

    results = {}

    for database in databases:

        where_clauses = [sql.SQL("visible = TRUE")]
        params = []

        if platform_id is not None:
            query = sql.SQL("""
                WITH RECURSIVE platform_tree AS (
                    SELECT id, parent_id
                    FROM platforms
                    WHERE id = %s

                    UNION ALL

                    SELECT parent.id, parent.parent_id
                    FROM platforms parent
                    JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id    
                )
                SELECT * FROM {}
            """).format(sql.Identifier(database))

            where_clauses.append(sql.SQL("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)"))
            params.append(platform_id)

        else:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(database))

        where_clauses.append(sql.SQL("LOWER(title) LIKE %s"))
        params.append(f"%{search_query.lower()}%")

        if where_clauses:
            query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)

        query += sql.SQL(" ORDER BY title")
        
        cursor = connection.cursor()
        cursor.execute(query, params)
        database_results = cursor.fetchall()
        cursor.close()

        results = results | format_results(database_results, database)

    return results

def increment_counter(id, content_type_name):

    query = sql.SQL("UPDATE {} SET visited_counter=visited_counter + 1 WHERE id=%s").format(sql.Identifier(content_type_name))
    params = (id,)

    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    cursor.close()

def get_news(news_id=None):
    
    cursor = connection.cursor()
    if news_id is None:
        cursor.execute(sql.SQL("SELECT * FROM news ORDER BY id DESC"))
    else:
        cursor.execute(sql.SQL("SELECT * FROM news WHERE id=%s"), (news_id,))
    results = cursor.fetchall()
    cursor.close()
    if not results:
        return None

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

    return formatted_results

def get_content_types():
    return config['content_types']

def get_content_type(name=None, prefix=None):
    for content_type in config['content_types']:
        if (name is not None and content_type['name'] != name) or (prefix is not None and content_type['prefix'] != prefix):
            continue
        return content_type
