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
import json
import os
import sys
import traceback
from unittest import mock
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
HIDDEN_TITLE = "Smoke Hidden App"
PREFIX = "smoke-test"
LEGACY_PREFIX = "applications"
LEGACY_ID = 4242
LEGACY_HIDDEN_ID = 4243
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
        # Hidden items must not show up anywhere, nor reveal that they exist.
        hidden_id = execute(cursor, """
            INSERT INTO content (title, file, category_id, publisher, version, icon, screenshot_prefix,
                                 screenshot_count, uid, visible)
            VALUES (%s, %s, %s, 'Smoke Publisher', '1.0', %s, %s, 0, '0xE0000002', FALSE)
            RETURNING id""", (HIDDEN_TITLE, f"{PREFIX}.sis", category_id, f"{PREFIX}.png", PREFIX))['id']
        execute(cursor, "INSERT INTO content_legacy (type_id, old_id, new_id) VALUES ('apps', %s, %s)",
                (LEGACY_ID, content_id))
        execute(cursor, "INSERT INTO content_legacy (type_id, old_id, new_id) VALUES ('apps', %s, %s)",
                (LEGACY_HIDDEN_ID, hidden_id))
        news_id = execute(cursor, "INSERT INTO news (title, file) VALUES (%s, %s) RETURNING id",
                          (NEWS_TITLE, f"{PREFIX}.md"))['id']
        admin_id = execute(cursor, """
            INSERT INTO users (email, password, confirmed, username, role)
            VALUES (%s, %s, true, 'smokeadmin', 'admin') RETURNING id""",
                           (ADMIN_EMAIL, db.generate_password(ADMIN_PASSWORD)))['id']

    return {'content_id': content_id, 'hidden_id': hidden_id, 'category_id': category_id, 'news_id': news_id,
            'admin_id': admin_id}


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

    def check(self, client, method, path, status, contains=None, xml=False, location=None, data=None, lacks=None,
              api=False, headers=None):
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
            for text in ([lacks] if isinstance(lacks, str) else lacks or []):
                if text.encode() in body:
                    problems.append(f"body has {text!r}")
            if xml:
                try:
                    ET.fromstring(body)
                except ET.ParseError as error:
                    problems.append(f"invalid XML: {error}")
            if api:
                # The JSON API: an envelope in every response, and never a cookie.
                try:
                    envelope = json.loads(body)
                    key = 'data' if response.status_code < 400 else 'error'
                    if not isinstance(envelope, dict) or key not in envelope:
                        problems.append(f"no {key!r} envelope")
                except ValueError as error:
                    problems.append(f"invalid JSON: {error}")
                if response.mimetype != 'application/json':
                    problems.append(f"Content-Type {response.content_type!r}")
                if 'Set-Cookie' in response.headers:
                    problems.append("sets a cookie")
            for name, value in (headers or {}).items():
                if response.headers.get(name) != value:
                    problems.append(f"{name} {response.headers.get(name)!r}, expected {value!r}")
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
        run.check(client, 'GET', '/', 301, location='/home')
        run.check(client, 'GET', '/home', 200, contains=NEWS_TITLE)
        run.check(client, 'GET', '/home?page=0', 302)
        run.check(client, 'GET', '/home?page=99', 302)
        run.check(client, 'GET', '/content/apps', 200, contains=TITLE)
        run.check(client, 'GET', f"/content/apps?category_id={ids['category_id']}", 200,
                  contains=[TITLE, 'Applications • Utilities • ', 'content="Utilities applications"'])
        run.check(client, 'GET', '/content/apps?sort=title&order=1', 200, contains=TITLE)
        run.check(client, 'GET', '/content/apps?sort=bogus', 200, contains=TITLE)
        run.check(client, 'GET', '/content/games', 200)
        run.check(client, 'GET', '/content/nonexistent', 404)
        run.check(client, 'GET', '/content/nonexistent/browse', 404)
        run.check(client, 'GET', '/content/apps/browse', 200, contains='Utilities')
        item_page_title = f'{TITLE} • Applications • Wunderland Store'
        run.check(client, 'GET', f'/item/{content_id}', 200, contains=[
            TITLE, 'Line one<br/>Line two', f'<title>{item_page_title}</title>',
            f'<meta property="og:title" content="{item_page_title}"/>', 'content="Line one Line two"'])
        # Listing args on a page that isn't a listing stay out of its canonical URL.
        run.check(client, 'GET', f'/item/{content_id}?page=3&category_id=9', 200,
                  contains=['rel="canonical" href="https://', f'/item/{content_id}"/>'])
        run.check(client, 'GET', '/home?page=1&sort=title', 200, contains='/home"/>')
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
        run.check(client, 'GET', '/news/999999', 404)
        run.check(client, 'GET', '/login', 200)
        run.check(client, 'GET', '/register', 200)
        run.check(client, 'GET', '/profile', 302, location='/login')
        run.check(client, 'GET', '/content/upload', 302)
        run.check(client, 'GET', '/confirm/not-a-real-token', 200)
        run.check(client, 'GET', '/robots.txt', 200,
                  contains=['Disallow: /StoreData/', 'Sitemap: https://'] if config['allow_indexing'] else 'Disallow: /')
        run.check(client, 'GET', '/sitemap.xml', 200, xml=True, contains=[
            '/home</loc>', '/content/apps</loc>', f"/content/apps?category_id={ids['category_id']}</loc>",
            f'/item/{content_id}</loc>', f'/content/{content_id}/images</loc>', f'/news/{news_id}</loc>',
            '<lastmod>'], lacks='/content/games</loc>')  # the seed data has no games
        run.check(client, 'GET', '/static/css/style.css', 200)
        run.check(client, 'GET', f'/static/content/icons/{PREFIX}.png', 200, contains='PNG')
        run.check(client, 'GET', f'/static/content/files/{PREFIX}.sis', 200, contains='not a real sis file')
        run.check(client, 'GET', '/static/content/icons/missing.png', 404)
        run.check(client, 'GET', '/no/such/page', 404)
        run.check(client, 'GET', '/healthz', 200, contains='ok')
        run.check(client, 'HEAD', '/healthz', 200)

        # Old Ovi Store URLs.
        run.check(client, 'GET', f'/{LEGACY_PREFIX}/{LEGACY_ID}', 301, location=f'/item/{content_id}')
        run.check(client, 'GET', f'/{LEGACY_PREFIX}/{LEGACY_ID}/images', 301, location=f'/content/{content_id}/images')
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

    # JSON API.
    with app.test_client() as client:
        category_id = ids['category_id']
        platform_id = config['platforms']['client'][0]
        cached = {'Cache-Control': 'public, max-age=3600'}
        run.check(client, 'GET', '/api/v1/', 200, api=True, headers={'Cache-Control': 'no-cache'}, contains=[
            '"api_version"', '/api/v1/platforms', '/api/v1/news"', '/api/v1/clients"'])
        run.check(client, 'HEAD', '/api/v1/', 200)
        run.check(client, 'GET', '/api/v1/content-types', 200, api=True, contains='"show_icons"', headers=cached)
        run.check(client, 'GET', '/api/v1/content-types/apps', 200, api=True, contains='"Applications"')
        run.check(client, 'GET', '/api/v1/content-types/Apps', 404, api=True, contains='"not_found"',
                  headers={'Cache-Control': 'no-store'})
        run.check(client, 'GET', '/api/v1/platforms', 200, api=True, contains=f'"{platform_id}"', headers=cached)
        run.check(client, 'GET', f'/api/v1/platforms/{platform_id}', 200, api=True, contains='"parent_id"')
        run.check(client, 'GET', '/api/v1/platforms/nope', 404, api=True)
        run.check(client, 'GET', '/api/v1/categories', 200, api=True,
                  contains=['"Utilities"', '"content_count":1'], headers=cached)
        run.check(client, 'GET', f'/api/v1/categories?type=apps&platform={platform_id},{platform_id}', 200,
                  api=True, contains='"Utilities"')
        run.check(client, 'GET', '/api/v1/categories?type=games', 200, api=True, lacks='"Utilities"')
        run.check(client, 'GET', '/api/v1/categories?type=apps&non_empty=false', 200, api=True, contains='"Utilities"')
        run.check(client, 'GET', '/api/v1/categories?type=nope', 400, api=True, contains='"invalid_parameter"')
        run.check(client, 'GET', '/api/v1/categories?platform=nope', 400, api=True, contains='"invalid_parameter"')
        run.check(client, 'GET', '/api/v1/categories?non_empty=yes', 400, api=True, contains='"non_empty"')
        run.check(client, 'GET', f'/api/v1/categories/{category_id}', 200, api=True, contains='"content_count":1')
        run.check(client, 'GET', f'/api/v1/categories/{category_id}?platform={platform_id}', 200, api=True)
        run.check(client, 'GET', '/api/v1/categories/999999', 404, api=True)
        run.check(client, 'GET', '/api/v1/categories/99999999999', 404, api=True)
        run.check(client, 'GET', '/api/v1/categories/abc', 404, api=True)
        hidden_id = ids['hidden_id']
        item = f'/api/v1/content/{content_id}'
        run.check(client, 'GET', '/api/v1/content', 200, api=True, headers={'Cache-Control': 'no-cache'}, contains=[
            TITLE, f'{item}/download', '"external":false', '"size":19', '"total":1', '"total_pages":1'],
            lacks=HIDDEN_TITLE)
        run.check(client, 'GET', '/api/v1/content?page=5&per_page=1', 200, api=True,
                  contains=['"data":[]', '"page":5', '"total":1'])
        run.check(client, 'GET', f'/api/v1/content?type=apps&category={category_id}&platform={platform_id}'
                  '&q=%20smoke%20&uid=0xe0000001&sort=title&order=asc', 200, api=True, contains=TITLE)
        run.check(client, 'GET', '/api/v1/content?q=50%25', 200, api=True, lacks=TITLE)
        run.check(client, 'GET', '/api/v1/content?uid=0xE0000002', 200, api=True, contains='"total":0')
        run.check(client, 'GET', '/api/v1/content?updated_since=2000-01-01T00:00:00Z', 200, api=True, contains=TITLE)
        run.check(client, 'GET', '/api/v1/content?updated_since=2999-01-01T00:00:00%2B02:00', 200, api=True,
                  lacks=TITLE)
        bad_queries = [
            ('updated_since=2000-01-01', 'updated_since'), (f'type=games&category={category_id}', 'category'),
            ('category=999999', 'category'), ('q=%20', 'q'), ('uid=123', 'uid'), ('sort=bogus', 'sort'),
            ('order=1', 'order'), ('page=0', 'page'), ('per_page=51', 'per_page'), ('ids=abc', 'ids'),
            (f'ids={content_id}&type=apps', 'ids'),
        ]
        for query, parameter in bad_queries:
            run.check(client, 'GET', f'/api/v1/content?{query}', 400, api=True,
                      contains=['"invalid_parameter"', f'"parameter":"{parameter}"'])
        run.check(client, 'GET', f'/api/v1/content?ids={content_id},{hidden_id},999999,{content_id}&sort=bogus', 200,
                  api=True, contains=['"total":2', '"per_page":2'], lacks=HIDDEN_TITLE)
        run.check(client, 'GET', item, 200, api=True, headers={'Cache-Control': 'no-cache'}, contains=[
            '"description":"Line one\\nLine two"', '"uid":"0xE0000001"', f'{PREFIX}1.jpg', '"text":"Extra notes"',
            '"url":null', f'{item}/related', f'{item}/rating', '"name":"Applications"'])
        run.check(client, 'GET', f'/api/v1/content/{hidden_id}', 404, api=True, contains='"not_found"')
        run.check(client, 'GET', '/api/v1/content/999999', 404, api=True)
        run.check(client, 'GET', f'{item}/related', 200, api=True, contains=['"data":[]', '"total":0'],
                  headers={'Cache-Control': 'no-store'})
        run.check(client, 'GET', f'{item}/related?limit=21', 400, api=True, contains='"limit"')
        run.check(client, 'GET', f'/api/v1/content/{hidden_id}/related', 404, api=True)
        run.check(client, 'GET', f'{item}/download', 302, location=f'/static/content/files/{PREFIX}.sis',
                  headers={'Cache-Control': 'no-store'})
        run.check(client, 'GET', f'/api/v1/content/{hidden_id}/download', 404, api=True)
        run.check(client, 'GET', f'{item}/rating', 200, api=True, contains=[
            '"average":null', '"count":0', '"rounded":0', '"5":0'])
        run.check(client, 'GET', '/api/v1/news', 200, api=True, headers={'Cache-Control': 'no-cache'}, contains=[
            f'"title":"{NEWS_TITLE}"', '<p>Smoke test news body.</p>', '"total":1', f'/api/v1/news/{news_id}"',
            f'/news/{news_id}"'])
        run.check(client, 'GET', '/api/v1/news?page=3&per_page=1', 200, api=True, contains=['"data":[]', '"total":1'])
        run.check(client, 'GET', '/api/v1/news?per_page=51', 400, api=True, contains='"per_page"')
        run.check(client, 'GET', f'/api/v1/news/{news_id}', 200, api=True, contains=[
            f'"id":{news_id}', '"created_at":"20'])
        run.check(client, 'GET', '/api/v1/news/999999', 404, api=True, contains='"not_found"')
        run.check(client, 'GET', '/api/v1/news/99999999999', 404, api=True)
        with mock.patch.dict(config, {'clients': [hidden_id, 999999, content_id]}):
            run.check(client, 'GET', '/api/v1/clients', 200, api=True, headers={'Cache-Control': 'no-cache'},
                      contains=[TITLE, f'/api/v1/content/{content_id}"'], lacks=[HIDDEN_TITLE, '"meta"'])
        for empty in (None, []):
            with mock.patch.dict(config, {'clients': empty}):
                run.check(client, 'GET', '/api/v1/clients', 200, api=True, contains='{"data":[]}')
        legacy = f'/api/v1/legacy/{LEGACY_PREFIX}'
        run.check(client, 'GET', f'{legacy}/{LEGACY_ID}', 200, api=True, headers={'Cache-Control': 'no-cache'},
                  contains=[f'"content_id":{content_id}', f'"id":{content_id}', TITLE])
        for path in (f'{legacy}/{LEGACY_HIDDEN_ID}', f'{legacy}/1', f'{legacy}/99999999999', f'{legacy}/abc',
                     f'/api/v1/legacy/unknownprefix/{LEGACY_ID}'):
            run.check(client, 'GET', path, 404, api=True, contains='"not_found"', lacks=HIDDEN_TITLE)
        # The legacy blueprint's /<prefix>/<id> also matches /api/<id>; it must still be a JSON 404.
        run.check(client, 'GET', '/api/42', 404, api=True)
        run.check(client, 'POST', '/api/v1/platforms', 405, api=True, contains='"method_not_allowed"')
        run.check(client, 'GET', '/api/v1/no/such/endpoint', 404, api=True)
        run.check(client, 'GET', '/api/v2/', 404, api=True)

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
        run.check(client, 'GET', f'/api/v1/content/{content_id}/rating', 200, api=True, contains=[
            '"average":4.0', '"count":1', '"rounded":4', '"4":1'])
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
