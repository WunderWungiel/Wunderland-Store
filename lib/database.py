import os
from datetime import datetime

import bcrypt
import psycopg2
import psycopg2.extras
from markdown import markdown
from flask import current_app

from . import conn


class WrongCategoryError(Exception):
    pass


def get_content_type_ids(content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = f"SELECT id FROM {content_type}"
    cursor.execute(query)
    return [result["id"] for result in cursor.fetchall()]


def get_content_number(content_type, category_id=None):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = f"SELECT COUNT(id) AS count FROM {content_type}"
    args = []
    if category_id:
        query += " WHERE category=%s"
        args.append(category_id)
    
    cursor.execute(query, args)
    result = cursor.fetchone()["count"]
    return result


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

    categories = get_categories(content_type)
    categories_ids = [result[0] for result in categories]

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if id:
        id = int(id)

    if category_id is None:
        if platform_id == "all":
            if id:
                query = f"SELECT * FROM {content_type} WHERE id=%s AND visible=true ORDER BY id DESC"
                cursor.execute(query, (id,))
            else:
                query = f"SELECT * FROM {content_type} WHERE visible=true ORDER BY id DESC"
                cursor.execute(query)
        else:
            if id:
                query = f"SELECT * FROM {content_type} WHERE (platform=%s or platform IS NULL) AND id=%s AND visible=true ORDER BY id DESC"
                cursor.execute(query, (platform_id, id))
            else:
                query = f"SELECT * FROM {content_type} WHERE (platform=%s OR platform IS null) AND visible=true ORDER BY id DESC"
                cursor.execute(query, (platform_id,))
    else:
        if int(category_id) not in categories_ids:
            raise WrongCategoryError
        
        if platform_id == "all":
            if id:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND id=%s AND visible=true ORDER BY id DESC"
                cursor.execute(query, (int(category_id), id))
            else:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND visible=true ORDER BY id DESC"
                cursor.execute(query, (int(category_id),))
        else:
            if id:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND platform=%s AND id=%s AND visible=true ORDER BY id DESC"
                cursor.execute(query, (int(category_id), platform_id, id))
            else:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND platform=%s AND visible=true ORDER BY id DESC"
                cursor.execute(query, (int(category_id), platform_id))
    
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
    if not result:
        return None
    cursor.close()
    return result["name"]


def get_platform_id(platform_name):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"SELECT id FROM platforms WHERE name=%s", (platform_name,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["id"]


def get_category_name(category_id, content_type):
    
    query = f"SELECT name FROM {content_type}_categories WHERE id=%s"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, (int(category_id),))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["name"]


def get_category_id(category_name, content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"SELECT id FROM {content_type}_categories WHERE name=%s", (category_name,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["id"]


def search(query, databases):

    if not databases:
        databases = ("apps", "games", "themes")

    results = {}

    for database in databases:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            f"SELECT * FROM {database} WHERE LOWER(title) LIKE LOWER(%s) ORDER BY title",
            ('%' + query + '%',)
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


class AccountSystem:
    def __init__(self):
        pass

    def _generate_password(self, user_password):
        user_password = user_password.encode('utf-8')
        salt = bcrypt.gensalt()

        hashed_password = bcrypt.hashpw(user_password, salt)
        return hashed_password.decode('utf-8')

    def get_user(self, id=None, username=None, email=None):
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = "SELECT id, email, username, password, confirmed, banned, banned_reason FROM users WHERE active=true AND "
        if email:
            query += "email=%s"
            args = (email,)
        elif username:
            query += "username=%s"
            args = (username,)
        elif id:
            query += "id=%s"
            args = (id,)
        else:
            raise TypeError

        cursor.execute(query, args)
        
        result = cursor.fetchone()
        cursor.close()

        return result if result else None
    
    def get_user_id(self, username=None, email=None):

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = "SELECT id FROM users WHERE "
        if username:
            query += "username=%s"
            args = (username,)
        elif email:
            query += "email=%s"
            args = (email,)
        else:
            raise TypeError

        cursor.execute(query, args)
        result = cursor.fetchone()
        cursor.close()

        return result['id'] if result else None
    
    def get_user_email(self, id=None, username=None):

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = "SELECT email FROM users WHERE "
        if id:
            query += "id=%s"
            args = (id,)
        elif username:
            query += "username=%s"
            args = (username,)
        else:
            raise TypeError

        cursor.execute(query, args)
        result = cursor.fetchone()
        cursor.close()

        return result['email'] if result else None
    
    def confirm_user(self, email):
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET confirmed=true WHERE email=%s", (email,))
        conn.commit()
    
    def email_exists(self, email):

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))

        result = cursor.fetchone()
        cursor.close()
        
        return True if result else False
    
    def username_exists(self, username):

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))

        result = cursor.fetchone()
        cursor.close()
        
        return True if result else False

    def register(self, email, user_password, username):

        hashed_password = self._generate_password(user_password)

        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, username, confirmed) VALUES (%s, %s, %s, false)", (email, hashed_password, username))
        cursor.close()

        conn.commit()

    def change_password(self, id, new_password):

        hashed_password = self._generate_password(new_password)

        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, id))

        conn.commit()


    def check_credentials(self, email, user_password):
        if not self.email_exists(email):
            return False

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT password FROM users WHERE email=%s AND active=true", (email,))
        
        result = cursor.fetchone()
        cursor.close()

        hashed_password = result["password"].encode('utf-8')
        user_password = user_password.encode('utf-8')

        return bcrypt.checkpw(user_password, hashed_password)
        
account_system = AccountSystem()


def get_news(news_id=None):
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if not news_id:
        cursor.execute("SELECT * FROM news")
    else:
        cursor.execute("SELECT * FROM news WHERE id=%s", (news_id,))
    results = cursor.fetchall()
    cursor.close()
    if not results:
        return None

    final_results = []

    for row in results:
        file_path = os.path.join(current_app.root_path, "news", row['file'])

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
