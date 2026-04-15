import os
import random
import math
from datetime import datetime

from flask import Blueprint, current_app, g, request, session, flash, redirect, render_template, url_for

from . import config
from . import database as db
from . import utils
from .auth import database as auth_db

store = Blueprint('store', __name__, template_folder="templates")

@store.route("/content/<int:content_id>/rate", methods=['GET', 'POST'])
def rate(content_id):

    item = db.get_item(content_id)

    if not item or not g.user:
        return redirect(url_for('.item', content_id=content_id))

    if request.method == 'GET':
        return render_template("rate.html", item=item)

    rating = request.form.get('rating')
    if not rating:
        return redirect(url_for('.item', content_id=content_id))

    db.rate(rating, content_id=content_id, user_id=session['user_id'])
    return redirect(url_for('.item', content_id=content_id))


@store.route("/item/<int:content_id>")
def item(content_id):

    item = db.get_item(content_id=content_id)

    if not item:
        return redirect(url_for('.root'))

    if (g.user and g.user['role'] != 'admin') or not g.user:
        db.increment_counter(content_id)

    file_path = os.path.join(current_app.root_path, 'static', 'content', 'files', item['file'])
    item['size'] = os.path.getsize(file_path) if os.path.isfile(file_path) else 0

    platform_id = session.get('platform_id')
    recommended, _ = db.get_content(content_type_id=item['category']['type_id'], category_id=item['category']['id'], platforms=[platform_id] if platform_id else None)

    recommended = [d for d in recommended if d['id'] != item['id']] if recommended else []
    recommended = random.sample(recommended, k=min(10, len(recommended))) or None

    item['description'] = item['description'].replace("\n", "<br>") if item['description'] else None
    item['addon_text'] = item['addon_text'].replace("\n", "<br>") if item['addon_text'] else None

    return render_template("item.html", item=item, recommended=recommended)


@store.route("/content/<int:content_id>/images")
def images(content_id):

    item = db.get_item(content_id)

    if not item:
        return redirect(url_for('.root'))

    if not item['screenshots']:
        return redirect(url_for('.item', content_id=content_id))

    return render_template("images.html", item=item)


@store.route("/content/<content_type_id>/browse")
def browse_categories(content_type_id):

    content_type = db.get_content_type_by_id(content_type_id)

    if not content_type:
        return redirect(url_for('.root'))

    categories = db.get_categories(content_type_id=content_type['id'], platform_id=g.platform['id'] if g.platform else None)

    return render_template("categories.html", content_type=content_type, categories=categories)


@store.route("/search")
def search():

    query = request.args.get('query')
    page = request.args.get('page', 1, type=int)

    if not query:
        return render_template("search.html")

    if page < 1:
        flash("Invalid page. Redirected to the first page.", "danger")
        return redirect(url_for('.search', **request.view_args, **request.args, page=1))

    offset = (page - 1) * config['per_page']

    results, total = db.search(query, platform_id=g.platform['id'] if g.platform else None, offset=offset, limit=config['per_page'])

    if not results:
        return render_template("empty.html", category=None, content_type=db.get_content_type_by_name('apps'))

    total_pages = max(1, math.ceil(total / config['per_page']))

    if page > total_pages:
        flash("Invalid page. Redirected to the last page.", "danger")
        return redirect(url_for('.search', **request.view_args, **request.args, page=total_pages))

    return render_template("results.html", results=results, query=query, pages=utils.generate_pages(page, total_pages))

@store.route("/platforms", methods=['GET', 'POST'])
def platforms():
    if request.method == 'GET':
        return render_template("platform.html", platforms=db.get_platforms())

    platform_id = request.form.get('platform_id')

    if not platform_id:
        session['platform_id'] = None
    else:
        if db.get_platform(platform_id):
            session['platform_id'] = platform_id
        else:
            flash("Invalid platform.", "danger")
    
    session.permanent = True
    return redirect(url_for('.root'))


@store.route("/content/<content_type_id>")
def content(content_type_id):

    content_type = db.get_content_type_by_id(content_type_id)

    if not content_type:
        return redirect(url_for('.root'))

    category_id = request.args.get('category', type=int)
    page = request.args.get('page', 1, type=int)

    category = db.get_category(category_id)

    if category_id and not category:
        flash("Invalid category.", "danger")
        return redirect(url_for('.content', content_type_id=content_type['id']))

    if page < 1:
        flash("Invalid page. Redirected to the first page.", "danger")
        return redirect(url_for('.content', **request.view_args, **request.args, page=1))

    offset = (page - 1) * config['per_page']

    results, total = db.get_content(content_type_id=content_type['id'], category_id=category_id, platforms=[g.platform['id']] if g.platform else None, offset=offset, limit=config['per_page'])

    if not results:
        return render_template("empty.html", category=category, content_type=content_type)

    total_pages = max(1, math.ceil(total / config['per_page']))

    if page > total_pages:
        flash("Invalid page. Redirected to the last page.", "danger")
        return redirect(url_for('.content', **request.view_args, **request.args, page=total_pages))

    return render_template("content.html", content_type=content_type, results=results, category=category, pages=utils.generate_pages(page, total_pages))

@store.route("/download")
def download():

    if not config['clients']:
        return redirect(url_for('.root'))

    results = [db.get_item(content_id=content_id) for content_id in config['clients']]
    results = [item for item in results if item is not None]

    content_type = db.get_content_type_by_name('apps')

    return render_template("download.html", content_type=content_type, results=results)

@store.route("/feed.xml")
def feed():

    xml = f"""
        <?xml version="1.0" encoding="windows-1252"?>
        <rssversion="2.0">
        <channel>
        <title>Wunderland Store</title>
        <description>News, content and programs for retro devices.</description>
        <link>http://ovi.wunderwungiel.pl/</link>
        <lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>
    """

    for content in db.get_news():
        xml += f"""
            <item>
                <title>{content['title']}</title>
                <link>{url_for('.news', _external=True, news_id=content['id'])}</link>
                <description></description>
                <pubDate>{content['date']}</pubDate>
                <guid>{url_for('.news', _external=True, news_id=content['id'])}</guid>
            </item>
        """

    xml += "</channel></rss>"

    return xml

@store.route("/news/<int:news_id>")
def news(news_id):

    news = db.get_one_news(news_id=news_id)

    if not news:
        return redirect(url_for('.root'))

    return render_template("news.html", news=news, share=True)

@store.route("/")
def _root():

    return redirect(url_for('.root'))

@store.route("/home")
def root():

    page = request.args.get('page', 1, type=int)

    if page < 1:
        flash("Invalid page. Redirected to the first page.", "danger")
        return redirect(url_for('.root', **request.view_args, **request.args, page=1))

    offset = (page - 1) * config['per_page']
    
    news, total = db.get_news(offset=offset, limit=config['per_page'])

    total_pages = max(1, math.ceil(total / config['per_page']))

    if page > total_pages:
        flash("Invalid page. Redirected to the last page.", "danger")
        return redirect(url_for('.root', **request.view_args, **request.args, page=total_pages))

    return render_template("index.html", news=news, pages=utils.generate_pages(page, total_pages))
