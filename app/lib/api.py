from flask import Blueprint, request

from . import database as db
from . import config

api = Blueprint('api', __name__, template_folder="templates", url_prefix=config['api_prefix'])

@api.route("/get_content/<content_type_name>")
def get_content(content_type_name):

    if not db.get_content_type(content_type_name):
        return {"error": "Wrong content type"}

    id = request.args.get('id')
    platform = request.args.get('platform')
    platforms = platform.split(",") if platform else None
    category_id = request.args.get('category_id')

    arguments = {}

    arguments['content_type'] = content_type_name

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

@api.route("/get_categories/<content_type_name>")
def get_categories(content_type_name):

    if not db.get_content_type(content_type_name):
        return {"error": "Wrong content type"}

    return db.get_categories(content_type_name=content_type_name)

@api.route("/search/<content_type_name>")
def content_type_search(content_type_name):

    if not db.get_content_type(content_type_name):
        return {"error": "Wrong content type"}

    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query, databases=(content_type_name,))
    return sorted(results.values(), key=lambda x: x['id'])

@api.route("/get_content_types")
def get_content_types():
    return db.get_content_types()

@api.route("/get_platforms")
def get_platforms():
    return db.get_platforms()

@api.route("/visit/<content_type_name>")
def content_visit(content_type_name):

    if not db.get_content_type(content_type_name):
        return {"error": "Wrong content type"}
    
    id = request.args.get('id')
    if id and id.isnumeric():
        db.increment_counter(id, content_type_name)
        return {}
    else:
        return {
            "error": "No ID Provided"
        }

@api.route("/search")
def search():
    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query)
    return sorted(results.values(), key=lambda x: x['id'])
