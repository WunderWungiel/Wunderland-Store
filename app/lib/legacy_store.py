from flask import Blueprint, request, redirect, url_for

from . import database as db

legacy_store = Blueprint('legacy_store', __name__, template_folder="templates")

@legacy_store.route("/<prefix>/<int:legacy_id>/rate", methods=['GET', 'POST'])
def rate(prefix, legacy_id):

    content_types = db.get_content_types(prefix=prefix)
    content_type = content_types[0] if content_types else None
    content_id = db.get_legacy_content_id(legacy_id, content_type['id'])

    if not content_id:
        return redirect(url_for('store.root'))

    return redirect(url_for('store.rate', content_id=content_id, **request.args), code=307)

@legacy_store.route("/<prefix>/<int:legacy_id>")
def item(prefix, legacy_id):

    content_types = db.get_content_type(prefix=prefix)
    content_type = content_types[0] if content_types else None
    content_id = db.get_legacy_content_id(legacy_id, content_type['id'])

    if not content_id:
        return redirect(url_for('store.root'))

    return redirect(url_for('store.item', content_id=content_id, **request.args), code=307) # TODO

@legacy_store.route("/<prefix>/<int:legacy_id>/images")
def images(prefix, legacy_id):

    content_types = db.get_content_types(prefix=prefix)
    content_type = content_types[0] if content_types else None
    content_id = db.get_legacy_content_id(legacy_id, content_type['id'])

    if not content_id:
        return redirect(url_for('store.root'))

    return redirect(url_for('store.images', content_id=content_id, **request.args), code=307) # TODO
