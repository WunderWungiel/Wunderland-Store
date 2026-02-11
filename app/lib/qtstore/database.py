import os

from flask import request, current_app
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from .. import connection

def generate_content(database, content_name, host):

    platforms = ("s60", "s60v3")

    content = ""

    query = sql.SQL("SELECT title, file FROM {}").format(sql.Identifier(database))
    where_clauses = []
    params = []

    where_clauses.append(sql.SQL("(platform = ANY(%s) OR platform IS NULL)"))
    params.append(platforms)

    if where_clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)
    query += sql.SQL(" ORDER BY id DESC")

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()

    for row in results:

        path = os.path.join(current_app.root_path, "static", "content", "files", row['file'])

        try:
            timestamp = int(os.path.getmtime(path))
        except FileNotFoundError:
            timestamp = 1672531200

        name, ext = os.path.splitext(row['file'])

        content += f"http://{host}/StoreData/{content_name}/{row['title']}/{timestamp}[descr.txt]\n"
        if ext in (".sis", ".sisx"):
            content += f"http://{host}/StoreData/{content_name}/{row['title']}/{timestamp}[file.sis]\n"
        else:
            content += f"http://{host}/StoreData/{content_name}/{row['title']}/{timestamp}[file{ext}]\n"
        content += f"http://{host}/StoreData/{content_name}/{row['title']}/{timestamp}[preview.png]\n"

    return content

def index():

    content = generate_content("apps", "Apps", request.host)
    content += generate_content("games", "Games", request.host)
    content += generate_content("themes", "Themes", request.host)

    return content

def get_content(name, content_type):

    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(content_type))
    where_clauses = [sql.SQL("VISIBLE = true"), sql.SQL("title LIKE %s")]
    params = [name]

    where_clauses.append(sql.SQL("(platform = ANY(%s) OR platform IS NULL)"))
    params.append(["s60", "s60v3"])

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
