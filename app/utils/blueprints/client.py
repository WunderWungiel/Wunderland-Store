import os
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement

from flask import Blueprint, current_app, request, url_for, send_from_directory

from .. import db
from .. import config

client = Blueprint('client', __name__, template_folder="templates")


def resolve_client_id(client_id):
    if client_id == 0:
        return None, 'apps'
    if client_id == 12:
        return None, 'games'

    with db.pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, type_id FROM categories WHERE client_id = %s", (client_id))
            row = cursor.fetchone()
            if row:
                return row['id'], row['type_id']

    return None, 'apps'


def get_client_id_mapping():
    categories = db.get_categories()
    mapping = {category['id']: category['client_id'] for category in categories if category.get('client_id')}
    mapping[('all', 'apps')] = 0
    mapping[('all', 'games')] = 12
    return mapping


def format_results(results, content_type_id=None, widget=False):
    root = Element('client')
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
            versiondate = SubElement(app, 'versiondate')
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
            icon.text = url_for('static', _external=True, filename=os.path.join("content", "icons", row['icon']))
            version = SubElement(app, 'version')
            version.text = row['version']
            versionstore = SubElement(app, 'versionstore')
            versionunsigned = SubElement(app, 'unsigned')
            versiondate = SubElement(app, 'versiondate')
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, 'versiondatestore')
            versiondateunsigned = SubElement(app, 'versiondateunsigned')

            client_id = mapping.get(row['category_id'])
            if client_id is None:
                client_id = mapping.get(('all', content_type_id), 0)

            category = SubElement(app, 'category')
            category.text = str(client_id)
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
                facebook.text = url_for('static', _external=True, filename=os.path.join(
                    "content", "files", row['addon_file']))
            donation = SubElement(app, 'donation')
            price = SubElement(app, 'price')
            price.text = "0.00"
            description = SubElement(app, 'description')
            if row['description']:
                description.text = row['description'].strip()

            if row['addon_text']:
                description.text += f"\n\nExtra file: {row['addon_text']}"

            screenshots = [f"{row['screenshot_prefix']}{i}.jpg" for i in range(1, row['screenshot_count'] + 1)]

            for i in range(5):  # 5 - 1
                image = SubElement(app, f'image{i + 1}')
                if len(screenshots) >= i + 1:
                    image.text = url_for(
                        'static', _external=True, filename=os.path.join("content", "screenshots", screenshots[i])
                    )

            tags = SubElement(app, 'tags')
            changelog = SubElement(app, 'changelog')
            unsignednote = SubElement(app, 'unsignednote')
            download = SubElement(app, 'download')
            download.text = url_for('static', _external=True, filename=os.path.join("content", "files", row['file']))
            downloadsize = SubElement(app, 'downloadsize')

            file_path = os.path.join(current_app.static_folder, "content", "files", row['file'])
            if os.path.isfile(file_path):
                downloadsize.text = str(os.path.getsize(file_path))
            else:
                downloadsize.text = "0"

            downloadstore = SubElement(app, 'downloadstore')
            downloadunsigned = SubElement(app, 'downloadunsigned')
            downloadunsignedsize = SubElement(app, 'downloadunsignedsize')

        root.append(app)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)


def search(query, start=None):

    results = []
    all_results, total = db.get_content(search=query, platforms=config['platforms']['client'], start=start)

    for result in all_results:
        result['category_id'] = result['category']['id']
        result['content_type_id'] = result['category']['type_id']
        results.append(result)

    return format_results(results)


def get_content(content_ids=None, category=None, start=None, widget=None, count=None, content_type_id=None):

    category_id, content_type_id = resolve_client_id(category) if category is not None else (None, content_type_id or 'apps')

    if content_ids is None:
        results, total = db.get_content(
            content_type_id=content_type_id,
            category_id=category_id,
            platforms=config['platforms']['client'],
            start=start,
            limit=count
        )
    else:
        results = []
        for content_id in content_ids:
            result = db.get_item(content_id=content_id)
            if result:
                results.append(result)

    for i, result in enumerate(results):
        result['category_id'] = result['category']['id']
        result['content_type_id'] = result['category']['type_id']
        results[i] = result

    return format_results(results, content_type_id, widget)


@client.route("/applist-download.php")
def applist_download():
    return "0"


@client.route("/applist.php")
def php():
    content_ids = request.args.get('id')
    start = request.args.get('start', type=int)
    count = request.args.get('count', type=int)
    query = request.args.get('search')
    widget = request.args.get('widget', type=bool)
    category = request.args.get('category', type=int)

    if content_ids:
        content_ids = [int(content_id) for content_id in content_ids.split(",") if content_id.isdecimal()]
    else:
        content_ids = None

    if not query:
        return get_content(content_ids=content_ids, category=category, start=start, widget=widget, count=count, content_type_id="apps")
    else:
        return search(query=query, start=start)


@client.route("/version.xml")
def version():
    return send_from_directory(current_app.static_folder, os.path.join("client", "version.xml"))


@client.route("/changelog.xml")
def changelog():
    return send_from_directory(current_app.static_folder, os.path.join("client", "changelog.xml"))
