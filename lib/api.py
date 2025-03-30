from flask import Blueprint,request

from . import database as db

api = Blueprint("api", __name__, template_folder="templates")

content_types = ["applications", "games", "themes"]

@api.route("/api/v1/<content_type>/get_content")
def _get_content(content_type):

    if content_type not in content_types:
        return {
            "error": "Wrong content type"
        }
    
    if content_type == "applications":
        content_type = "apps"

    id = request.args.get("id")
    platform_id = request.args.get("platformId")
    category_id = request.args.get("categoryId")

    arguments = {}

    arguments["content_type"] = content_type

    if id and id.isnumeric():
        arguments["id"] = id
    if platform_id:
        arguments["platform_id"] = platform_id
    if category_id:
        arguments["category_id"] = category_id
    
    results = db.get_content(**arguments)

    return sorted(results.values(), key=lambda x: x["id"]) if not "id" in arguments else [results,]

@api.route("/api/v1/<content_type>/get_categories")
def _get_categories(content_type):

    if content_type not in content_types:
        return {
            "error": "Wrong content type"
        }
    
    if content_type == "applications":
        content_type = "apps"

    results = db.get_categories(content_type=content_type)
    return [{"id": result[0], "name": result[1]} for result in results]

@api.route("/api/v1/<content_type>/search")
def _content_type_search(content_type):

    if content_type not in content_types:
        return {
            "error": "Wrong content type"
        }
    
    if content_type == "applications":
        content_type = "apps"

    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query, databases=(content_type,))
    return sorted(results.values(), key=lambda x: x["id"])

@api.route("/api/v1/get_content_types")
def _get_content_types():
    return content_types

@api.route("/api/v1/search")
def _search():
    query = request.args.get('q')
    if not query:
        return {
            "error": "No query provided"
        }
    
    results = db.search(query)
    return sorted(results.values(), key=lambda x: x["id"])
