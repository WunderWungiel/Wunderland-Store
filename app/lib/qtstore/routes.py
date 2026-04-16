import os

from flask import Blueprint, current_app, send_file, abort, url_for

from . import database as db

qtstore = Blueprint('qtstore', __name__, template_folder="templates")

@qtstore.route("/StoreData/storeIndex.xml")
def index():
    return db.index()

@qtstore.route("/StoreData/<content_type_id>/<app>/descr.txt")
def description(content_type_id, app):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = db.get_content(app, content_type['id'])
    if not content:
        return abort(404)

    description = content['description']
    if not description:
        description = ""

    if len(content['screenshots']) > 0:
        if description:
            description += "<br><br>"
        for i, screenshot in enumerate(content['screenshots'], start=1):
            path = url_for('static', _external=True, filename=os.path.join("content", "screenshots", screenshot))
            description += f'<img src="{path}" alt="screenshot{i}" width="150"><br><br>'

    if content['addon_text']:
        description += f"<br><br>Extra file: {content['addon_text']}"
    if content['addon_file']:
        path = url_for('static', _external=True, filename=os.path.join("content", "files", content['addon_file']))
        description += f"<br><br>Link: {path}"

    return description

@qtstore.route("/StoreData/<content_type_id>/<app>/file<ext>")
def file(content_type_id, app, ext):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = db.get_content(app, content_type['id'])
    path = os.path.join(current_app.root_path, "static", "content", "files", content['file'])

    if content and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)

@qtstore.route("/StoreData/<content_type_id>/<app>/preview.png")
def preview(content_type_id, app):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = db.get_content(app, content_type['id'])
    path = os.path.join(current_app.root_path, "static", "content", "icons", content['icon'])

    if content and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)
