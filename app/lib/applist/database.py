import os
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement

from flask import url_for, current_app, send_from_directory
from psycopg import sql

from .. import database as db
from .. import config

def version():
    return send_from_directory(current_app.static_folder, os.path.join("applist", "version.xml"))

def changelog():
    return send_from_directory(current_app.static_folder, os.path.join("applist", "changelog.xml"))

def resolve_client_id(client_id):
    if client_id == 0:
        return None, 'apps'
    if client_id == 12:
        return None, 'games'

    with db.pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, type_id FROM categories WHERE client_id = %s", [client_id])
            row = cursor.fetchone()
            if row:
                return row['id'], row['type_id']

    return None, 'apps'

def get_client_id_mapping():
    categories = db.get_categories()
    mapping = {category['id']: category['client_id'] for category in categories if category.get('client_id') is not None}
    mapping[('all', 'apps')] = 0
    mapping[('all', 'games')] = 12
    return mapping

def format_results(results, content_type_id=None, widget=False):
    root = Element('applist')
    minversion = Element('minversion')
    minversion.text = "1.0.298"
    root.append(minversion)

    mapping = get_client_id_mapping()

    for row in results:

        if not content_type_id:
            content_type_id = row['content_type_id']

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
            icon.text = url_for('static', _external=True, filename=os.path.join("content", "icons", content_type_id, row['icon']))
            version = SubElement(app, 'version')
            version.text = row['version']
            versionstore = SubElement(app, 'versionstore')
            versionunsigned = SubElement(app, 'unsigned')
            versiondate = SubElement(app, 'version')
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, 'versiondatestore')
            versiondateunsigned = SubElement(app, 'versiondateunsigned')
            
            applist_id = mapping.get(row['category_id'])
            if applist_id is None:
                applist_id = mapping.get(('all', content_type_id), 0)
                
            category = SubElement(app, 'category')
            category.text = str(applist_id)
            language = SubElement(app, 'language')
            language.text = "EN"

            os_element = SubElement(app, 'os')
            os_element.text = "5.2,5.3,5.4,5.5"
            developer = SubElement(app, 'developer')
            developer.text = row['publisher']
            mail = SubElement(app, 'mail')
            website = SubElement(app, 'website')
            website.text = url_for('store.item', _external=True, content_id=row['id'])
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

            if row['addon_text']:
                description.text += f"\n\nExtra file: {row['addon_text']}"

            screenshots = [f"{row['screenshot_prefix']}{i}.jpg" for i in range(1, row['screenshot_count'] + 1)]

            for i in range(5): # 5 - 1
                image = SubElement(app, f'image{i + 1}')
                if len(screenshots) >= i + 1:
                    image.text = url_for('static', _external=True, filename=os.path.join("content", "screenshots", content_type_id, screenshots[i]))
                    print("")

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
    all_results, _ = db.search(search_query)
    
    for result in all_results:
        result['category_id'] = result['category']['id']
        result['content_type_id'] = result['category']['type_id']
        results.append(result)

    if start is not None:
        results = [result for result in results if result['id'] > start]

    return format_results(results)

def get_content(id=None, category=None, start=None, latest=None, count=None, widget=None, content_type_id=None):

    category_id, content_type_id = resolve_client_id(category) if category is not None else (None, content_type_id or 'apps')

    where_clauses = ["content.visible = true"]
    params = []

    query = """
        SELECT content.*, categories.type_id as content_type_id
        FROM content
        JOIN categories ON content.category_id = categories.id
    """

    if config['platforms']['applist']:
        query = """
            WITH RECURSIVE platform_tree AS (
                SELECT id, parent_id FROM platforms WHERE id = ANY(%s)
                UNION ALL
                SELECT parent.id, parent.parent_id
                FROM platforms parent
                JOIN platform_tree ON parent.id = platform_tree.parent_id
            )
        """ + query
        where_clauses.append("(platform_id IN (SELECT id FROM platform_tree) OR platform_id IS NULL)")
        params.append(config['platforms']['applist'])

    if content_type_id:
        if content_type_id in [content_type['id'] for content_type in db.get_content_types()]:
            content_type_filter = content_type_id
        else:
            content_type_filter = 'apps'
        
        where_clauses.append("categories.type_id = %s")
        params.append(content_type_filter)

    if category_id is not None:
        where_clauses.append("category_id = %s")
        params.append(category_id)

    if id is not None:
        if isinstance(id, int): id = [id]
        where_clauses.append("content.id = ANY(%s)")
        params.append(id)

    if start is not None:
        where_clauses.append("content.id > %s")
        params.append(start)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY content.id DESC"

    if latest is not None and count is not None:
        query += " LIMIT %s"
        params.append(count)

    with db.pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()

    return format_results(results, content_type_id, widget)
