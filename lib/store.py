import os
import random
import math

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

from . import database as db
from .auth import session_logout, is_logged

store = Blueprint("store", __name__, template_folder="templates")

@store.before_request
def check_platform_id():
    platformId = session.get('platformId')
    platformName = session.get('platformName')

    if not platformId or not platformName:
        session['platformId'] = "all"
        session['platformName'] = "All"
        session.permanent = True

    usernameId = session.get('id')
    if not usernameId:
        session_logout()
        return
    else:
        user = db.account_system.get_user(id=usernameId)
        if user['banned']:
            session_logout()
            return render_template('auth/banned.html', reason=user['banned_reason'])

@store.route("/api/rate")
def _api_rate():
    username = request.args.get("username")
    rating = request.args.get("rating")
    content_id = request.args.get("content_id")
    content_type = request.args.get("content_type")

    if not username or not rating or not content_id or not content_type:
        return {}
    else:
        if session['username'] != username:
            return {}
    
    user_id = db.account_system.get_user_id(username=username)
    db.rate(int(rating), user_id, content_id, content_type)
    
    rating = db.get_rating(content_id, content_type)
    return {'rating': rating}

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

    prefixes = {
        "apps": "applications",
        "games": "games",
        "themes": "themes"
    }

    app = db.get_content(id=id, content_type=content_type)

    if not app:
        return redirect(f"/{prefixes[content_type]}")
    
    try:
        app['size'] = round(os.stat(os.path.join(current_app.root_path, 'static', 'files', app['file'])).st_size / (1024 * 1024), 2)
    except FileNotFoundError:
        app['size'] = 0

    recommended = list(db.get_content(content_type=content_type, categoryId=app['category_id'], platformId=session['platformId']).values())
    recommended = random.choices(recommended, k=10)
    # recommended = [dict((k, tuple(v)) if isinstance(v, list) else (k, v) for k, v in d.items()) for d in recommended] # Can convert lists to tuples automatically
    recommended = [dict(t) for t in {tuple(d.items()) for d in recommended}]
    recommended = [d for d in recommended if d['id'] != app['id']]
    if not recommended:
        recommended = None

    if content_type == "apps":
        template = "app_page.html"
    elif content_type == "games":
        template = "game_page.html"
    elif content_type == "themes":
        template = "theme_page.html"

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

        return redirect(url)

    app['screenshots'] = [image for image in (app['image1'], app['image2'], app['image3'], app['image4']) if image]
    return render_template("app_images.html", app=app, content_type=content_type)

@store.route("/applications/browse")
def _applications_browse():
    categories = db.get_categories("apps")
    return render_template("applications_browse.html", categories=categories)

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
    
    results = db.search(query, ("apps", "games", "themes"))

    pageId = request.args.get('pageId')

    if not pageId:
        pageId = 1
    else:
        pageId = int(pageId)
    
    if (pageId * 10) > math.ceil(len(results) / 10) * 10:
        if pageId != 1:
            return redirect(url_for("._search", q=query, pageId=1))
        else:
            return render_template("applications_empty.html", category=None)
    else:
        if ((pageId + 1) * 10) < math.ceil(len(results) / 10) * 10:
            if pageId != 1:
                next_page = pageId + 1
            else:
                next_page = None
            if pageId != math.ceil(len(results) / 10):
                previous_page = pageId - 1
            else:
                previous_page = None
        else:
            next_page = None
            previous_page = None
    
    first_index = pageId - 1
    last_index = first_index + 10

    ids = list(results.keys())
    apps_to_show = ids[first_index:last_index]
    apps_to_show = [results[id] for id in apps_to_show]

    if not results:
        return ""
    else:
        return render_template("search.html", results=apps_to_show, search_query=query, next_page=next_page, previous_page=previous_page)

@store.route("/platform_chooser")
def _platform_chooser():

    platforms = db.get_platforms()
    return render_template("platform_chooser.html", platforms=platforms)

@store.route("/set_platform")
def _set_platform():
    platformId = request.args.get('platformId')
    if not platformId:
        return redirect(url_for("._root"))
    elif platformId == "all":
        session['platformId'] = "all"
        session['platformName'] = "All"
        session.permanent = True
        return redirect(url_for("._root"))
    elif not db.get_platform_name(platformId):
        return redirect(url_for("._root"))
    
    session['platformId'] = platformId
    session['platformName'] = db.get_platform_name(platformId)
    session.permanent = True

    return redirect(url_for("._root"))

@store.route("/applications")
def _applications():
    return _content("apps")

@store.route("/games")
def _games():
    return _content("games")

@store.route("/themes")
def _themes():
    return _content("themes")

def _content(content_type):

    prefixes = {
        "apps": "applications",
        "games": "games",
        "themes": "themes"
    }
    
    content_type_prefix = prefixes.get(content_type)

    categoryId = request.args.get('categoryId')
    category_name = db.get_category_name(categoryId, content_type) if categoryId else None
    
    try:
        all_apps = db.get_content(categoryId=categoryId, content_type=content_type, platformId=session['platformId'])
    except db.WrongCategoryError:
        return redirect(f"/{content_type_prefix}/")


    if not all_apps:
        return render_template(f"{content_type_prefix}_empty.html")
    pageId = request.args.get('pageId')

    if not pageId:
        pageId = 1
    else:
        pageId = int(pageId)
    
    if (pageId * 10) > math.ceil(len(all_apps) / 10) * 10:
        if pageId != 1:
            if categoryId:
                return redirect(f"/{content_type_prefix}/?pageId=1&categoryId={categoryId}")
            else:
                return redirect(f"/{content_type_prefix}/?pageId=1")
        else:
            if categoryId:
                return render_template(f"{content_type_prefix}_empty.html", category=category_name)
            else:
                return render_template(f"{content_type_prefix}_empty.html", category=None)
    else:
        if ((pageId + 1) * 10) <= math.ceil(len(all_apps) / 10) * 10:
            if pageId != math.ceil(len(all_apps) / 10):
                next_page = pageId + 1
            else:
                next_page = None
        else:
            next_page = None
        
        if pageId != 1:
            previous_page = pageId - 1
        else:
            previous_page = None
    
    if pageId == 1:
        first_index = 0
    else:
        first_index = (pageId * 10) - 10
    
    last_index = first_index + 10

    ids = list(all_apps.keys())
    apps_to_show = ids[first_index:last_index]
    apps_to_show = [all_apps[id] for id in apps_to_show]

    if not categoryId:
        return render_template(f'{content_type_prefix}.html', apps=apps_to_show, category=None, category_id=categoryId, next_page=next_page, previous_page=previous_page)
    else:
        return render_template(f'{content_type_prefix}.html', apps=apps_to_show, category=category_name, category_id=categoryId, next_page=next_page, previous_page=previous_page)

@store.route("/")
def __root():
    return redirect("/home/")

@store.route("/home")
def _root():

    apps = db.get_content(content_type="apps", platformId=session["platformId"])
    if not apps:
        return render_template("applications_empty.html")
    pageId = request.args.get('pageId')

    if not pageId:
        pageId = 1
    else:
        pageId = int(pageId)
    
    if (pageId * 10) > math.ceil(len(apps) / 10) * 10:
        if pageId != 1:
            return redirect(f"/search/?pageId=1")
    else:
        if ((pageId + 1) * 10) < math.ceil(len(apps) / 10) * 10:
            if pageId != 1:
                next_page = pageId + 1
            else:
                next_page = None
            if pageId != math.ceil(len(apps) / 10):
                previous_page = pageId - 1
            else:
                previous_page = None
        else:
            next_page = None
            previous_page = None
    
    first_index = pageId - 1
    last_index = first_index + 10

    ids = list(apps.keys())
    apps_to_show = ids[first_index:last_index]
    apps_to_show = [apps[id] for id in apps_to_show]
    
    return render_template("index.html", apps=apps_to_show, next_page=next_page, previous_page=previous_page)