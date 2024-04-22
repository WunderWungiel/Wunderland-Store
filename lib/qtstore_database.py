"""QtStore database backend"""

import os

from flask import request, current_app
import psycopg2
import psycopg2.extras

from . import conn

def content_generator(database, content_name, host):
    content = ""

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(f"SELECT title, file FROM {database} WHERE (platform='s60' OR platform IS NULL) ORDER BY id DESC")
    results = cursor.fetchall()
    cursor.close()

    for row in results:

        path = os.path.join(current_app.root_path, "static", "files", row['file'])

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

def qtstore_generator():

    host = request.host
    content = ""

    content += content_generator("apps", "Apps", host)
    content += content_generator("games", "Games", host)
    content += content_generator("themes", "Themes", host)

    return content

def qtstore_content(name, content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(f"SELECT title, description, file, img, addon_message, addon_file, image1, image2, image3, image4 FROM {content_type} WHERE title LIKE %s AND (platform='s60' OR platform IS NULL) LIMIT 1", (name,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        result["screenshots"] = [image for image in (result['image1'], result['image2'], result['image3'], result['image4']) if image]
        result['description'] = result['description'].replace("\n", "<br>") if result['description'] else None
        result['addon_message'] = result['addon_message'].replace("\n", "<br>") if result['addon_message'] else None
        return result
    else:
        return None