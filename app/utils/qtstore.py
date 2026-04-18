import os
import time

from flask import Blueprint, current_app, request, send_file, abort, url_for

from . import database as db
from . import config

qtstore = Blueprint('qtstore', __name__, template_folder="templates")

def generate_content(content_type_id, content_name):

    content = ""

    results, total = db.get_content(content_type_id=content_type_id, platforms=config['platforms']['qtstore'])

    for row in results:

        path = os.path.join(current_app.static_folder, "content", "files", row['file'])

        try:
            timestamp = int(os.path.getmtime(path))
        except FileNotFoundError:
            timestamp = time.time()

        name, extension = os.path.splitext(row['file'])

        content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[descr.txt]\n"
        if extension in (".sis", ".sisx"):
            content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[file.sis]\n"
        else:
            content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[file{extension}]\n"
        content += f"{request.scheme}://{request.host}/StoreData/{content_name}/{row['title']}/{timestamp}[preview.png]\n"

    return content

def get_content(name, content_type_id):

    results, total = db.get_content(content_type_id=content_type_id, search=name, limit=1)
    content = results[0] if results else None

    if content:
        content['description'] = content['description'].replace("\n", "<br>") if content['description'] else None
        content['addon_text'] = content['addon_text'].replace("\n", "<br>") if content['addon_text'] else None
        return content
    else:
        return None


@qtstore.route("/StoreData/storeIndex.xml")
def index():
    content = generate_content("apps", "Apps")
    content += generate_content("games", "Games")
    content += generate_content("themes", "Themes")

    return content

@qtstore.route("/StoreData/<content_type_id>/<name>/descr.txt")
def description(content_type_id, name):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = get_content(name, content_type['id'])
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
