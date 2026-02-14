import os
import random
import math
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, abort

from . import database as db
from .auth import database as auth_db
from . import config

store = Blueprint('store', __name__, template_folder="templates")

@store.route("/<prefix>/<int:id>/rate", methods=['GET', 'POST'])
def item_rate(prefix, id):

    content_type = db.get_content_type(prefix=prefix)
    if not content_type:
        return redirect(url_for('.root'))
    
    if request.method == 'GET':
        return rate_form(id, content_type['name'])
    else:
        return rate(id, content_type['name'])

def rate_form(id, content_type):

    prefix = db.get_content_type(prefix=prefix)['prefix']

    if not db.get_content(id=id, content_type=content_type) or not session.get('logged_in'):
        return redirect(url_for('.item', prefix=prefix, id=id))
    
    app = db.get_content(id=id, content_type=content_type)
    return render_template("rate.html", app=app, prefix=prefix)

def rate(id, content_type):

    if not db.get_content(id=id, content_type=content_type) or not session.get('logged_in'):
        return redirect(url_for('.item', prefix=config['content_types'][content_type]['prefix'], id=id))

    rating = request.form.get('rating')
    if not rating:
        return redirect(url_for('.item', prefix=config['content_types'][content_type]['prefix'], id=id))
    
    db.rate(rating, user_id=session['user_id'], content_id=id, content_type=content_type)
    return redirect(url_for('.item', prefix=config['content_types'][content_type]['prefix'], id=id))

@store.route("/<prefix>/<int:id>")
def item(prefix, id):

    content_type = db.get_content_type(prefix=prefix)
    if not content_type:
        return redirect(url_for('.root'))

    return item_page(id, content_type['name'])
        
def item_page(id, content_type):

    app = db.get_content(id=id, content_type=content_type)

    if app and ((session.get('logged_in') and auth_db.get_user(session['user_id'])['username'] not in config['admin_usernames']) or not session.get('logged_in')):
        db.increment_counter(id, content_type)

    if not app:
        return redirect(url_for('.content_type', content_type=content_type))

    try:
        app['size'] = os.stat(os.path.join(current_app.root_path, 'static', 'content', 'files', app['file'])).st_size
    except FileNotFoundError:
        app['size'] = 0

    recommended = db.get_content(content_type=content_type, category_id=app['category_id'], platform_id=session['platform'])

    if recommended:
        recommended = random.choices(list(recommended.values()), k=10)
        recommended = [dict(t) for t in {tuple(d.items()) for d in recommended}]
        recommended = [d for d in recommended if d['id'] != app['id']]
        if not recommended:
            recommended = None
    else:
        recommended = None

    app['description'] = app['description'].replace("\n", "<br>") if app['description'] else None
    app['addon_message'] = app['addon_message'].replace("\n", "<br>") if app['addon_message'] else None

    return render_template("item_page.html", app=app, recommended=recommended, content_type=db.get_content_type(content_type))

@store.route("/<prefix>/<int:id>/images")
def item_images(prefix, id):

    content_type = db.get_content_type(prefix=prefix)
    if not content_type:
        return redirect(url_for('.root'))

    return item_images_page(id, content_type['name'])

def item_images_page(id, content_type):
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
    return render_template("item_images.html", app=app, content_type=db.get_content_type(content_type))

@store.route("/<content_type>/browse")
def content_type_browse(content_type):
    categories = db.get_categories(content_type)
    return render_template(f"{content_type}_browse.html", categories=categories)

@store.route("/search")
def search():

    query = request.args.get('q')
    if not query:
        return render_template("search.html")
    
    results = db.search(query, platform_id=session['platform'])

    if not results:
        return render_template("content_type_empty.html", category=None, content_type=db.get_content_type('apps'))
    
    page_id = request.args.get('page', default=1, type=int)
    per_page = 10
    total_pages = max(1, math.ceil(len(results) / per_page))

    if page_id < 1 or page_id > total_pages:
        return redirect(url_for('.search', q=query, page=1))

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
def platform():
    platforms = db.get_platforms()
    return render_template("platform.html", platforms=platforms)

@store.route("/set_platform")
def set_platform():
    platform = request.args.get('platform')
    if platform is None:
        session['platform'] = None
        session.permanent = True
        return redirect(url_for('.root'))
    elif not platform:
        return redirect(url_for('.root'))
    elif not db.get_platform(platform):
        return redirect(url_for('.root'))
    
    session['platform'] = platform
    session.permanent = True

    return redirect(url_for('.root'))

@store.route("/<content_type>")
def content_type(content_type):

    if db.get_content_type(name=content_type):
        return content(content_type)
    else:
        return redirect(url_for('.root'))

def content(content_type):

    category_id = request.args.get('category_id')
    category_id = int(category_id) if category_id else None

    category = db.get_category(category_id, content_type) if category_id else None

    if category_id and not category:
        return redirect(url_for('.content_type', content_type=content_type))

    all_apps = db.get_content(category_id=category_id, content_type=content_type, platform_id=session['platform'])
    if not all_apps:
        return render_template(f"content_type_empty.html", category=category, content_type=db.get_content_type(content_type))
    
    page_id = request.args.get('page', default=1, type=int)
    per_page = 10
    total_pages = max(1, math.ceil(len(all_apps) / per_page))

    if page_id < 1 or page_id > total_pages:
        arguments = {'page': 1}
        if category_id:
            arguments['category_id'] = category_id
        return redirect(url_for('.content_type', content_type=content_type, **arguments))

    ids = list(all_apps.keys())

    first_index = (page_id - 1) * per_page
    last_index = first_index + per_page

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    apps_to_show = [all_apps[app_id] for app_id in ids[first_index:last_index]]

    return render_template(
        f"content_type.html",
        apps=apps_to_show,
        category=category,
        category_id=category_id,
        next_page=next_page,
        previous_page=previous_page,
        content_type=db.get_content_type(content_type)
    )

@store.route("/feed.xml")
def feed():

    now = datetime.now()
    now_string = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    news = db.get_news()

    xml = f"""<?xml version="1.0" encoding="windows-1252"?>
<rssversion="2.0">
    <channel>
        <title>Wunderland Store</title>
        <description>News, content and programs for retro devices.</description>
        <link>http://ovi.wunderwungiel.pl/</link>
        <lastBuildDate>{now_string}</lastBuildDate>"""
    
    for content in news:
        xml += f"""
        <item>
            <title>{content['title']}</title>
            <link>{url_for('.news', _external=True, news_id=content['id'])}</link>
            <description></description>
            <pubDate>{content['date']}</pubDate>
            <guid>{url_for('.news', _external=True, news_id=content['id'])}</guid>
        </item>"""

    xml += """
    </channel>
</rss>"""

    return xml

@store.route("/news/<int:news_id>")
def news(news_id):

    content = db.get_news(news_id=news_id)[0]

    return render_template("news.html", title=content['title'], content=content['content'], share=True)

@store.route("/")
def _root():

    return redirect(url_for('.root'))

@store.route("/home")
def root():

    news = db.get_news()
    if not news:
        return render_template("index.html", news=[], next_page=None, previous_page=None)
    
    page_id = request.args.get('page', default=1, type=int)
    per_page = 10
    total_pages = max(1, math.ceil(len(news) / per_page))

    if page_id < 1 or page_id > total_pages:
        return redirect(url_for('.root', page=1))

    first_index = (page_id - 1) * per_page
    last_index = first_index + per_page

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    news_to_show = news[first_index:last_index]
    
    return render_template("index.html", news=news_to_show, next_page=next_page, previous_page=previous_page)
