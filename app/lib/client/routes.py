from flask import Blueprint, request

from . import database as db

client = Blueprint('client', __name__, template_folder="templates")

@client.route("/applist-download.php")
def applist_download():
    return "0"

@client.route("/applist.php")
def php():
    id = request.args.get('id')
    start = request.args.get('start', type=int)
    latest = request.args.get('latest')
    count = request.args.get('count', type=int)
    search = request.args.get('search')
    widget = request.args.get('widget')
    category = request.args.get('category', type=int)

    if id:
        id = [int(id) for id in id.split(",") if id.isdecimal()]
    else:
        id = None

    if not search:
        return db.get_content(id=id, start=start, latest=latest, count=count, widget=widget, category=category, content_type_id="apps")
    else:
        return db.search(search, start=start)

@client.route("/version.xml")
def version():
    return db.version()

@client.route("/changelog.xml")
def changelog():
    return db.changelog()
