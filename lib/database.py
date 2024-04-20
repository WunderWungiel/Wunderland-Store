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
            "platformName": get_platform_name(row["platform"]),
            "image1": row["image1"],
            "image2": row["image2"],
            "image3": row["image3"],
            "image4": row["image4"],
            "img": os.path.join(content_type, row["img"]),
            "content_type": content_type,
            "rating": get_rating(row["id"], content_type),
            "addon_message": row["addon_message"],
            "addon_file": row["addon_file"],
            "screenshots": tuple([image for image in (row['image1'], row['image2'], row['image3'], row['image4']) if image])
        }

    return final_results

def get_content(id=None, categoryId=None, content_type=None, platformId="all"):

    categories = get_categories(content_type)
    categories_ids = [result[0] for result in categories]

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if id:
        id = int(id)

    if categoryId is None:
        if platformId == "all":
            if id:
                query = f"SELECT * FROM {content_type} WHERE id=%s AND visible=true"
                cursor.execute(query, (id,))
            else:
                query = f"SELECT * FROM {content_type} WHERE visible=true"
                cursor.execute(query)
        else:
            if id:
                query = f"SELECT * FROM {content_type} WHERE platform=%s AND id=%s AND visible=true"
                cursor.execute(query, (platformId, id))
            else:
                query = f"SELECT * FROM {content_type} WHERE platform=%s AND visible=true"
                cursor.execute(query, (platformId,))
    else:
        if int(categoryId) not in categories_ids:
            raise WrongCategoryError
        
        if platformId == "all":
            if id:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND id=%s AND visible=true ORDER BY title"
                cursor.execute(query, (int(categoryId), id))
            else:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND visible=true ORDER BY title"
                cursor.execute(query, (int(categoryId),))
        else:
            if id:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND platform=%s AND id=%s AND visible=true ORDER BY title"
                cursor.execute(query, (int(categoryId), platformId, id))
            else:
                query = f"SELECT * FROM {content_type} WHERE category=%s AND platform=%s AND visible=true ORDER BY title"
                cursor.execute(query, (int(categoryId), platformId))
    
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

def get_platform_name(platformId):
    
    query = f"SELECT name FROM platforms WHERE id=%s"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, (platformId,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["name"]

def get_platform_id(platformName):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"SELECT id FROM platforms WHERE name=%s", (platformName,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["id"]

def get_category_name(categoryId, content_type):
    
    query = f"SELECT name FROM {content_type}_categories WHERE id=%s"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query, (int(categoryId),))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["name"]

def get_category_id(categoryName, content_type):

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(f"SELECT id FROM {content_type}_categories WHERE name=%s", (categoryName,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result["id"]

def search(query, databases):

    if not databases:
        databases = ("apps", "games")

    results = {}

    for database in databases:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(f"SELECT * FROM {database} WHERE LOWER(title) LIKE LOWER(%s) ORDER BY title", ('%' + query + '%',))
        db_results = cursor.fetchall()
        cursor.close()

        results = results | format_results(db_results, database)

    return results

class AccountSystem:
    def __init__(self):
        pass

    def _generate_password(self, user_password):
        user_password = user_password.encode('utf-8')
        salt = bcrypt.gensalt()

        hashed_password = bcrypt.hashpw(user_password, salt)
        return hashed_password.decode('utf-8')
    
    def get_user(self, email=None, id=None):
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if email:
            cursor.execute("SELECT id, email, username, password, confirmed, banned, banned_reason FROM users WHERE email=%s AND active=true", (email,))
        elif id:
            cursor.execute("SELECT id, email, username, password, confirmed, banned, banned_reason FROM users WHERE id=%s AND active=true", (id,))
        else:
            raise TypeError("Provide either id or email")
        
        result = cursor.fetchone()
        cursor.close()

        if not result:
            return None

        return result

    def confirm_user(self, email):
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET confirmed=true WHERE email=%s", (email,))
        conn.commit()

    def get_emails(self):
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT email FROM users WHERE active=true")

        results = cursor.fetchall()
        cursor.close()
        results = [result["email"] for result in results]
        
        return results
    
    def get_usernames(self):
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT username FROM users WHERE active=true")

        results = cursor.fetchall()
        cursor.close()
        results = [row["username"] for row in results]
        
        return results

    def register(self, email, user_password, username):

        hashed_password = self._generate_password(user_password)

        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, username, confirmed) VALUES (%s, %s, %s, false)", (email, hashed_password, username))
        cursor.close()

        conn.commit()

    def check_credentials(self, email, user_password):
        emails = self.get_emails()
        if email not in emails:
            return False

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT password FROM users WHERE email=%s AND active=true", (email,))
        
        result = cursor.fetchone()
        cursor.close()

        hashed_password = result["password"].encode('utf-8')
        user_password = user_password.encode('utf-8')

        return bcrypt.checkpw(user_password, hashed_password)
    
    def get_user_id(self, email=None, username=None, id=None):
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if email:
            cursor.execute("SELECT id FROM users WHERE email=%s AND active=true", (email,))
        elif id:
            cursor.execute("SELECT id FROM users WHERE id=%s AND active=true", (id,))
        elif username:
            cursor.execute("SELECT id FROM users WHERE username=%s AND active=true", (username,))
        else:
            raise TypeError("Provide either id or email")

        result = cursor.fetchone()
        cursor.close()

        return result["id"] if result else None
        
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

    print(final_results)

    return final_results