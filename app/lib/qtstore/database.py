import os

from flask import request, current_app
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from .. import connection
from .. import config

def generate_content(database, content_name):

    content = ""

    where_clauses = [sql.SQL("visible = true")]
    params = []

    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(database))

    if config['platforms']['qtstore']:
        query = sql.SQL("""
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id
                FROM platforms
                WHERE id = ANY(%s)

                UNION ALL

                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id    
            )
        """) + query
        where_clauses.append(sql.SQL("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)"))
        params.append(config['platforms']['qtstore'])

    if where_clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)
    
    query += sql.SQL(" ORDER BY id DESC")

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()

    for row in results:

        path = os.path.join(current_app.static_folder, "content", "files", row['file'])

        try:
            timestamp = int(os.path.getmtime(path))
        except FileNotFoundError:
            timestamp = 1672531200

        name, ext = os.path.splitext(row['file'])

        content += f"http://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[descr.txt]\n"
        if ext in (".sis", ".sisx"):
            content += f"http://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[file.sis]\n"
        else:
            content += f"http://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[file{ext}]\n"
        content += f"http://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[preview.png]\n"

    return content

def index():

    content = generate_content("apps", "Apps")
    content += generate_content("games", "Games")
    content += generate_content("themes", "Themes")

    return content

def get_content(name, content_type):

    where_clauses = [sql.SQL("visible = true")]
    params = []

    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(content_type))

    if config['platforms']['qtstore']:
        query = sql.SQL("""
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id
                FROM platforms
                WHERE id = ANY(%s)

                UNION ALL

                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id    
            )
        """) + query
        where_clauses.append(sql.SQL("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)"))
        params.append(config['platforms']['qtstore'])

    where_clauses.append(sql.SQL("title LIKE %s"))
    params.append(name)

    if where_clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)
    query += sql.SQL(" LIMIT 1")

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()

    if result:
        result["screenshots"] = [image for image in (result['image1'], result['image2'], result['image3'], result['image4']) if image]
        result['description'] = result['description'].replace("\n", "<br>") if result['description'] else None
        result['addon_message'] = result['addon_message'].replace("\n", "<br>") if result['addon_message'] else None
        return result
    else:
        return None
