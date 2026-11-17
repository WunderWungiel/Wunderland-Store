from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

# JSON API for native clients, registered under /api/v1. It is stateless: no
# cookie session, no session token lookup and no CSRF check (see app.py).
api = Blueprint('api', __name__)

# Requests are recognised by path rather than blueprint, because unknown /api/ URLs
# have no blueprint (or the legacy one, for /api/<number>) but must still get the
# JSON treatment.
API_PREFIX = '/api/'


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
# without it revalidate every time (lists, detail, news).
DEFAULT_CACHE = 'no-cache'


def cache(*directives, max_age=None):
    """Set the Cache-Control of a view's 200 responses, e.g. @cache('public', max_age=3600).

    Responses that may be stored get an ETag and answer If-None-Match with 304;
    @cache('no-store') responses (random order, for instance) get neither.
    """
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
        cache_control = getattr(view, 'cache_control', DEFAULT_CACHE)
        response.headers['Cache-Control'] = cache_control
        if request.method in ('GET', 'HEAD') and 'no-store' not in cache_control:
            response.add_etag()
            response = response.make_conditional(request)
    else:
        # Errors and redirects (downloads) may change at any time.
        response.headers['Cache-Control'] = 'no-store'

    # For HTTP stacks and proxies that hide error bodies: the envelope already holds the
    # real status in error.status. Redirects are left alone so downloads still work.
    if request.args.get('suppress_response_codes') in ('1', 'true') and response.status_code >= 400:
        response.status_code = 200

    return response
