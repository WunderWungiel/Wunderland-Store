from flask import Blueprint, request

from . import applist_database as db

applist = Blueprint("applist", __name__, template_folder="templates")

@applist.route("/abcapplist-download.php")
@applist.route("/applist-download.php")
def _applist_download():
    return "0"

@applist.route("/abcapplist.php")
@applist.route("/applist.php")
def _applist():
    id = request.args.get("id")
    start = request.args.get("start")
    latest = request.args.get("latest")
    count = request.args.get("count")
    search = request.args.get("search")
    widget = request.args.get("widget")
    category = request.args.get("category")

    return db.get_content(id=id, start=start, latest=latest, count=count, search=search, widget=widget, category=category, content_type="apps")

@applist.route("/version.xml")
@applist.route("/abcversion.xml")
def _version_xml():
    return db.version()

@applist.route("/changelog.xml")
@applist.route("/abcchangelog.xml")
def _changelog_xml():
    return db.changelog()