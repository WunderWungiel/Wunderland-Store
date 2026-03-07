from flask import Blueprint, request

from . import database as db
from . import config

api = Blueprint('api', __name__, template_folder="templates", url_prefix=config['api_prefix'])

@api.route("/get_content/<content_type_name>")
def get_content(content_type_name):

    if not db.get_content_type(content_type_name):
        return {'error': "Wrong content type"}

    id = request.args.get('id', type=int)
    platform = request.args.get('platform')
    platforms = platform.split(",") if platform else None
    category_id = request.args.get('category', type=int)

    arguments = {}

    arguments['content_type_name'] = content_type_name

    if id is not None:
        arguments['id'] = id
    if category_id is not None:
        arguments['category_id'] = category_id
    if platforms is not None:
        arguments['platforms'] = platforms

    results = db.get_content(**arguments).values()

    return sorted(results, key=lambda x: x['id']) if id is None else [results]

@api.route("/get_categories/<content_type_name>")
def get_categories(content_type_name):

    if not db.get_content_type(content_type_name):
        return {'error': "Wrong content type"}

    return db.get_categories(content_type_name=content_type_name)

@api.route("/search/<content_type_name>")
def content_type_search(content_type_name):

    if not db.get_content_type(content_type_name):
        return {'error': "Wrong content type"}

    query = request.args.get('q')
    if not query:
        return {
            'error': "No query provided"
        }
    
    databases = [content_type_name]

    results = db.search(query, databases=databases).values()

    return sorted(results, key=lambda x: x['id'])

@api.route("/get_content_types")
def get_content_types():
    return db.get_content_types()

@api.route("/get_platforms")
def get_platforms():
    return db.get_platforms()

@api.route("/visit/<content_type_name>")
def content_visit(content_type_name):

    if not db.get_content_type(content_type_name):
        return {'error': "Wrong content type"}
    
    id = request.args.get('id', type=int)
    if id is not None:
        db.increment_counter(id, content_type_name)
        return {}
    else:
        return {'error': "No ID Provided"}

@api.route("/search")
def search():
    query = request.args.get('q')
    if not query:
        return {
            'error': "No query provided"
        }
    
    results = db.search(query).values()

    return sorted(results, key=lambda x: x['id'])
