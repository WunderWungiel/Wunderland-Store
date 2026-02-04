import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from markdown import markdown
from flask import current_app

from . import conn


def build_query(base_query, conditions={}, extras=""):

    query = base_query
    query_params = []

    where_clauses = []

    for column, values in conditions.items():

        if isinstance(values, list) and values:
            or_clauses = [f"{column}=%s" if value is not None else f"{column} IS NULL" for value in values]
            where_clauses.append(f"({' OR '.join(or_clauses)})")
            query_params.extend(value for value in values if value is not None)
        else:
            where_clauses.append(f"{column}=%s" if values is not None else f"{column} IS NULL")
            if values is not None:
                query_params.append(values)

    if len(conditions) > 0:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " " + extras

    return query, query_params


def get_content_type_ids(content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = f"SELECT id FROM {content_type}"
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return [result["id"] for result in results]


def get_content_number(content_type, category_id=None):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = f"SELECT COUNT(id) AS count FROM {content_type}"
    args = []
    if category_id:
        query += " WHERE category=%s"
        args.append(category_id)
    
    cursor.execute(query, args)
    result = cursor.fetchone()
    cursor.close()
    
    return result["count"] if result else None


def format_results(results, content_type):

    final_results = {}
    for row in results:
        final_results[row["id"]] = {
            "id": row["id"],
            "title": row["title"],
            "file": row["file"],
            "category_name": get_category_name(row["category"], content_type),
            "category_id": row["category"],
            "description": row["description"],
            "publisher": row["publisher"],
            "version": row["version"],
            "platform": row["platform"],
            "platform_name": get_platform_name(row["platform"]) if row["platform"] is not None else None,
            "image1": row["image1"],
            "image2": row["image2"],
            "image3": row["image3"],
            "image4": row["image4"],
            "img": os.path.join(content_type, row["img"]),
            "content_type": content_type,
            "rating": get_rating(row["id"], content_type),
            "addon_message": row["addon_message"],
            "addon_file": row["addon_file"],
            "uid": row["uid"],
            "screenshots": tuple([image for image in (
                row['image1'],
                row['image2'],
                row['image3'],
                row['image4']
            ) if image])
        }

    return final_results


def get_content(id=None, category_id=None, content_type=None, platform_id="all"):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_query = f"SELECT * FROM {content_type}"
    conditions = {"visible": True}
    if id:
        id = int(id)
        conditions["id"] = id
    if category_id:
        category_id = int(category_id)
        conditions["category"] = category_id
    if platform_id != "all":
        conditions["platform"] = [platform_id, None]

    query, query_params = build_query(base_query, conditions, "ORDER BY id DESC")
    
    cursor.execute(query, query_params)

    results = cursor.fetchall()
    cursor.close()

    if not results:
        return None

    results = format_results(results, content_type)

    if id:
        return results.get(id)
    else:
        return results


def get_rating(content_id, content_type):
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = f"SELECT ROUND(AVG(rating)) as rating FROM {content_type}_rating WHERE content_id=%s"
    cursor.execute(query, (content_id,))
    result = cursor.fetchone()["rating"]
    cursor.close()

    return int(result) if result else 0


def rate(rating, user_id, content_id, content_type):

    cursor = conn.cursor()
    query = f"SELECT * FROM {content_type}_rating WHERE content_id=%s AND user_id=%s"
    cursor.execute(query, (content_id, user_id))
    results = cursor.fetchall()
    cursor.close()

    cursor = conn.cursor()
    if results:
        query = f"UPDATE {content_type}_rating SET rating=%s WHERE content_id=%s AND user_id=%s"
        cursor.execute(query, (rating, content_id, user_id))
    else:
        query = f"INSERT INTO {content_type}_rating (content_id, rating, user_id) VALUES (%s, %s, %s)"
        cursor.execute(query, (content_id, rating, user_id))

    conn.commit()
    cursor.close()


def get_categories(content_type):

    query = f"SELECT * FROM {content_type}_categories ORDER by name"

    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return results


def get_platforms():

    query = f"SELECT * FROM platforms ORDER by name"

    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return results


def get_platform_name(platform_id):
    
    query = f"SELECT name FROM platforms WHERE id=%s"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, (platform_id,))
    result = cursor.fetchone()
    cursor.close()

    return result["name"] if result else None


def get_platform_id(platform_name):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"SELECT id FROM platforms WHERE name=%s", (platform_name,))
    result = cursor.fetchone()
    cursor.close()

    return result["id"] if result else None


def get_category_name(category_id, content_type):
    
    query = f"SELECT name FROM {content_type}_categories WHERE id=%s"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, (int(category_id),))
    result = cursor.fetchone()
    cursor.close()

    return result["name"] if result else None


def get_category_id(category_name, content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"SELECT id FROM {content_type}_categories WHERE name=%s", (category_name,))
    result = cursor.fetchone()
    cursor.close()

    return result["id"] if result else None


def search(query, databases=None):

    if not databases:
        databases = ("apps", "games", "themes")

    results = {}

    for database in databases:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            f"SELECT * FROM {database} WHERE LOWER(title) LIKE LOWER(%s) ORDER BY title",
            (f'%{query}%',)
        )

        db_results = cursor.fetchall()
        cursor.close()

        results = results | format_results(db_results, database)

    return results


def increment_counter(id, content_type):
    cursor = conn.cursor()
    cursor.execute(f"UPDATE {content_type} SET visited_counter=visited_counter + 1 WHERE id=%s", (id,))
    conn.commit()
    cursor.close()

def get_news(news_id=None):
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not news_id:
        cursor.execute("SELECT * FROM news ORDER BY id DESC")
    else:
        cursor.execute("SELECT * FROM news WHERE id=%s", (news_id,))
    results = cursor.fetchall()
    cursor.close()
    if not results:
        return None

    final_results = []

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

        final_results.append(
            {
                'id': row['id'],
                'title': row['title'],
                'content': html_content,
                'date': file_date
            }
        )

    return final_results
