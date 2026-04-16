import os

from flask import request, current_app

from ..database import pool, get_content_type_by_id
from .. import config

def generate_content(content_type_id, content_name):

    content = ""

    where_clauses = ["content.visible = true"]
    params = []

    query = """
        SELECT content.*
        FROM content
        JOIN categories ON content.category_id = categories.id
    """

    if config['platforms']['qtstore']:
        query = """
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id FROM platforms WHERE id = ANY(%s)
                UNION ALL
                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree ON parent.id = platform_tree.parent_id
            )
        """ + query
        where_clauses.append("(platform_id IN (SELECT id FROM platform_tree) OR platform_id IS NULL)")
        params.append(config['platforms']['qtstore'])

    where_clauses.append("categories.type_id = %s")
    params.append(content_type_id)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY content.id DESC"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()

    for row in results:

        path = os.path.join(current_app.static_folder, "content", "files", row['file'])

        try:
            timestamp = int(os.path.getmtime(path))
        except FileNotFoundError:
            timestamp = 1672531200

        name, extension = os.path.splitext(row['file'])

        content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[descr.txt]\n"
        if extension in (".sis", ".sisx"):
            content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[file.sis]\n"
        else:
            content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[file{extension}]\n"
        content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[preview.png]\n"

    return content

def index():

    content = generate_content("apps", "Apps")
    content += generate_content("games", "Games")
    content += generate_content("themes", "Themes")

    return content

def get_content(name, content_type_id):

    where_clauses = ["content.visible = true"]
    params = []

    query = """
        SELECT content.*
        FROM content
        JOIN categories ON content.category_id = categories.id
    """

    if config['platforms']['qtstore']:
        query = """
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id FROM platforms WHERE id = ANY(%s)
                UNION ALL
                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree ON parent.id = platform_tree.parent_id
            )
        """ + query
        where_clauses.append("(platform_id IN (SELECT id FROM platform_tree) OR platform_id IS NULL)")
        params.append(config['platforms']['qtstore'])

    where_clauses.append("categories.type_id = %s")
    params.append(content_type_id)

    where_clauses.append("content.title LIKE %s")
    params.append(name)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " LIMIT 1"

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()

    if result:
        result['screenshots'] = [f"{result['screenshot_prefix']}{i}.jpg" for i in range(1, result['screenshot_count'] + 1)]
        result['description'] = result['description'].replace("\n", "<br>") if result['description'] else None
        result['addon_text'] = result['addon_text'].replace("\n", "<br>") if result['addon_text'] else None
        return result
    else:
        return None
