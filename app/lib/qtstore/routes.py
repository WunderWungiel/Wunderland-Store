import os

from flask import Blueprint, current_app, send_file, abort, url_for

from . import database as db
from .. import config
from ..database import get_content_type

qtstore = Blueprint('qtstore', __name__, template_folder="templates")

@qtstore.route("/StoreData/storeIndex.xml")
def index():
    return db.index()

@qtstore.route("/StoreData/<content_type_name>/<app>/descr.txt")
def description(content_type_name, app):

    content_type = get_content_type(content_type_name.lower())
    if not content_type:
        abort(404)

    content = db.get_content(app, content_type_name)
    if not content:
        return abort(404)

    description = content['description']
    if not description:
        description = ""

    if len(content['screenshots']) > 0:
        if description:
            description += "<br><br>"
        for i, screenshot in enumerate(content['screenshots'], start=1):
            path = url_for('static', _external=True, filename=os.path.join("content", "screenshots", content_type_name, screenshot))
            description += f'<img src="{path}" alt="image{i}" width="150"><br><br>'

    if content['addon_message']:
        description += f"<br><br>Extra file: {content['addon_message']}"
    if content['addon_file']:
        path = url_for('static', _external=True, filename=os.path.join("content", "files", content['addon_file']))
        description += f"<br><br>Link: {path}"

    return description

@qtstore.route("/StoreData/<content_type_name>/<app>/file<ext>")
def file(content_type_name, app, ext):

    content_type = get_content_type(content_type_name.lower())
    if not content_type:
        abort(404)

    content = db.get_content(app, content_type_name)
    path = os.path.join(current_app.root_path, "static", "content", "files", content['file'])

    if content and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)

@qtstore.route("/StoreData/<content_type_name>/<app>/preview.png")
def preview(content_type_name, app):

    content_type = get_content_type(content_type_name.lower())
    if not content_type:
        abort(404)

    content = db.get_content(app, content_type_name)
    path = os.path.join(current_app.root_path, "static", "content", "icons", content_type_name, content['img'])

    if content and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)
