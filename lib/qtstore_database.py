"""QtStore database backend"""

from flask import request
import psycopg2
import psycopg2.extras

from . import conn

def qtstore_generator():

    host = request.host
    content = ""

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT title, file FROM apps WHERE (platform='s60' OR platform IS NULL) ORDER BY id DESC")
    results = cursor.fetchall()
    cursor.close()

    for row in results:
        # date = int(round(os.stat(os.path.join(current_app.root_path, 'static', 'files', row['file'])).st_size / (1024 * 1024), 2))
        date = 1708635534
        content += f"http://{host}/StoreData/Apps/{row['title']}/{date}[descr.txt]\n"
        content += f"http://{host}/StoreData/Apps/{row['title']}/{date}[file.sis]\n"
        content += f"http://{host}/StoreData/Apps/{row['title']}/{date}[preview.png]\n"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT title, file FROM games WHERE (platform='s60' OR platform IS NULL) ORDER BY id DESC")
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
    cursor.execute(f"SELECT title, description, file, img, addon_message, addon_file, image1, image2, image3, image4 FROM {content_type} WHERE title LIKE %s AND (platform='s60' OR platform IS NULL) LIMIT 1", (name,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        result["screenshots"] = [image for image in (result['image1'], result['image2'], result['image3'], result['image4']) if image]
        print(result)
        return result
    else:
        return None