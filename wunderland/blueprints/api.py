import re
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from .. import api_format as fmt
from .. import db
from ..config import config
from ..helpers import external_url_for

# JSON API for native clients, registered under /api/v1. It is stateless: no
# cookie session, no session token lookup and no CSRF check (see app.py).
api = Blueprint('api', __name__)

# Requests are recognised by path rather than blueprint, because unknown /api/ URLs
# have no blueprint (or the legacy one, for /api/<number>) but must still get the
# JSON treatment.
API_PREFIX = '/api/'

API_VERSION = '1.0'
STORE_NAME = 'Wunderland Store'

PER_PAGE_MAX = 50
IDS_MAX = 50
# Every integer the API takes or returns fits in 32 bits (device parsers), and a
# bigger page would overflow OFFSET in Postgres.
INT_MAX = 2**31 - 1
SORT_ORDERS = {'asc': 'ASC', 'desc': 'DESC'}
BOOLEANS = {'true': True, 'false': False}
# ASCII digits only: str.isdigit() also accepts characters like '²' that int() rejects.
DIGITS = re.compile(r'[0-9]+')


class ApiError(HTTPException):
    """An error that carries its JSON envelope, so views and parsers can raise it."""

    def __init__(self, status, code, message, **details):
        body = {'error': {'status': status, 'code': code, 'message': message, 'details': details}}
        response = jsonify(body)
        response.status_code = status
        super().__init__(description=message, response=response)
        self.code = status


def api_error(status, code, message, **details):
    return ApiError(status, code, message, **details)


def invalid_parameter(name, message):
    return api_error(400, 'invalid_parameter', message, parameter=name)


def is_api_request():
    return request.path.startswith(API_PREFIX)


# Stable codes for the errors Werkzeug raises; the client switches on these.
ERROR_CODES = {
    400: 'bad_request',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    409: 'conflict',
    413: 'payload_too_large',
    429: 'rate_limited',
    500: 'internal_error',
    503: 'service_unavailable',
}


def error_response(e):
    """Turn any HTTPException raised under /api/ into the JSON error envelope.

    app.py calls this from its error handlers, which also see the requests that matched
    no route (those never reach the blueprint's own handlers).
    """
    if isinstance(e, ApiError):
        return e.get_response()

    status = e.code or 500
    code = ERROR_CODES.get(status, 'bad_request' if status < 500 else 'internal_error')
    # Werkzeug's descriptions are generic English text and never include the cause.
    response = api_error(status, code, e.description or e.name).get_response()
    # 405 must say which methods are allowed; 429 and 503 may carry Retry-After.
    for name in ('Allow', 'Retry-After'):
        value = dict(e.get_headers()).get(name)
        if value:
            response.headers[name] = value
    return response


# Cache-Control per endpoint, set with @cache(...) under @api.route(...). Endpoints
# without it are fetched again every time (lists, detail, news).
DEFAULT_CACHE = 'no-cache'


def cache(*directives, max_age=None):
    """Set the Cache-Control of a view's 200 responses, e.g. @cache('public', max_age=3600)."""
    value = ', '.join(directives + ((f'max-age={max_age}',) if max_age is not None else ()))

    def decorator(view):
        view.cache_control = value
        return view
    return decorator


@api.after_app_request
def finalize_response(response):
    # Registered app-wide so that unknown /api/ URLs, which have no blueprint, get it too.
    if not is_api_request():
        return response

    if response.mimetype == 'application/json':
        response.content_type = 'application/json; charset=utf-8'

    if response.status_code == 200:
        view = current_app.view_functions.get(request.endpoint)
        response.headers['Cache-Control'] = getattr(view, 'cache_control', DEFAULT_CACHE)
    else:
        # Errors and redirects (downloads) may change at any time.
        response.headers['Cache-Control'] = 'no-store'

    return response


# Werkzeug's request.args.get(type=int) falls back to the default on bad input. The
# API reports bad input instead, so every parser below reads the raw string.

def _parse_int(name, value, minimum=1, maximum=INT_MAX):
    if not DIGITS.fullmatch(value) or not minimum <= int(value) <= maximum:
        raise invalid_parameter(name, f"{name} must be an integer from {minimum} to {maximum}")
    return int(value)


def _split_list(name, value):
    items = value.split(',')
    if not all(items):
        raise invalid_parameter(name, f"{name} must be a comma-separated list without empty items")
    return items


def parse_page():
    """Return (page, per_page, offset) from ?page= and ?per_page=."""
    page = request.args.get('page')
    page = 1 if page is None else _parse_int('page', page)

    per_page = request.args.get('per_page')
    if per_page is None:
        per_page = min(config['per_page'], PER_PAGE_MAX)
    else:
        per_page = _parse_int('per_page', per_page, maximum=PER_PAGE_MAX)

    # page * per_page stays far below Postgres' bigint OFFSET limit.
    return page, per_page, (page - 1) * per_page


def parse_platforms(name='platform'):
    """Return the list of platform IDs in ?platform=, or None for no filtering."""
    value = request.args.get(name)
    if value is None:
        return None

    platforms = _split_list(name, value)
    known = {platform['id'] for platform in db.get_platforms()}
    unknown = [platform for platform in platforms if platform not in known]
    if unknown:
        raise api_error(
            400, 'invalid_parameter', f"unknown platform: {', '.join(unknown)}", parameter=name, values=unknown
        )
    # Order and duplicates don't matter to the filter.
    return sorted(set(platforms))


def parse_sort():
    """Return (sort_by, sort_order) for db.get_content() from ?sort= and ?order=."""
    sort_by = request.args.get('sort', 'updated_at')
    if sort_by not in db.VALID_SORT_FIELDS:
        raise invalid_parameter('sort', f"sort must be one of: {', '.join(db.VALID_SORT_FIELDS)}")

    order = request.args.get('order', 'desc')
    if order not in SORT_ORDERS:
        raise invalid_parameter('order', f"order must be one of: {', '.join(SORT_ORDERS)}")

    return sort_by, SORT_ORDERS[order]


def parse_bool(name, default):
    value = request.args.get(name)
    if value is None:
        return default
    if value not in BOOLEANS:
        raise invalid_parameter(name, f"{name} must be true or false")
    return BOOLEANS[value]


def parse_ids(name='ids', maximum=IDS_MAX):
    """Return the list of IDs in ?ids=, in the given order with duplicates kept, or None."""
    value = request.args.get(name)
    if value is None:
        return None

    items = _split_list(name, value)
    if len(items) > maximum:
        raise invalid_parameter(name, f"{name} takes at most {maximum} IDs")
    return [_parse_int(name, item) for item in items]


def parse_timestamp(name):
    """Return the ISO 8601 timestamp in ?<name>= as an aware datetime in UTC, or None.

    The timestamp must carry a zone (Z or an offset): device clocks and zones are often
    wrong, and guessing one would silently shift the result.
    """
    value = request.args.get(name)
    if value is None:
        return None

    message = f"{name} must be an ISO 8601 timestamp with a zone, e.g. 2026-11-17T10:04:00Z"
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        raise invalid_parameter(name, message) from None
    if timestamp.tzinfo is None:
        raise invalid_parameter(name, message)
    return timestamp.astimezone(timezone.utc)


def parse_content_type(name='type'):
    """Return the content type ID in ?<name>=, or None for no filtering."""
    value = request.args.get(name)
    if value is None:
        return None
    if db.get_content_type_by_id(value) is None:
        raise api_error(400, 'invalid_parameter', f"unknown content type: {value}", parameter=name, values=[value])
    return value


def not_found(what):
    return api_error(404, 'not_found', f"{what} not found")


# Path IDs are 32-bit, like every integer the API takes (bigger ones would make Postgres fail).
ID = f'int(max={INT_MAX})'


# Endpoints.

def envelope(data):
    """A single resource or an unpaginated collection (reference data with a handful of rows)."""
    return jsonify({'data': data})


@api.route('/')
def index():
    # No DB access, so it doubles as a cheap reachability check for clients.
    return envelope({
        'name': STORE_NAME,
        'api_version': API_VERSION,
        'server_time': fmt.iso(datetime.now(timezone.utc)),
        'per_page_default': min(config['per_page'], PER_PAGE_MAX),
        'per_page_max': PER_PAGE_MAX,
        'sort_fields': list(db.VALID_SORT_FIELDS),
        # Links are added here as their endpoints are built.
        'links': {
            'content_types': external_url_for('api.content_types'),
            'platforms': external_url_for('api.platforms'),
            'categories': external_url_for('api.categories'),
            'web': external_url_for('store.root'),
        },
    })


@api.route('/content-types')
@cache('public', max_age=3600)
def content_types():
    return envelope([fmt.content_type(row) for row in db.get_content_types()])


@api.route('/content-types/<type_id>')
@cache('public', max_age=3600)
def content_type_item(type_id):
    row = db.get_content_type_by_id(type_id)
    if row is None:
        raise not_found("content type")
    return envelope(fmt.content_type(row))


@api.route('/platforms')
@cache('public', max_age=3600)
def platforms():
    return envelope([fmt.platform(row) for row in db.get_platforms()])


@api.route('/platforms/<platform_id>')
@cache('public', max_age=3600)
def platform_item(platform_id):
    row = db.get_platform(platform_id)
    if row is None:
        raise not_found("platform")
    return envelope(fmt.platform(row))


@api.route('/categories')
@cache('public', max_age=3600)
def categories():
    rows = db.get_categories(
        content_type_id=parse_content_type(),
        platforms=parse_platforms(),
        only_with_content=parse_bool('non_empty', True),
        with_counts=True,
    )
    return envelope([fmt.category(row) for row in rows])


@api.route(f'/categories/<{ID}:category_id>')
@cache('public', max_age=3600)
def category_item(category_id):
    # content_count is over all platforms, or over ?platform= if given.
    rows = db.get_categories(category_id=category_id, platforms=parse_platforms(), with_counts=True)
    if not rows:
        raise not_found("category")
    return envelope(fmt.category(rows[0]))
