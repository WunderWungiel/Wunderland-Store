"""nnhub compatibility layer."""

import os
import json

from flask import Blueprint, request, abort, current_app, send_from_directory

from . import database as db
from . import nnhub_database as nndb

nnhub = Blueprint("nnhub", __name__, template_folder="templates")

@nnhub.route("/nns/<int:id>/default.png")
def _icon(id):

    id, content_type = nndb.id_nnhub_to_wunderland(id)
    app = db.get_content(id=id, content_type=content_type)

    return send_from_directory(os.path.join(current_app.static_folder, "store"), app["img"])

@nnhub.route("/nns/categories.php")
def _categories():
    
    response = current_app.response_class(response=json.dumps(nndb.nnhub_categories(), ensure_ascii=False), mimetype='application/json')
    return response

@nnhub.route("/nns/catalog_apps.json")
def _catalog_apps():
    
    response = current_app.response_class(response=json.dumps(nndb.nnhub_catalog_apps(), ensure_ascii=False), mimetype='application/json')
    return response
    
@nnhub.route("/nns/catalog.php")
def _catalog():
    
    body = []
    c = request.args.get("c")

    if c:
        categories = nndb.nnhub_categories()
        if c.isnumeric():
            if c not in categories[0]: abort(400)
            content = nndb.nnhub_many_contents(content_type="apps", category_id=int(c))
        else:
            content = nndb.nnhub_many_contents(content_type=c)

        response = current_app.response_class(response=json.dumps(content, ensure_ascii=False), mimetype='application/json')
        return response

    else:

        body = []

        catalog = nndb.nnhub_catalog_apps()
        catalog = catalog[:10]
        for id in catalog:
            app = nndb.nnhub_content(int(id))
            if not app:
                continue
            app.pop("screenshots")
            body.append(app)

        response = current_app.response_class(response=json.dumps(body, ensure_ascii=False), mimetype='application/json')
        return response


@nnhub.route("/nns/app.php")
def _app():
    id = request.args.get("id")

    if not id: abort(400)
    if "/" in id or "\\" in id or "." in id: abort(400)

    app = nndb.nnhub_content(id)
    response = current_app.response_class(response=json.dumps(app, ensure_ascii=False), mimetype='application/json')
    return response