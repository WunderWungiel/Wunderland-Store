import os

import bcrypt
import psycopg2

from .config import config
from . import conn

class WrongCategoryError(Exception):
    pass

def format_results(results_list, content_type):

    results = {}
    for result_list in results_list:
        results[result_list[0]] = {
            "id": result_list[0],
            "title": result_list[1],
            "file": result_list[2],
            "category_name": get_category_name(result_list[3], content_type),
            "category_id": result_list[3],
            "description": result_list[4].strip(),
            "publisher": result_list[5],
            "version": result_list[6],
            "platform": result_list[7],
            "platformName": get_platform_name(result_list[7]),
            "screenshots_count": result_list[8],
            "img": os.path.join(content_type, result_list[9]),
            "content_type": content_type,
            "rating": get_rating(result_list[0], content_type),
            "addon_message": result_list[11],
            "addon_file": result_list[12]
        }

    return results

def get_content(id=None, categoryId=None, content_type=None, platformId="all"):

    categories = get_categories(content_type)
    categories_ids = [result[0] for result in categories]

    cursor = conn.cursor()

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
    
    results_list = cursor.fetchall()
    cursor.close()
    if not results_list:
        return None

    results = format_results(results_list, content_type)
    if id:
        return results.get(id)
    else:
        return results

def get_rating(content_id, content_type):
    
    cursor = conn.cursor()
    query = f"SELECT ROUND(AVG(rating)) as rating FROM {content_type}_rating WHERE content_id=%s"
    cursor.execute(query, (content_id,))
    result = cursor.fetchone()[0]
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

    cursor = conn.cursor()
    cursor.execute(query, (platformId,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result[0]

def get_platform_id(platformName):

    cursor = conn.cursor()

    cursor.execute(f"SELECT id FROM platforms WHERE name=%s", (platformName,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result[0]

def get_category_name(categoryId, content_type):
    
    query = f"SELECT name FROM {content_type}_categories WHERE id=%s"

    cursor = conn.cursor()
    cursor.execute(query, (int(categoryId),))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result[0]

def get_category_id(categoryName, content_type):

    cursor = conn.cursor()

    cursor.execute(f"SELECT id FROM {content_type}_categories WHERE name=%s", (categoryName,))
    result = cursor.fetchone()
    if not result:
        return None
    cursor.close()
    return result[0]

def search(query, databases):

    if not databases:
        databases = ("apps", "games")

    results = {}

    for database in databases:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {database} WHERE LOWER(title) LIKE LOWER(%s) ORDER BY title", ('%' + query + '%',))
        results_list = cursor.fetchall()
        cursor.close()

        results = results | format_results(results_list, database)

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
        cursor = conn.cursor()
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
        
        user = {
            'id': result[0],
            'email': result[1],
            'username': result[2],
            'password': result[3],
            'confirmed': result[4],
            'banned': result[5],
            'banned_reason': result[6]
        }

        return user

    def confirm_user(self, email):
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET confirmed=true WHERE email=%s", (email,))
        conn.commit()

    def get_emails(self):
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE active=true")

        results = cursor.fetchall()
        cursor.close()
        results = [result[0] for result in results]
        
        return results
    
    def get_usernames(self):
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE active=true")

        results = cursor.fetchall()
        cursor.close()
        results = [result[0] for result in results]
        
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

        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE email=%s AND active=true", (email,))
        
        result = cursor.fetchone()
        cursor.close()

        hashed_password = result[0].encode('utf-8')
        user_password = user_password.encode('utf-8')

        return bcrypt.checkpw(user_password, hashed_password)
    
    def get_user_id(self, email=None, username=None, id=None):
        cursor = conn.cursor()
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

        return result[0] if result else None
        
account_system = AccountSystem()