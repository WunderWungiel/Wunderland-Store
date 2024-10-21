import os
import random
import math
import shutil
import json

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, abort
from werkzeug.utils import secure_filename

from . import database as db
from . import auth_database as auth_db
from . import config
from .auth import session_logout, is_logged
from .email import send_email

store = Blueprint("store", __name__, template_folder="templates")


@store.before_request
def check_platform_id():
    platform_id = session.get('platformId')
    platform_name = session.get('platformName')

    if not platform_id or not platform_name:
        session['platformId'] = "all"
        session['platformName'] = "All"
        session.permanent = True

    username_id = session.get('id')
    if not username_id:
        session_logout()
        return
    else:
        user = auth_db.get_user(id=username_id)
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
    
    user_id = auth_db.get_user_id(username=username)
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

    if app and ((is_logged() and session['username'] != config['ADMIN_USERNAME']) or not is_logged()):
        db.increment_counter(id, content_type)

    if not app:
        return redirect(f"/{prefixes[content_type]}")
    
    try:
        app['size'] = round(
            os.stat(
                os.path.join(current_app.root_path, 'static', 'files', app['file'])
            ).st_size / (1024 * 1024), 2)
    except FileNotFoundError:
        app['size'] = 0

    recommended = db.get_content(
        content_type=content_type,
        category_id=app['category_id'],
        platform_id=session['platformId']
    )

    if recommended:
        recommended = list(recommended.values())
        recommended = random.choices(recommended, k=10)

        # recommended = [dict((k, tuple(v)) if isinstance(v, list) else (k, v) for k, v in d.items()) for d in recommended] # Can convert lists to tuples automatically

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
        abort(400)

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

    page_id = request.args.get('pageId', default=1, type=int)

    total_pages = math.ceil(len(results) / 10)

    if page_id < 1 or page_id > total_pages:
        return redirect(url_for("._search", q=query, pageId=1))

    if len(results) == 0:
        return render_template("applications_empty.html", category=None)

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    first_index = page_id - 1
    last_index = first_index + 10

    ids = list(results.keys())
    apps_to_show = ids[first_index:last_index]
    apps_to_show = [results[id] for id in apps_to_show]

    if not results:
        return ""
    else:
        return render_template(
            "search.html",
            results=apps_to_show,
            search_query=query,
            next_page=next_page,
            previous_page=previous_page
        )


@store.route("/platform_chooser")
def _platform_chooser():

    platforms = db.get_platforms()
    return render_template("platform_chooser.html", platforms=platforms)


@store.route("/set_platform")
def _set_platform():
    platform_id = request.args.get('platformId')
    if not platform_id:
        return redirect(url_for("news._root"))
    elif platform_id == "all":
        session['platformId'] = "all"
        session['platformName'] = "All"
        session.permanent = True
        return redirect(url_for("news._root"))
    elif not db.get_platform_name(platform_id):
        return redirect(url_for("news._root"))
    
    session['platformId'] = platform_id
    session['platformName'] = db.get_platform_name(platform_id)
    session.permanent = True

    return redirect(url_for("news._root"))


@store.route("/<content_type>/upload", methods=["GET", "POST"])
def _upload(content_type):

    if not is_logged():
        return redirect("/")

    image_extensions = ["png", "jpg", "jpeg"]
    file_extensions = ["sis", "sisx", "zip", "jar"]

    def clear_path():
        if os.path.isdir(path):
            shutil.rmtree(path)

    if content_type not in ("applications", "games", "themes"):
        return redirect("/")
    
    if content_type == "applications":
        content_type = "apps"

    categories = db.get_categories(content_type)

    if request.method == "GET":
        return render_template("upload_form.html", categories=categories)
    elif request.method == "POST":

        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        publisher = request.form.get("publisher")
        version = request.form.get("version")
        platform = request.form.get("platform")
        file = request.files.get('file')
        addonfile = request.files.get('addonfile')
        addonmessage = request.files.get('addonmessage')
        icon = request.files.get('icon')
        screenshots = request.files.getlist('screenshots')

        for item in (title, description, category, publisher, version, platform, file, icon, screenshots):
            if not item:
                clear_path()
                return redirect(request.url)
                        
        if platform not in ("s60v2", "s60v3", "s60", "all" "ngage2") or category not in [str(category[0]) for category in categories]:
            clear_path()
            return redirect(request.url)
        
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], secure_filename(title))
        if not os.path.isdir(path):
            os.makedirs(path)
        
        app = {
            "content_type": content_type,
            "title": title,
            "description": description,
            "category": category,
            "version": version,
            "publisher": publisher,
            "platform": platform,
            "file": None,
            "addonfile": None,
            "addonmessage": addonmessage if addonmessage else None,
            "icon": None,
            "screenshot1": None,
            "screenshot2": None,
            "screenshot3": None,
            "screenshot4": None
        }
        
        file_extension = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        if file_extension not in file_extensions:
            clear_path()
            return redirect(request.url)
        file.save(os.path.join(path, f"file.{file_extension}"))
        
        app["file"] = f"file.{file_extension}"

        if addonfile:
            addonfile_extension = secure_filename(addonfile.filename).rsplit('.', 1)
            if len(addonfile_extension) > 0:
                addonfile_extension = addonfile_extension[1].lower() 
                if addonfile_extension not in file_extensions:
                    clear_path()    
                    return redirect(request.url)
                addonfile.save(os.path.join(path, f"addonfile.{addonfile_extension}"))
                app["addonfile"] = f"addonfile.{file_extension}"

        icon_extension = secure_filename(icon.filename).rsplit('.', 1)[1].lower()
        if icon_extension not in image_extensions:
            clear_path()
            return redirect(request.url)
        icon.save(os.path.join(path, "icon." + icon_extension))
        app["icon"] = "icon." + icon_extension

        for i, screenshot in enumerate(screenshots, start=1):
            screenshot_extension = secure_filename(screenshot.filename).rsplit('.', 1)[1].lower()
            if screenshot_extension not in screenshot_extension:
                return redirect(request.url)
            screenshot.save(os.path.join(path, f"screenshot{i}.{screenshot_extension}"))
            if i == 1:
                app["screenshot1"] = f"screenshot1.{screenshot_extension}"
            elif i == 2:
                app["screenshot2"] = f"screenshot2.{screenshot_extension}"
            elif i == 3:
                app["screenshot3"] = f"screenshot3.{screenshot_extension}"
            elif i == 4:
                app["screenshot4"] = f"screenshot4.{screenshot_extension}"

            if i > 4:
                break

        with open(os.path.join(path, "app.json"), "w") as f:
            json.dump(app, f)

        text_message = f"New content! Title: \"{title}\""
        send_email("New content", text_message, text_message, "me@wunderwungiel.pl")

        return "Uploaded"


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

    category_id = request.args.get('categoryId')
    category_id = int(category_id) if category_id else None
    category_name = db.get_category_name(category_id, content_type) if category_id else None

    if category_id and not category_name:
        return redirect(f"/{content_type_prefix}/")

    all_apps = db.get_content(category_id=category_id, content_type=content_type, platform_id=session['platformId'])        

    if not all_apps:
        return render_template(f"{content_type_prefix}_empty.html", category=category_name)
    page_id = request.args.get('pageId', default=1, type=int)

    total_pages = math.ceil(len(all_apps) / 10)

    if page_id < 1 or page_id > total_pages:
        redirect_url = f"/{content_type_prefix}/?pageId=1"
        if category_id:
            redirect_url += f"&categoryId={category_id}"
        return redirect(redirect_url)

    if len(all_apps) == 0:
        return render_template(f"{content_type_prefix}_empty.html", category=category_name)

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    first_index = (page_id - 1) * 10
    last_index = first_index + 10

    ids = list(all_apps.keys())
    apps_to_show = ids[first_index:last_index]
    apps_to_show = [all_apps[app_id] for app_id in apps_to_show]

    return render_template(
        f'{content_type_prefix}.html',
        apps=apps_to_show,
        category=category_name,
        category_id=category_id,
        next_page=next_page,
        previous_page=previous_page
    )
