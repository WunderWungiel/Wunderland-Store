import json

from flask import request

from . import database as db


def id_nnhub_to_wunderland(id):

    apps_length = db.get_content_number("apps")
    games_length = db.get_content_number("games")
    themes_length = db.get_content_number("themes")

    content_type = None

    if id <= apps_length:
        content_type = "apps"
    elif id <= (apps_length + games_length):
        id = id - apps_length
        content_type = "games"
    elif id <= (apps_length + games_length + themes_length):
        id = id - apps_length - games_length
        content_type = "themes"
    else:
        return None

    return id, content_type


def id_wunderland_to_nnhub(id, content_type):

    apps_length = db.get_content_number("apps")
    games_length = db.get_content_number("games")

    if content_type == "apps":
        return id
    elif content_type == "games":
        return apps_length + id
    elif content_type == "themes":
        return apps_length + games_length + id
    
    return id


def nnhub_catalog_apps():
    
    apps_ids = db.get_content_type_ids("apps")
    apps_ids = [str(id_wunderland_to_nnhub(id, "apps")) for id in apps_ids]
    games_ids = db.get_content_type_ids("games")
    games_ids = [str(id_wunderland_to_nnhub(id, "games")) for id in games_ids]
    themes_ids = db.get_content_type_ids("themes")
    themes_ids = [str(id_wunderland_to_nnhub(id, "themes")) for id in themes_ids]

    return apps_ids + games_ids + themes_ids


def nnhub_content(id):

    id = int(id)
    id, content_type = id_nnhub_to_wunderland(id)
    
    app = db.get_content(id, content_type=content_type)

    body = {
        "id": str(id),
        "suite": app["title"],
        "vendor": app["publisher"],
        "uid": app["uid"],
        "last": app["version"],
        "type": 1 if app["platform"] in ["s60v3", "s60"] else 0,

        "dl": f"http://{request.host}/static/files/{app['file']}",
        "description": app["description"]
    }

    screenshots = []
    if app.get("image1"):
        screenshots.append(["1.jpg", "1.jpg"])
    if app.get("image2"):
        screenshots.append(["2.jpg", "2.jpg"])
    if app.get("image3"):
        screenshots.append(["3.jpg", "3.jpg"])
    if app.get("image4"):
        screenshots.append(["4.jpg", "4.jpg"])
    
    body["screenshots"] = screenshots
    return body


def nnhub_many_contents(content_type, category_id=None):

    new_content = []
    content = db.get_content(content_type=content_type, category_id=category_id)
    for app in content.values():
        app["id"] = str(id_wunderland_to_nnhub(app["id"], content_type))

        body = {
            "id": app["id"],
            "suite": app["title"],
            "vendor": app["publisher"],
            "uid": app["uid"],
            "last": app["version"],
            "type": 1 if app["platform"] in ["s60v3", "s60"] else 0,

            "dl": f"http://{request.host}/static/files/{app['file']}",
            "description": app["description"]
        }

        new_content.append(body)
    
    return new_content


def nnhub_categories():

    body = []
    categories = db.get_categories("apps")
    categories_ids = [str(result[0]) for result in categories]

    body.append(categories_ids + ["games", "themes"])
    body.append({"nnmidlets":{"name": "nnproject MIDlets"}, "sympatches": {"sym": True, "name": "Symbian Patches", "name": {
        "en": "Symbian Patches",
        "ru": "Симбиан патчи"
    }}})
    for category in categories:
        body[1][str(category[0])] = {"name": category[1]}
    body[1]["games"] = {"name": "Games"}
    body[1]["themes"] = {"name": "Themes"}
    
    return body