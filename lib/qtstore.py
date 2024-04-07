"""QTStore compatibility layer"""

import os

from flask import Blueprint, redirect, request, send_from_directory

from . import qtstore_database as db

qtstore = Blueprint("qtstore", __name__, template_folder="templates")

@qtstore.route("/StoreData/storeIndex.xml")
def store_index():

    content = db.qtstore_generator()
    return content

@qtstore.route("/StoreData/Apps/<app>/descr.txt")
def description(app):

    content = db.qtstore_content(app, "apps")
    return content['description'] if content else None

@qtstore.route("/StoreData/Apps/<app>/file.html")
def file(app):

    content = db.qtstore_content(app, "apps")
    # return redirect(f'http://{request.host}/static/files/{content['file']}') if content else None
    return f''''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{content['title']}</title>
    <meta http-equiv="Refresh" content="0; url='http://{request.host}/static/files/{content['file']}'" />
</head>
<body>
    
</body>
</html>
''' if content else None

@qtstore.route("/StoreData/Apps/<app>/preview.png")
def preview(app):

    content = db.qtstore_content(app, "apps")
    return send_from_directory("static/store/apps", content['img']) # Can't use redirect here, it works bad with the app.