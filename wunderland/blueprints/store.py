import os
import math
from datetime import datetime, timezone
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement

from flask import Blueprint, Response, abort, g, request, session, flash, redirect, render_template, url_for
from werkzeug.utils import secure_filename

from .. import db, helpers
from ..config import CONTENT_DIR, config

store = Blueprint('store', __name__)

# PostgreSQL's OFFSET is a bigint; a larger one is an error, not an empty page.
MAX_OFFSET = 2**63 - 1


def _redirect_to_page(page, message):
    flash(message, "danger")
    request_args = request.args.to_dict()
    request_args['page'] = page
    return redirect(url_for(request.endpoint, **request.view_args, **request_args))


def _paginate(fetch):
    """Fetch the page that ?page= asks for.

    fetch(offset, limit) returns (rows, total). Returns (rows, pages, None), or
    (None, None, redirect) when the page is out of range.
    """
    page = request.args.get('page', 1, type=int)
    per_page = config['per_page']

    if page < 1:
        return None, None, _redirect_to_page(1, "Invalid page. Redirected to the first page.")

    offset = (page - 1) * per_page
    rows, total = fetch(offset, per_page) if offset <= MAX_OFFSET else ([], 0)

    # Past the end the query returns no rows, so it can't report the total either.
    if not rows and page > 1:
        _, total = fetch(0, 1)

    total_pages = max(1, math.ceil(total / per_page))

    if page > total_pages:
        return None, None, _redirect_to_page(total_pages, "Invalid page. Redirected to the last page.")

    return rows, helpers.generate_pages(page, total_pages), None


@store.route("/content/upload", methods=['GET', 'POST'])
def upload():

    if (g.user and g.user['role'] != 'admin') or not g.user:
        return redirect(url_for('.root'))

    if request.method == 'GET':
        platforms = db.get_platforms()
        categories = db.get_categories()
        return render_template("upload.html", platforms=platforms, categories=categories)

    prefix = request.form.get('prefix')
    title = request.form.get('title')
    file = request.files.get('file')
    latest_url = request.form.get('latest_url', '').strip() or None
    category_id = request.form.get('category_id')
    description = request.form.get('description')
    publisher = request.form.get('publisher')
    version = request.form.get('version')
    platforms = request.form.getlist('platforms')
    icon = request.files.get('icon')
    screenshots = [screenshot for screenshot in request.files.getlist('screenshots') if screenshot.filename]
    addon_text = request.form.get('addon_text')
    addon_file = request.files.get('addon_file')
    uid = request.form.get('uid')

    if not all([prefix, title, category_id, description, publisher, version, platforms]):
        flash("Missing required parameters!", "danger")
        return redirect(url_for('.upload'))

    if not icon:
        flash("An icon is required!", "danger")
        return redirect(url_for('.upload'))

    prefix = secure_filename(prefix)
    if not prefix:
        flash("Invalid prefix.", "danger")
        return redirect(url_for('.upload'))

    if not file and not latest_url:
        flash("Either a file or a latest release URL is required!", "danger")
        return redirect(url_for('.upload'))

    if latest_url and urlparse(latest_url).scheme not in ("http", "https"):
        flash("Latest release URL must be an http(s) URL.", "danger")
        return redirect(url_for('.upload'))

    if not db.get_category(category_id):
        return redirect(url_for('.upload'))

    if any(not db.get_platform(platform_id) for platform_id in platforms):
        return redirect(url_for('.upload'))

    icon_extension = os.path.splitext(icon.filename)[1].lower().lstrip('.')
    if icon_extension != "png":
        flash("Invalid icon extension.", "danger")
        return redirect(url_for('.upload'))

    screenshot_extensions = [os.path.splitext(screenshot.filename)[1].lower().lstrip('.') for screenshot in screenshots]
    if not all(extension == "jpg" for extension in screenshot_extensions):
        flash("Invalid screenshot extensions.", "danger")
        return redirect(url_for('.upload'))

    file_name = None
    if file:
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')
        file_name = f"{prefix}.{file_extension}"

    addon_file_name = None
    if addon_file:
        addon_extension = os.path.splitext(secure_filename(addon_file.filename))[1].lower().lstrip('.')
        addon_file_name = f"{prefix}_addon.{addon_extension}" if addon_extension else f"{prefix}_addon"

    uploads = [(icon, os.path.join(CONTENT_DIR, "icons", f"{prefix}.{icon_extension}"))]
    if file:
        uploads.append((file, os.path.join(CONTENT_DIR, "files", file_name)))
    if addon_file:
        uploads.append((addon_file, os.path.join(CONTENT_DIR, "files", addon_file_name)))
    for i, screenshot in enumerate(screenshots):
        uploads.append((screenshot, os.path.join(CONTENT_DIR, "screenshots", f"{prefix}{i+1}.{screenshot_extensions[i]}")))

    if db.prefix_in_use(prefix) or any(os.path.exists(path) for _, path in uploads):
        flash("This prefix is already in use.", "danger")
        return redirect(url_for('.upload'))

    written = []
    try:
        for upload_file, path in uploads:
            # Exclusively create each file; preflight checks alone can race.
            with open(path, 'xb') as destination:
                written.append(path)
                upload_file.save(destination)

        db.upload(
            title=title,
            file=file_name,
            latest_url=latest_url,
            category_id=category_id,
            description=description,
            publisher=publisher,
            version=version,
            icon=f"{prefix}.{icon_extension}",
            screenshot_prefix=prefix,
            screenshot_count=len(screenshots),
            addon_text=addon_text,
            addon_file=addon_file_name,
            uid=uid,
            platforms=platforms
        )
    except Exception as error:
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        if isinstance(error, FileExistsError):
            flash("This prefix is already in use.", "danger")
            return redirect(url_for('.upload'))
        raise

    return redirect(url_for('.root'))
    

@store.route("/content/<int:content_id>/rate", methods=['GET', 'POST'])
def rate(content_id):

    item = db.get_item(content_id)

    if not item:
        abort(404)

    if not g.user:
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template("rate.html", item=item)

    rating = request.form.get('rating', type=int)
    if rating is None or not 1 <= rating <= 5:
        return redirect(url_for('.item', content_id=content_id))

    db.rate(rating, content_id=content_id, user_id=g.user['id'])
    return redirect(url_for('.item', content_id=content_id))


@store.route("/item/<int:content_id>")
def item(content_id):

    item = db.get_item(content_id=content_id)

    if not item:
        abort(404)

    if (g.user and g.user['role'] != 'admin') or not g.user:
        db.increment_counter(content_id)

    item['size'] = helpers.get_file_size(item)
    item['file_url'] = helpers.get_file_url(item)

    platform_id = session.get('platform_id')
    recommended, _ = db.get_content(
        content_type_id=item['category']['type_id'],
        category_id=item['category']['id'],
        platforms=[platform_id] if platform_id else None,
        exclude_content_id=item['id'],
        random_order=True,
        limit=10
    )

    recommended = recommended or None

    item['meta_description'] = " ".join(item['description'].split()) if item['description'] else ""

    return render_template("item.html", item=item, recommended=recommended)


@store.route("/content/<int:content_id>/images")
def images(content_id):

    item = db.get_item(content_id)

    if not item:
        abort(404)

    if not item['screenshots']:
        return redirect(url_for('.item', content_id=content_id))

    return render_template("images.html", item=item)


@store.route("/content/<content_type_id>/browse")
def browse_categories(content_type_id):

    content_type = db.get_content_type_by_id(content_type_id)

    if not content_type:
        return redirect(url_for('.root'))

    categories = db.get_categories(
        content_type_id=content_type['id'],
        platform_id=g.platform['id'] if g.platform else None,
        only_with_content=True
    )

    return render_template("categories.html", content_type=content_type, categories=categories)


@store.route("/search")
def search():

    query = request.args.get('query')
    sort_by = request.args.get('sort')
    order = request.args.get('order', type=int, default=-1)

    sort_order = "DESC" if order == -1 else "ASC"

    if not query:
        return render_template("search.html")

    results, pages, out_of_range = _paginate(lambda offset, limit: db.get_content(
        search=query,
        platforms=[g.platform['id']] if g.platform else None,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    ))

    if out_of_range:
        return out_of_range

    return render_template(
        "results.html",
        results=results,
        query=query,
        pages=pages,
        sort=sort_by,
        order=order,
        sort_fields=db.VALID_SORT_FIELDS,
    )


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

    category_id = request.args.get('category_id', type=int)
    sort_by = request.args.get('sort')
    order = request.args.get('order', type=int, default=-1)

    sort_order = "DESC" if order == -1 else "ASC"

    category = db.get_category(category_id)

    if category_id is not None and (not category or category['type_id'] != content_type['id']):
        flash("Invalid category.", "danger")
        return redirect(url_for('.content', content_type_id=content_type['id']))

    results, pages, out_of_range = _paginate(lambda offset, limit: db.get_content(
        content_type_id=content_type['id'],
        category_id=category_id,
        platforms=[g.platform['id']] if g.platform else None,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    ))

    if out_of_range:
        return out_of_range

    return render_template(
        "content.html",
        content_type=content_type,
        results=results,
        category=category,
        pages=pages,
        sort=sort_by,
        order=order,
        sort_fields=db.VALID_SORT_FIELDS,
    )


@store.route("/download")
def download():

    if not config['clients']:
        return redirect(url_for('.root'))

    results = db.get_items(config['clients'])

    content_type = db.get_content_type_by_id('apps')

    return render_template("download.html", content_type=content_type, results=results)


@store.route("/feed.xml")
def feed():

    rss = Element('rss', version="2.0")
    channel = SubElement(rss, 'channel')

    SubElement(channel, 'title').text = "Wunderland Store"
    SubElement(channel, 'description').text = "News, content and programs for retro devices."
    SubElement(channel, 'link').text = helpers.external_url_for('store.root')
    SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    news_items, total = db.get_news()
    for content in news_items:
        news_url = helpers.external_url_for('store.news', news_id=content['id'])

        item = SubElement(channel, 'item')
        SubElement(item, 'title').text = content['title']
        SubElement(item, 'link').text = news_url
        SubElement(item, 'description').text = ""
        SubElement(item, 'pubDate').text = content['date']
        SubElement(item, 'guid').text = news_url

    ET.indent(rss)

    xml = ET.tostring(rss, encoding='utf-8', xml_declaration=True, short_empty_elements=False)

    return Response(xml, mimetype='application/rss+xml')


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

    news, pages, out_of_range = _paginate(lambda offset, limit: db.get_news(offset=offset, limit=limit))

    if out_of_range:
        return out_of_range

    return render_template("index.html", news=news, pages=pages)
