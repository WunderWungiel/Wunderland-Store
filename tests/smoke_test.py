#!/usr/bin/env python3
"""Request every route once and check the responses.

Run it against a throwaway database created from db/schema.sql, with the
POSTGRES_* environment variables pointing at that database. The script
fills the empty tables with a small set of fixtures, requests each web page
and both client XML APIs through the Flask test client, then empties the
tables again and removes the fixture files it wrote under the content
directory.

It refuses to run if any of the tables it uses already hold rows, so it
can't touch a real store's data.

    python -m tests.smoke_test

Run it from the repo root. WUNDERLAND_CONFIG can name a config file other
than the repo root's config.yaml.

Exit status is 0 when every check passes and 1 otherwise.
"""
import os
import sys
import traceback
from xml.etree import ElementTree as ET

from wunderland import db
from wunderland.app import app
from wunderland.config import CONTENT_DIR, config

# Every table the fixtures or the requests write to.
TABLES = [
    'ratings', 'content_stats', 'content_platforms', 'content_legacy', 'categories_legacy',
    'content', 'categories', 'content_types', 'platforms', 'news', 'sessions', 'users',
]

TITLE = "Smoke Test App"
PREFIX = "smoke-test"
LEGACY_PREFIX = "applications"
LEGACY_ID = 4242
CLIENT_CATEGORY_ID = 7
NEWS_TITLE = "Smoke test news"
ADMIN_EMAIL = "smoke-admin@example.com"
ADMIN_PASSWORD = "smoke-password"

FIXTURE_FILES = {
    os.path.join(CONTENT_DIR, "files", f"{PREFIX}.sis"): b"not a real sis file",
    os.path.join(CONTENT_DIR, "icons", f"{PREFIX}.png"): b"\x89PNG\r\n\x1a\n",
    os.path.join(CONTENT_DIR, "screenshots", f"{PREFIX}1.jpg"): b"\xff\xd8\xff",
    os.path.join(CONTENT_DIR, "news", f"{PREFIX}.md"): b"Smoke test news body.\n",
}


def execute(cursor, query, params=()):
    cursor.execute(query, params)
    return cursor.fetchone() if cursor.description else None


def check_empty():
    with db.pool.connection() as connection, connection.cursor() as cursor:
        busy = [table for table in TABLES if execute(cursor, f"SELECT EXISTS (SELECT 1 FROM {table}) AS e")['e']]
    if busy:
        sys.exit(f"Refusing to run: these tables already hold rows: {', '.join(busy)}. "
                 "Point the POSTGRES_* variables at a fresh database created from db/schema.sql.")
    existing = [path for path in FIXTURE_FILES if os.path.exists(path)]
    if existing:
        sys.exit(f"Refusing to run: fixture files already exist: {', '.join(existing)}")


def seed():
    written = []
    for path, data in FIXTURE_FILES.items():
        with open(path, 'xb') as destination:
            written.append(path)
            destination.write(data)

    platforms = sorted(set(config['platforms']['qtstore']) | set(config['platforms']['client']))

    with db.pool.connection() as connection, connection.cursor() as cursor:
        for platform_id in platforms:
            execute(cursor, "INSERT INTO platforms (id, name) VALUES (%s, %s)", (platform_id, f"Platform {platform_id}"))
        for type_id, name, prefix in (('apps', 'Applications', LEGACY_PREFIX), ('games', 'Games', 'games'),
                                      ('themes', 'Themes', 'themes')):
            execute(cursor, "INSERT INTO content_types (id, name, prefix) VALUES (%s, %s, %s)", (type_id, name, prefix))
        category_id = execute(
            cursor, "INSERT INTO categories (name, type_id, client_id) VALUES ('Utilities', 'apps', %s) RETURNING id",
            (CLIENT_CATEGORY_ID,))['id']
        content_id = execute(cursor, """
            INSERT INTO content (title, file, category_id, description, publisher, version, icon,
                                 screenshot_prefix, screenshot_count, addon_text, uid)
            VALUES (%s, %s, %s, %s, 'Smoke Publisher', '1.02(3)', %s, %s, 1, 'Extra notes', '0xE0000001')
            RETURNING id""", (TITLE, f"{PREFIX}.sis", category_id, "Line one\nLine two", f"{PREFIX}.png", PREFIX))['id']
        for platform_id in platforms:
            execute(cursor, "INSERT INTO content_platforms (content_id, platform_id) VALUES (%s, %s)",
                    (content_id, platform_id))
        execute(cursor, "INSERT INTO content_legacy (type_id, old_id, new_id) VALUES ('apps', %s, %s)",
                (LEGACY_ID, content_id))
        news_id = execute(cursor, "INSERT INTO news (title, file) VALUES (%s, %s) RETURNING id",
                          (NEWS_TITLE, f"{PREFIX}.md"))['id']
        admin_id = execute(cursor, """
            INSERT INTO users (email, password, confirmed, username, role)
            VALUES (%s, %s, true, 'smokeadmin', 'admin') RETURNING id""",
                           (ADMIN_EMAIL, db.generate_password(ADMIN_PASSWORD)))['id']

    return {'content_id': content_id, 'category_id': category_id, 'news_id': news_id, 'admin_id': admin_id}


def cleanup():
    with db.pool.connection() as connection, connection.cursor() as cursor:
        # No CASCADE: a table outside TABLES that references these makes this fail
        # instead of being emptied without ever being checked.
        cursor.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY")
    for path in FIXTURE_FILES:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


class Runner:
    def __init__(self):
        self.failures = 0
        self.count = 0

    def check(self, client, method, path, status, contains=None, xml=False, location=None, data=None):
        self.count += 1
        label = f"{method} {path}"
        try:
            response = client.open(path, method=method, data=data)
            body = response.get_data()
            problems = []
            if response.status_code != status:
                problems.append(f"status {response.status_code}, expected {status}")
            for text in ([contains] if isinstance(contains, str) else contains or []):
                if text.encode() not in body:
                    problems.append(f"body lacks {text!r}")
            if xml:
                try:
                    ET.fromstring(body)
                except ET.ParseError as error:
                    problems.append(f"invalid XML: {error}")
            if location and location not in response.headers.get('Location', ''):
                problems.append(f"Location {response.headers.get('Location')!r} lacks {location!r}")
        except Exception:
            problems = ["raised:\n" + traceback.format_exc()]

        if problems:
            self.failures += 1
            print(f"FAIL {label}: {'; '.join(problems)}")
        else:
            print(f"ok   {label}")


def csrf_token(client):
    with client.session_transaction() as session:
        return session.get('csrf_token')


def run_checks(ids):
    content_id = ids['content_id']
    news_id = ids['news_id']
    run = Runner()

    # Logged-out web pages.
    with app.test_client() as client:
        run.check(client, 'GET', '/', 302, location='/home')
        run.check(client, 'GET', '/home', 200, contains=NEWS_TITLE)
        run.check(client, 'GET', '/home?page=0', 302)
        run.check(client, 'GET', '/home?page=99', 302)
        run.check(client, 'GET', '/content/apps', 200, contains=TITLE)
        run.check(client, 'GET', f"/content/apps?category_id={ids['category_id']}", 200,
                  contains=[TITLE, 'Applications • Utilities • ', 'content="Utilities applications"'])
        run.check(client, 'GET', '/content/apps?sort=title&order=1', 200, contains=TITLE)
        run.check(client, 'GET', '/content/apps?sort=bogus', 200, contains=TITLE)
        run.check(client, 'GET', '/content/games', 200)
        run.check(client, 'GET', '/content/nonexistent', 302)
        run.check(client, 'GET', '/content/apps/browse', 200, contains='Utilities')
        run.check(client, 'GET', f'/item/{content_id}', 200, contains=[
            TITLE, 'Line one<br/>Line two', f'<title>{TITLE} for Platform ', 'content="Line one Line two"'])
        run.check(client, 'GET', '/item/999999', 404)
        run.check(client, 'GET', f'/content/{content_id}/images', 200, contains=f'{PREFIX}1.jpg')
        run.check(client, 'GET', f'/content/{content_id}/rate', 302, location='/login')
        run.check(client, 'GET', '/search', 200)
        run.check(client, 'GET', '/search?query=Smoke', 200, contains=[TITLE, 'noindex'])
        run.check(client, 'GET', '/search?query=nothing-matches-this', 200)
        run.check(client, 'GET', '/platforms', 200)
        run.check(client, 'POST', '/platforms', 302, data={
            'platform_id': config['platforms']['client'][0], 'csrf_token': csrf_token(client)})
        run.check(client, 'GET', '/content/apps', 200, contains=TITLE)
        run.check(client, 'POST', '/platforms', 302, data={'platform_id': ''})  # no CSRF token
        run.check(client, 'GET', '/download', 200)
        run.check(client, 'GET', '/feed.xml', 200, contains=NEWS_TITLE, xml=True)
        run.check(client, 'GET', f'/news/{news_id}', 200,
                  contains=['Smoke test news body.', f'<title>{NEWS_TITLE} • ', 'content="Smoke test news body.'])
        run.check(client, 'GET', '/news/999999', 302)
        run.check(client, 'GET', '/login', 200)
        run.check(client, 'GET', '/register', 200)
        run.check(client, 'GET', '/profile', 302, location='/login')
        run.check(client, 'GET', '/content/upload', 302)
        run.check(client, 'GET', '/confirm/not-a-real-token', 200)
        run.check(client, 'GET', '/robots.txt', 404 if config['allow_indexing'] else 200)
        run.check(client, 'GET', '/static/css/style.css', 200)
        run.check(client, 'GET', f'/static/content/icons/{PREFIX}.png', 200, contains='PNG')
        run.check(client, 'GET', f'/static/content/files/{PREFIX}.sis', 200, contains='not a real sis file')
        run.check(client, 'GET', '/static/content/icons/missing.png', 404)
        run.check(client, 'GET', '/no/such/page', 404)
        run.check(client, 'GET', '/healthz', 200, contains='ok')
        run.check(client, 'HEAD', '/healthz', 200)

        # Old Ovi Store URLs.
        run.check(client, 'GET', f'/{LEGACY_PREFIX}/{LEGACY_ID}', 307, location=f'/item/{content_id}')
        run.check(client, 'GET', f'/{LEGACY_PREFIX}/{LEGACY_ID}/images', 307, location=f'/content/{content_id}/images')
        run.check(client, 'GET', f'/{LEGACY_PREFIX}/{LEGACY_ID}/rate', 307, location=f'/content/{content_id}/rate')
        run.check(client, 'GET', f'/{LEGACY_PREFIX}/1', 404)
        run.check(client, 'GET', f'/unknownprefix/{LEGACY_ID}', 404)

    # Java/Qt client XML API.
    with app.test_client() as client:
        run.check(client, 'GET', '/applist.php', 200, contains=TITLE, xml=True)
        run.check(client, 'GET', '/applist.php?category=0', 200, contains=TITLE, xml=True)
        run.check(client, 'GET', f'/applist.php?category={CLIENT_CATEGORY_ID}', 200, contains=TITLE, xml=True)
        run.check(client, 'GET', '/applist.php?category=12', 200, xml=True)
        run.check(client, 'GET', f'/applist.php?id={content_id},abc', 200, contains=[TITLE, '1.2.3'], xml=True)
        run.check(client, 'GET', '/applist.php?search=Smoke', 200, contains=TITLE, xml=True)
        run.check(client, 'GET', '/applist.php?widget=1', 200, contains='0xE0000001', xml=True)
        run.check(client, 'GET', '/applist.php?start=1&count=1', 200, contains=TITLE, xml=True)
        run.check(client, 'GET', '/applist-download.php', 200, contains='0')
        run.check(client, 'GET', '/version.xml', 200, xml=True)
        run.check(client, 'GET', '/changelog.xml', 200, xml=True)

    # Qt store index and item files.
    with app.test_client() as client:
        run.check(client, 'GET', '/StoreData/storeIndex.xml', 200, contains=[
            '/StoreData/Apps/Smoke%20Test%20App/', '[descr.txt]', '[file.sis]', '[preview.png]'])
        base = '/StoreData/Apps/Smoke%20Test%20App'
        run.check(client, 'GET', f'{base}/descr.txt', 200, contains=['Line one', f'{PREFIX}1.jpg', 'Extra notes'])
        run.check(client, 'GET', f'{base}/file.sis', 200, contains='not a real sis file')
        run.check(client, 'GET', f'{base}/preview.png', 200)
        run.check(client, 'GET', '/StoreData/Apps/No%20Such%20App/descr.txt', 404)
        run.check(client, 'GET', '/StoreData/Nope/Smoke%20Test%20App/descr.txt', 404)

    # Logging in through the form, then the logged-in pages.
    with app.test_client() as client:
        run.check(client, 'GET', '/login', 200)
        run.check(client, 'POST', '/login', 302, location='/home', data={
            'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD, 'csrf_token': csrf_token(client)})
        with client.session_transaction() as session:
            logged_in = bool(session.get('token'))
        run.count += 1
        if logged_in:
            print("ok   login set a session token")
        else:
            run.failures += 1
            print("FAIL login set no session token")

        run.check(client, 'GET', '/profile', 200, contains='smokeadmin')
        run.check(client, 'GET', '/login', 302)
        run.check(client, 'GET', '/content/upload', 200)
        run.check(client, 'GET', f'/content/{content_id}/rate', 200)
        run.check(client, 'POST', f'/content/{content_id}/rate', 302, location=f'/item/{content_id}', data={
            'rating': '4', 'csrf_token': csrf_token(client)})
        run.check(client, 'GET', f'/item/{content_id}', 200, contains=TITLE)
        # Logging out needs the CSRF token; without it the session stays.
        run.check(client, 'GET', '/logout', 302, location='/profile')
        run.check(client, 'GET', '/profile', 200, contains='smokeadmin')
        run.check(client, 'GET', f'/logout?csrf_token={csrf_token(client)}', 302, location='/home')
        run.check(client, 'GET', '/profile', 302, location='/login')

    print(f"\n{run.count - run.failures}/{run.count} checks passed")
    return run.failures == 0


def main():
    app.config['TESTING'] = True
    check_empty()
    try:
        ids = seed()
        passed = run_checks(ids)
    finally:
        cleanup()
        db.pool.close()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
