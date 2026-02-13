from flask import Blueprint,request

from . import database as db
from . import config

api = Blueprint("api", __name__, template_folder="templates", url_prefix=config['api_prefix'])

@api.route("/<content_type>/get_content")
def _get_content(content_type):

    if content_type not in config['content_types']:
        return {"error": "Wrong content type"}

    id = request.args.get("id")
    platform = request.args.get("platform")
    platforms = platform.split(",") if platform else None
    category_id = request.args.get("category_id")

    arguments = {}

    arguments['content_type'] = content_type

    if id and id.isnumeric():
        arguments['id'] = id
    if category_id:
        arguments['category_id'] = category_id

    if platforms:
        results = []
        for platform in platforms:
            arguments['platform'] = platform
            results += db.get_content(**arguments).values()
        results = [dict(t) for t in {tuple(d.items()) for d in results}]
    else:
        results = db.get_content(**arguments).values()

    return sorted(results, key=lambda x: x['id']) if not "id" in arguments else [results]

@api.route("/<content_type>/get_categories")
def _get_categories(content_type):

    if content_type not in config['content_types']:
        return {"error": "Wrong content type"}

    results = db.get_categories(content_type=content_type)
    return [{"id": result[0], "name": result[1]} for result in results]

@api.route("/<content_type>/search")
def _content_type_search(content_type):

    if content_type not in config['content_types']:
        return {"error": "Wrong content type"}

    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query, databases=(content_type,))
    return sorted(results.values(), key=lambda x: x['id'])

@api.route("/get_content_types")
def _get_content_types():
    return config['content_types']

@api.route("/get_platforms")
def _get_platforms():
    return db.get_platforms()

@api.route("/<content_type>/content_visit")
def _content_visit(content_type):

    if content_type not in config['content_types']:
        return {"error": "Wrong content type"}
    
    id = request.args.get("id")
    if id and id.isnumeric():
        db.increment_counter(id, content_type)
        return {}
    else:
        return {
            "error": "No ID Provided"
        }

@api.route("/search")
def _search():
    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query)
    return sorted(results.values(), key=lambda x: x['id'])
