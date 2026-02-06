import os

from flask import Blueprint, current_app, send_from_directory, request

from . import qtstore_database as db

qtstore = Blueprint("qtstore", __name__, template_folder="templates")

content_types = ("apps", "games", "themes")


@qtstore.route("/StoreData/storeIndex.xml")
def store_index():

    content = db.qtstore_generator()
    return content


@qtstore.route("/StoreData/<content_type>/<app>/descr.txt")
def description(content_type, app):

    content_type = content_type.lower()
    if content_type not in content_types:
        return ""

    content = db.qtstore_content(app, content_type)
    if not content:
        return ""

    description = content['description']
    if not description:
        description = ""

    if len(content['screenshots']) > 0:
        description += "<br><br>"
        for i, screenshot in enumerate(content['screenshots'], start=1):
            path = f"http://{request.host}/static/content/screenshots/{content_type}/{screenshot}"
            description += f'''<img src="{path}" alt="image{i}" width="150"><br><br>'''

    if content['addon_message']:
        description += f"<br><br>Extra file: {content['addon_message']}"
    if content['addon_file']:
        description += f'''<br><br>Link: http://{request.host}/static/content/files/{content['addon_file']}'''

    return description


@qtstore.route("/StoreData/<content_type>/<app>/file<ext>")
def file(content_type, app, ext):

    content_type = content_type.lower()
    if content_type not in content_types:
        return ""

    content = db.qtstore_content(app, content_type)
    return send_from_directory(os.path.join(current_app.root_path, "static", "content", "files"), content['file']) if content else None


@qtstore.route("/StoreData/<content_type>/<app>/preview.png")
def preview(content_type, app):

    content_type = content_type.lower()
    if content_type not in content_types:
        return ""

    content = db.qtstore_content(app, content_type)
    return send_from_directory(os.path.join(current_app.root_path, "static", "content", "store", content_type), content['img']) if content else None
