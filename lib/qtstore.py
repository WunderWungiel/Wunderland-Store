"""QtStore compatibility layer"""

import os

from flask import Blueprint, current_app, send_from_directory

from . import qtstore_database as db

qtstore = Blueprint("qtstore", __name__, template_folder="templates")

content_types = ("apps", "games")

@qtstore.route("/StoreData/storeIndex.xml")
def store_index():

    content = db.qtstore_generator()
    return content

@qtstore.route("/StoreData/<content_type>/<app>/descr.txt")
def description(content_type, app):

    content_type = content_type.lower()
    if content_type not in content_types:
        return None

    content = db.qtstore_content(app, content_type)
    return content['description'] if content else None

@qtstore.route("/StoreData/<content_type>/<app>/file.sis")
def file(content_type, app):

    content_type = content_type.lower()
    if content_type not in content_types:
        return None

    content = db.qtstore_content(app, content_type)
    return send_from_directory(os.path.join(current_app.root_path, "static", "files"), content['file']) if content else None

@qtstore.route("/StoreData/<content_type>/<app>/preview.png")
def preview(content_type, app):

    content_type = content_type.lower()
    if content_type not in content_types:
        return None

    content = db.qtstore_content(app, content_type)
    return send_from_directory(os.path.join(current_app.root_path, "static", "store", content_type), content['img']) if content else None