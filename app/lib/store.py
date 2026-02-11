import os
import random
import math

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, abort

from . import database as db
from . import config
from .auth.routes import is_logged

store = Blueprint("store", __name__, template_folder="templates")

@store.route("/app/<int:id>/rate", methods=["GET", "POST"])
def _app_rate(id):
    if request.method == "GET":
        return _rate_form(id, "apps")
    else:
        return rate(id, "apps")


@store.route("/game/<int:id>/rate", methods=["GET", "POST"])
def _game_rate(id):
    if request.method == "GET":
        return _rate_form(id, "games")
    else:
        return rate(id, "games")


@store.route("/theme/<int:id>/rate", methods=["GET", "POST"])
def _theme_rate(id):
    if request.method == "GET":
        return _rate_form(id, "themes")
    else:
        return rate(id, "themes")


def _rate_form(id, content_type):

    prefixes = {
        "apps": "app",
        "games": "game",
        "themes": "theme"
    }

    if not db.get_content(id=id, content_type=content_type):
        return redirect(url_for(f"._{prefixes[content_type]}", id=id))

    if not is_logged():
        return redirect(url_for(f"store._{prefixes[content_type]}", id=id))
    
    app = db.get_content(id=id, content_type=content_type)
    return render_template("rate.html", app=app, prefixes=prefixes)


def rate(id, content_type):

    prefixes = {
        "apps": "app",
        "games": "game",
        "themes": "theme"
    }

    if not db.get_content(id=id, content_type=content_type):
        return redirect(url_for(f"store._{prefixes[content_type]}", id=id))

    if not is_logged():
        return redirect(url_for(f"store._{prefixes[content_type]}", id=id))
    rating = request.form.get("rating")
    if not rating:
        return redirect(url_for(f"store._{prefixes[content_type]}", id=id))
    
    db.rate(rating, user_id=session['id'], content_id=id, content_type=content_type)
    return redirect(url_for(f"store._{prefixes[content_type]}", id=id))


@store.route("/app/<int:id>")
def _app(id):
    return _item_page(id, content_type="apps")


@store.route("/game/<int:id>")
def _game(id):
    return _item_page(id, content_type="games")


@store.route("/theme/<int:id>")
def _theme(id):
    return _item_page(id, content_type="themes")


def _item_page(id, content_type):

    app = db.get_content(id=id, content_type=content_type)

    if app and ((is_logged() and session['username'] not in config['admin_usernames']) or not is_logged()):
        db.increment_counter(id, content_type)

    if not app:
        return redirect(f"/{content_type}")

    try:
        app['size'] = round(
            os.stat(
                os.path.join(current_app.root_path, 'static', 'content', 'files', app['file'])
            ).st_size / (1024 * 1024), 2)
    except FileNotFoundError:
        app['size'] = 0

    recommended = db.get_content(
        content_type=content_type,
        category_id=app['category_id'],
        platform_id=session['platform']
    )

    if recommended:
        recommended = list(recommended.values())
        recommended = random.choices(recommended, k=10)
        recommended = [dict(t) for t in {tuple(d.items()) for d in recommended}]
        recommended = [d for d in recommended if d['id'] != app['id']]
        if not recommended:
            recommended = None
    else:
        recommended = None

    app['description'] = app['description'].replace("\n", "<br>") if app['description'] else None
    app['addon_message'] = app['addon_message'].replace("\n", "<br>") if app['addon_message'] else None

    if content_type == "apps":
        template = "app_page.html"
    elif content_type == "games":
        template = "game_page.html"
    elif content_type == "themes":
        template = "theme_page.html"
    else:
        return redirect("news._root")

    return render_template(template, app=app, recommended=recommended)


@store.route("/app/<int:id>/images")
def _app_images(id):
    return _item_images(id, "apps")


@store.route("/game/<int:id>/images")
def _game_images(id):
    return _item_images(id, "games")


@store.route("/theme/<int:id>/images")
def _theme_images(id):
    return _item_images(id, "themes")


def _item_images(id, content_type):
    app = db.get_content(id=id, content_type=content_type)

    screenshots = [image for image in (app['image1'], app['image2'], app['image3'], app['image4']) if image]
    if not len(screenshots) > 0:
        if type == "apps":
            url = f"/app/{id}/"
        elif content_type == "games":
            url = f"/game/{id}/"
        elif content_type == "themes":
            url = f"/theme/{id}/"
        else:
            abort(400)

        return redirect(url)

    app['screenshots'] = [image for image in (app['image1'], app['image2'], app['image3'], app['image4']) if image]
    return render_template("app_images.html", app=app, content_type=content_type)


@store.route("/apps/browse")
def _apps_browse():
    categories = db.get_categories("apps")
    return render_template("apps_browse.html", categories=categories)


@store.route("/games/browse")
def _games_browse():
    categories = db.get_categories("games")
    return render_template("games_browse.html", categories=categories)


@store.route("/themes/browse")
def _themes_browse():
    categories = db.get_categories("themes")
    return render_template("themes_browse.html", categories=categories)


@store.route("/search")
def _search():

    query = request.args.get('q')
    if not query:
        return render_template("search.html")
    
    results = db.search(query, platform_id=session['platform'])

    if not results:
        return render_template("apps_empty.html", category=None)
    
    page_id = request.args.get('page', default=1, type=int)
    per_page = 10
    total_pages = max(1, math.ceil(len(results) / per_page))

    if page_id < 1 or page_id > total_pages:
        return redirect(url_for("._search", q=query, page=1))

    ids = list(results.keys())

    first_index = (page_id - 1) * per_page
    last_index = first_index + per_page

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    apps_to_show = [results[id] for id in ids[first_index:last_index]]

    return render_template(
        "search.html",
        results=apps_to_show,
        search_query=query,
        next_page=next_page,
        previous_page=previous_page
    )


@store.route("/platform")
def _platform():
    platforms = db.get_platforms()
    return render_template("platform.html", platforms=platforms)


@store.route("/set_platform")
def _set_platform():
    platform = request.args.get('platform')
    if platform is None:
        session['platform'] = None
        session.permanent = True
        return redirect(url_for("news._root"))
    elif not platform:
        return redirect(url_for("news._root"))
    elif not db.get_platform(platform):
        return redirect(url_for("news._root"))
    
    session['platform'] = platform
    session.permanent = True

    return redirect(url_for("news._root"))

@store.route("/<content_type>")
def _content_type(content_type):
    if content_type in config['content_types']:
        return _content(content_type)

def _content(content_type):

    category_id = request.args.get('category_id', default=1, type=int)

    category = db.get_category(category_id, content_type) if category_id else None

    if category_id and not category:
        return redirect(url_for("._content_type", content_type=content_type))

    all_apps = db.get_content(category_id=category_id, content_type=content_type, platform_id=session['platform'])
    if not all_apps:
        return render_template(f"{content_type}_empty.html", category=category)
    
    page_id = request.args.get('page', default=1, type=int)
    per_page = 10
    total_pages = max(1, math.ceil(len(all_apps) / per_page))

    if page_id < 1 or page_id > total_pages:
        arguments = {'page': 1}
        if category_id:
            arguments['category_id'] = category_id
        return redirect(url_for('._content_type', content_type=content_type, **arguments))

    ids = list(all_apps.keys())

    first_index = (page_id - 1) * per_page
    last_index = first_index + per_page

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    apps_to_show = [all_apps[app_id] for app_id in ids[first_index:last_index]]

    return render_template(
        f'{content_type}.html',
        apps=apps_to_show,
        category=category,
        category_id=category_id,
        next_page=next_page,
        previous_page=previous_page
    )
