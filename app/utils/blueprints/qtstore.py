import os
import time
from urllib.parse import quote, urlparse

from flask import Blueprint, current_app, request, send_file, abort, redirect, url_for
from markupsafe import Markup

from .. import db
from .. import config
from .. import utils

qtstore = Blueprint('qtstore', __name__, template_folder="templates")


def generate_content(content_type_id, content_name):

    content = ""

    results, total = db.get_content(content_type_id=content_type_id, platforms=config['platforms']['qtstore'])

    for row in results:

        if row['latest_url']:
            timestamp = int(row['updated_at'].timestamp())
            name, extension = os.path.splitext(urlparse(row['latest_url']).path)
        else:
            try:
                timestamp = int(os.path.getmtime(utils.get_file_path(row)))
            except FileNotFoundError:
                timestamp = time.time()

            name, extension = os.path.splitext(row['file'])

        base = f"{request.scheme}://{request.host}/StoreData/{content_name}/{quote(row['title'], safe='')}/{timestamp}"

        content += f"{base}[descr.txt]\n"
        if extension in (".sis", ".sisx"):
            content += f"{base}[file.sis]\n"
        else:
            content += f"{base}[file{extension}]\n"
        content += f"{base}[preview.png]\n"

    return content


def get_content(name, content_type_id):

    print(name, content_type_id)

    results, total = db.get_content(
        content_type_id=content_type_id,
        title=name,
        platforms=config['platforms']['qtstore'],
        limit=1
    )
    content = results[0] if results else None

    if content:
        content['description'] = utils.nl2br(content['description']) or None
        content['addon_text'] = utils.nl2br(content['addon_text']) or None
        return content
    else:
        return None


@qtstore.route("/StoreData/storeIndex.xml")
def index():
    content = generate_content("apps", "Apps")
    content += generate_content("games", "Games")
    content += generate_content("themes", "Themes")

    return content


@qtstore.route("/StoreData/<content_type_id>/<path:name>/descr.txt")
def description(content_type_id, name):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = get_content(name, content_type['id'])
    if not content:
        return abort(404)

    description = content['description'] or Markup("")

    if len(content['screenshots']) > 0:
        if description:
            description += Markup("<br><br>")
        for i, screenshot in enumerate(content['screenshots'], start=1):
            path = url_for('static', _external=True, filename=os.path.join("content", "screenshots", screenshot))
            description += Markup('<img src="{}" alt="screenshot{}" width="150"><br><br>').format(path, i)

    if content['addon_text']:
        description += Markup("<br><br>Extra file: {}").format(content['addon_text'])
    if content['addon_file']:
        path = url_for('static', _external=True, filename=os.path.join("content", "files", content['addon_file']))
        description += Markup("<br><br>Link: {}").format(path)

    return description


@qtstore.route("/StoreData/<content_type_id>/<path:name>/file<ext>")
def file(content_type_id, name, ext):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = get_content(name, content_type['id'])
    if not content:
        abort(404)

    if content['latest_url']:
        return redirect(content['latest_url'])

    path = utils.get_file_path(content)
    if path and os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)


@qtstore.route("/StoreData/<content_type_id>/<path:name>/preview.png")
def preview(content_type_id, name):

    content_type = db.get_content_type_by_id(content_type_id.lower())
    if not content_type:
        abort(404)

    content = get_content(name, content_type['id'])
    if not content:
        abort(404)

    path = os.path.join(current_app.root_path, "static", "content", "icons", content['icon'])
    if os.path.isfile(path):
        return send_file(path)
    else:
        abort(404)
