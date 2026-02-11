import os

from flask import Blueprint, current_app, send_file, request, abort

from .. import config
from . import database as db

qtstore = Blueprint("qtstore", __name__, template_folder="templates")

@qtstore.route("/StoreData/storeIndex.xml")
def index():
    return db.index()

@qtstore.route("/StoreData/<content_type>/<app>/descr.txt")
def description(content_type, app):

    content_type = content_type.lower()
    if content_type not in config['content_types']:
        abort(404)

    content = db.get_content(app, content_type)
    if not content:
        return abort(404)

    description = content['description']
    if not description:
        description = ""

    if len(content['screenshots']) > 0:
        if description:
            description += "<br><br>"
        for i, screenshot in enumerate(content['screenshots'], start=1):
            path = f"http://{request.host}/static/content/screenshots/{content_type}/{screenshot}"
            description += f'<img src="{path}" alt="image{i}" width="150"><br><br>'

    if content['addon_message']:
        description += f"<br><br>Extra file: {content['addon_message']}"
    if content['addon_file']:
        description += f"<br><br>Link: http://{request.host}/static/content/files/{content['addon_file']}"

    return description

@qtstore.route("/StoreData/<content_type>/<app>/file<ext>")
def file(content_type, app, ext):

    content_type = content_type.lower()
    if content_type not in config['content_types']:
        abort(404)

    content = db.get_content(app, content_type)
    path = os.path.join(current_app.root_path, "static", "content", "files", content['file'])

    if content and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)

@qtstore.route("/StoreData/<content_type>/<app>/preview.png")
def preview(content_type, app):

    content_type = content_type.lower()
    if content_type not in config['content_types']:
        return ""

    content = db.get_content(app, content_type)
    path = os.path.join(current_app.root_path, "static", "content", "icons", content_type, content['img'])

    if content and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)
