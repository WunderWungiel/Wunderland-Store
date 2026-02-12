from flask import Blueprint, request

from . import database as db

applist = Blueprint("applist", __name__, template_folder="templates")

# Change abc* routes to something that will make your host with this prefix be the same lenght as applist.schumi1331.de
# I.e. applist.schumi1331.de/applist.php [33] is the same as ovi.wunderwungiel.pl/aapplist.php [33]

@applist.route("/aapplist-download.php")
@applist.route("/applist-download.php")
def _applist_download():
    return "0"

@applist.route("/aapplist.php")
@applist.route("/applist.php")
def _applist():
    id = request.args.get("id")
    start = request.args.get("start", type=int)
    latest = request.args.get("latest")
    count = request.args.get("count", type=int)
    search = request.args.get("search")
    widget = request.args.get("widget")
    category = request.args.get("category", type=int)

    if id is not None:
        if id.isdigit():
            id = int(id)
        elif "," in id:
            id = [int(id) for id in id.split(",")]

    if search is None:
        return db.get_content(id=id, start=start, latest=latest, count=count, widget=widget, category=category, content_type="apps")
    else:
        return db.search(search, start=start)

@applist.route("/version.xml")
@applist.route("/aversion.xml")
def _version_xml():
    return db.version()

@applist.route("/changelog.xml")
@applist.route("/achangelog.xml")
def _changelog_xml():
    return db.changelog()
