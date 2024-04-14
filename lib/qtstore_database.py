"""QtStore database backend"""

from flask import request
import psycopg2
import psycopg2.extras

from . import conn

def qtstore_generator():

    host = request.host
    content = ""

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT title, file FROM apps")
    results = cursor.fetchall()
    cursor.close()

    for row in results:
        # date = int(round(os.stat(os.path.join(current_app.root_path, 'static', 'files', row['file'])).st_size / (1024 * 1024), 2))
        date = 1708635534
        content += f"http://{host}/StoreData/Apps/{row['title']}/{date}[descr.txt]\n"
        content += f"http://{host}/StoreData/Apps/{row['title']}/{date}[file.sis]\n"
        content += f"http://{host}/StoreData/Apps/{row['title']}/{date}[preview.png]\n"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT title, file FROM games")
    results = cursor.fetchall()
    cursor.close()

    for row in results:
        # date = int(round(os.stat(os.path.join(current_app.root_path, 'static', 'files', row['file'])).st_size / (1024 * 1024), 2))
        date = 1708635534
        content += f"http://{host}/StoreData/Games/{row['title']}/{date}[descr.txt]\n"
        content += f"http://{host}/StoreData/Games/{row['title']}/{date}[file.sis]\n"
        content += f"http://{host}/StoreData/Games/{row['title']}/{date}[preview.png]\n"

    content += f"http://{host}/StoreData/{date}[RefreshStore.php]\n"
    content += f"http://{host}/StoreData/{date}[storeIndex.xml]"

    return content

def qtstore_content(name, content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(f"SELECT title, description, file, img FROM {content_type} WHERE title LIKE %s LIMIT 1", (name,))
    results = cursor.fetchone()
    cursor.close()

    return results if results else None