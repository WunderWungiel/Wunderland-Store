from flask import current_app, Blueprint, request

from . import database as db

api = Blueprint("api", __name__, template_folder="templates")

@api.route("/api/v1/<content_type>/get_content")
def _get_content(content_type):
    results = db.get_content(content_type=content_type)
    return sorted(results.values(), key=lambda x: x["id"])


@api.route("/api/v1/<content_type>/get_categories")
def _get_categories(content_type):
    results = db.get_categories(content_type=content_type)
    return [{"id": result[0], "name": result[1]} for result in results]

@api.route("/api/v1/<content_type>/search")
def _content_type_search(content_type):
    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query, databases=(content_type,))
    return sorted(results.values(), key=lambda x: x["id"])

@api.route("/api/v1/search")
def _search():
    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query)
    return sorted(results.values(), key=lambda x: x["id"])