import logging
import os
import re
from urllib.parse import urlsplit

from flask import current_app, has_request_context, request, url_for
from markupsafe import Markup, escape

from .config import CANONICAL_URL, CONTENT_DIR, config

logger = logging.getLogger(__name__)


def external_url_for(endpoint, **values):
    """Build a public URL on base_url's host, never the request's Host header.

    The store serves both HTTP (old Symbian devices that can't do modern TLS) and
    HTTPS, so inside a request the link keeps the scheme the visitor used, as
    passed on by the proxy. base_url's scheme applies only outside a request.
    """
    base = urlsplit(config['base_url'])
    scheme = request.scheme if has_request_context() else base.scheme
    adapter = current_app.url_map.bind(base.netloc, script_name=base.path or '/', url_scheme=scheme)
    return adapter.build(endpoint, values, force_external=True)


def canonical_url_for(endpoint, **values):
    """Build the URL search engines should index, on canonical_url's scheme and host.

    Unlike external_url_for, the scheme never follows the request, so a page fetched
    over HTTP still names its HTTPS address. Use it only for canonical links, og:url,
    the sitemap and structured data; emails, the feed and client links need
    external_url_for.
    """
    adapter = current_app.url_map.bind(CANONICAL_URL.netloc, script_name=CANONICAL_URL.path or '/',
                                       url_scheme=CANONICAL_URL.scheme)
    return adapter.build(endpoint, values, force_external=True)


def _positive_arg(name):
    value = request.args.get(name, type=int)
    return value if value is not None and value > 0 else None


def canonical_for_request():
    """The canonical URL of the current page, or None outside a matched route.

    Keeps the path and only the query args that pick a different listing: category_id,
    and page past the first. sort, order, query and anything else are dropped, so every
    ordering of a listing points at one URL.
    """
    if not has_request_context() or request.url_rule is None:
        return None
    values = dict(request.view_args or {})
    category_id = _positive_arg('category_id')
    if category_id:
        values['category_id'] = category_id
    page = _positive_arg('page')
    if page and page > 1:
        values['page'] = page
    return canonical_url_for(request.endpoint, **values)


def og_image_for(item=None):
    """The canonical URL of a page's share image: the item's first screenshot, else its
    icon, else the store logo."""
    if item and item.get('screenshots'):
        return canonical_url_for('content', filename='screenshots/' + item['screenshots'][0])
    if item and item.get('icon'):
        return canonical_url_for('content', filename='icons/' + item['icon'])
    return canonical_url_for('static', filename='img/logo_wunderland.png')


def nl2br(text):
    """Escape text and turn its newlines into <br/> tags."""
    if not text:
        return text
    return Markup("<br/>").join(escape(line) for line in text.split("\n"))

def generate_pages(page, total_pages):

    return {
        'current': page,
        'next': page + 1 if page < total_pages else None,
        'previous': page - 1 if page > 1 else None,
        'total': total_pages
    }

def to_version(symbian_version):
    match = re.match(r"(\d+)\.(\d+)\((\d+)\)", symbian_version)
    if not match:
        logger.debug("Not a Symbian version string: %r", symbian_version)
        raise ValueError(f"Invalid Symbian version format: {symbian_version!r}")
    
    major, minor, patch = match.groups()
    if len(minor) == 2 and minor.startswith("0"):
        minor = minor[1]

    return f"{major}.{minor}.{patch}"

def to_symbian_version(version):
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid version format")

    major, minor, patch = parts

    if len(minor) < 2:
        minor = minor.zfill(2)

    return f"{major}.{minor}({patch})"


def get_file_path(item):
    if not item['file']:
        return None
    return os.path.join(CONTENT_DIR, "files", item['file'])

def get_file_url(item, external=False):
    if not item['file']:
        return None
    builder = external_url_for if external else url_for
    return builder('content', filename=os.path.join("files", item['file']))

def get_download_url(item, external=False):
    # Clients that take a single link get latest_url when set
    return item['latest_url'] or get_file_url(item, external)

def get_file_size(item):
    # Size of the local file only; a remote latest_url has no known size
    path = get_file_path(item)
    if not path:
        return None
    return os.path.getsize(path) if os.path.isfile(path) else 0
