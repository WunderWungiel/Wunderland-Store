import os
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement

from flask import url_for
from psycopg import sql

from .. import database as db
from .. import config

def version():
    root = Element('xml')
    message = Element('message')

    message.text = """Changelog for Wunderland 2.00(1):
*Added Turkish translation"""

    url = Element('url')
    url.text = "http://ovi.wunderwungiel.pl/static/content/files/Wunderland.sis"
    root.append(message)
    root.append(url)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)

def changelog():
    root = Element('xml')
    message = Element('message')

    message.text = """Changelog for Wunderland 2.00(1):
*Added Turkish translation
    
Changelog for Wunderland 2.00(0):
*Initial release based on AppList source code
*Supports all content types
*The categories list is equal to server
*Supports icons, addon files, UIDs, feed
*Most references and strings are migrated to Wunderland
*Icons are migrated
*Unused settings entries are removed
*UID and project name is changed
*Widget appears to be working"""

    url = Element('url')
    root.append(message)
    root.append(url)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)

# !!! Replace right side and comments with YOUR categories' IDs!
applist_to_wunderland = {
    0: (None, 'apps'),  # All apps
    1: (4, 'apps'),  # Camera, photos, videos
    2: (11, 'apps'),  # Emulator
    3: (12, 'apps'),  # Extras
    4: (5, 'apps'),  # File manager & cloud
    5: (7, 'apps'),  # Internet
    6: (8, 'apps'),  # Music
    7: (3, 'apps'),  # Office
    8: (1, 'apps'),  # Other apps
    9: (9, 'apps'),  # Social
    10: (10, 'apps'),  # Tools
    11: (2, 'apps'),  # Weather & GPS
    12: (None, 'games'),  # All games
    13: (2, 'games'),  # Action
    14: (3, 'games'),  # Adventure
    15: (1, 'games'),  # Other games
    16: (6, 'games'),  # Puzzles & cards
    17: (4, 'games'),  # Sports
    18: (5, 'games'),  # Strategy
    19: (1, 'themes')  # Themes
}

# !!! Replace left side and comments with YOUR categories' IDs!
wunderland_to_applist = {
    'apps': {
        None: 0,  # All apps
        4: 1,  # Camera, photos, videos
        11: 2,  # Emulator
        12: 3,  # Extras
        5: 4,  # File manager & cloud
        7: 5,  # Internet
        8: 6,  # Music
        3: 7,  # Office
        1: 8,  # Other apps
        9: 9,  # Social
        10: 10,  # Tools
        2: 11  # Weather & GPS
    },
    'games': {
        None: 12,  # All games
        2: 13,  # Action
        3: 14,  # Adventure
        1: 15,  # Other games
        6: 16,  # Puzzles & cards
        4: 17,  # Sports
        5: 18  # Strategy
    },
    'themes': {
        1: 19  # Themes
    }
}

def format_results(results, content_type_name=None, widget=False):
    root = Element('applist')
    minversion = Element('minversion')
    minversion.text = "1.0.298"
    root.append(minversion)

    for row in results:

        if not content_type_name:
            content_type_name = row['content_type_name']

        content_type = db.get_content_type(content_type_name)

        row = {key: value.strip() if isinstance(value, str) else value for (key, value) in row.items()}

        app = Element('app')

        if widget:
            
            id = SubElement(app, 'id')
            id.text = str(row['id'])
            uid = SubElement(app, 'uid')
            if row['uid']:
                uid.text = row['uid']
            uidstore = SubElement(app, 'uidstore')
            uidunsigned = SubElement(app, 'uidunsigned')
            version = SubElement(app, 'version')
            version.text = row['version']
            versionstore = SubElement(app, 'versionstore')
            versionunsigned = SubElement(app, 'unsigned')
            versiondate = SubElement(app, 'version')
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, 'versiondatestore')
            versiondateunsigned = SubElement(app, 'versiondateunsigned')

        else:

            id = SubElement(app, 'id')
            id.text = str(row['id'])
            name = SubElement(app, 'name')
            name.text = row['title']
            uid = SubElement(app, 'uid')
            if row['uid']:
                uid.text = row['uid']
            uidstore = SubElement(app, 'uidstore')
            uidunsigned = SubElement(app, 'uidunsigned')
            icon = SubElement(app, 'icon')
            icon.text = url_for('static', _external=True, filename=os.path.join("content", "icons", content_type_name, row['img']))
            version = SubElement(app, 'version')
            version.text = row['version']
            versionstore = SubElement(app, 'versionstore')
            versionunsigned = SubElement(app, 'unsigned')
            versiondate = SubElement(app, 'version')
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, 'versiondatestore')
            versiondateunsigned = SubElement(app, 'versiondateunsigned')
            category = SubElement(app, 'category')
            category.text = str(wunderland_to_applist[content_type_name][row['category']])
            language = SubElement(app, 'language')
            language.text = "EN"
            
            os_element = SubElement(app, 'os')
            os_element.text = "5.2,5.3,5.4,5.5"
            developer = SubElement(app, 'developer')
            developer.text = row['publisher']
            mail = SubElement(app, 'mail')
            website = SubElement(app, 'website')
            website.text = url_for('store.item', _external=True, prefix=content_type['prefix'], id=row['id'])
            twitter = SubElement(app, 'twitter')
            facebook = SubElement(app, 'facebook')
            if row['addon_file']:
                facebook.text = url_for('static', _external=True, filename=os.path.join("content", "files", row['addon_file']))
            donation = SubElement(app, 'donation')
            price = SubElement(app, 'price')
            price.text = "0.00"
            description = SubElement(app, 'description')
            if row['description']:
                row['description'].strip()
                description.text = row['description']

            if row['addon_message']:
                description.text += f"\n\nExtra file: {row['addon_message']}"
            image1 = SubElement(app, 'image1')
            image2 = SubElement(app, 'image2')
            image3 = SubElement(app, 'image3')
            image4 = SubElement(app, 'image4')
            image5 = SubElement(app, 'image5')
            if row['image1']:
                image1.text = url_for('static', _external=True, filename=os.path.join("content", "screenshots", content_type_name, row['image1']))
            if row['image2']:
                image2.text = url_for('static', _external=True, filename=os.path.join("content", "screenshots", content_type_name, row['image2']))
            if row['image3']:
                image3.text = url_for('static', _external=True, filename=os.path.join("content", "screenshots", content_type_name, row['image3']))
            if row['image4']:
                image4.text = url_for('static', _external=True, filename=os.path.join("content", "screenshots", content_type_name, row['image4']))
            tags = SubElement(app, 'tags')
            changelog = SubElement(app, 'changelog')
            unsignednote = SubElement(app, 'unsignednote')
            download = SubElement(app, 'download')
            download.text = url_for('static', _external=True, filename=os.path.join("content", "files", row['file']))
            downloadsize = SubElement(app, 'downloadsize')
            downloadsize.text = "0"
            downloadstore = SubElement(app, 'downloadstore')
            downloadunsigned = SubElement(app, 'downloadunsigned')
            downloadunsignedsize = SubElement(app, 'downloadunsignedsize')

        root.append(app)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)

def search(search_query, start=None):

    results = []

    for content_type in db.get_content_types():

        where_clauses = [sql.SQL("visible = true")]
        params = []

        query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(content_type['name']))

        if config['platforms']['applist']:
            query = sql.SQL("""
                WITH RECURSIVE platform_tree AS (
                    SELECT id, parent_id
                    FROM platforms
                    WHERE id = ANY(%s)

                    UNION ALL

                    SELECT parent.id, parent.parent_id
                    FROM platforms parent
                    JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id    
                )
            """) + query
            where_clauses.append(sql.SQL("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)"))
            params.append(config['platforms']['applist'])

        where_clauses.append(sql.SQL("title ILIKE %s"))
        params.append(f"%{search_query}%")

        if start is not None:
            where_clauses.append(sql.SQL("id > %s"))
            params.append(start)
    
        if where_clauses:
            query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)

        with db.connection.cursor() as cursor:
            cursor.execute(query, params)
            content_type_results = cursor.fetchall()

        for i, result in enumerate(content_type_results):
            content_type_results[i]['content_type_name'] = content_type['name']

        results += content_type_results

    xml = format_results(results)

    return xml

def get_content(id=None, category=None, start=None, latest=None, count=None, widget=None, content_type_name=None):
    
    if category is not None:
        new_category, content_type_name = applist_to_wunderland.get(category) or (None, 'apps')
    else:
        new_category = None

    where_clauses = [sql.SQL("visible = true")]
    params = []

    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(content_type_name))

    if config['platforms']['applist']:
        query = sql.SQL("""
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id
                FROM platforms
                WHERE id = ANY(%s)

                UNION ALL

                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree AS current_platform ON parent.id = current_platform.parent_id    
            )
        """) + query
        where_clauses.append(sql.SQL("(platform IN (SELECT id FROM platform_tree) OR platform IS NULL)"))
        params.append(config['platforms']['applist'])

    if new_category is not None:
        where_clauses.append(sql.SQL("category = %s"))
        params.append(new_category)

    if id is not None:
        if isinstance(id, int):
            where_clauses.append(sql.SQL("id = %s"))
        elif isinstance(id, list) and id:
            where_clauses.append(sql.SQL("id = ANY(%s)"))
        params.append(id) # Append regardless of type

    if start is not None:
        where_clauses.append(sql.SQL("id > %s"))
        params.append(start)

    if where_clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)

    query += sql.SQL(" ORDER BY id DESC")

    if latest is not None and count is not None:
        query += sql.SQL(" LIMIT %s")
        params.append(count)

    with db.connection.cursor() as cursor:
        cursor.execute(query, params)
        results = cursor.fetchall()

    xml = format_results(results, content_type_name, widget)
    return xml
