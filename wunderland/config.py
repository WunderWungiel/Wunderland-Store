import yaml
import os
from urllib.parse import urlsplit

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# WUNDERLAND_CONFIG overrides the default of config.yaml at the repo root.
path = os.environ.get("WUNDERLAND_CONFIG") or os.path.join(ROOT_DIR, "config.yaml")

with open(path, "r") as f:
    config = yaml.safe_load(f.read())

class ConfigError(ValueError):
    pass


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_list_of(check):
    return lambda value: isinstance(value, list) and all(check(item) for item in value)


def _is_str(value):
    return isinstance(value, str)


def _is_port(value):
    # The DB and SMTP libraries also accept a quoted port.
    return _is_int(value) or (isinstance(value, str) and value.strip().isdigit())


# Every key the app reads, with a check for the value and what the check expects.
REQUIRED_KEYS = {
    'secret_key': (_is_str, "a string"),
    'base_url': (_is_str, "a string"),
    'email.address': (_is_str, "a string"),
    'email.password': (_is_str, "a string"),
    'email.smtp.port': (_is_port, "a port number"),
    'email.smtp.address': (_is_str, "a string"),
    'allow_indexing': (lambda value: isinstance(value, bool), "true or false"),
    'per_page': (lambda value: _is_int(value) and value > 0, "a positive integer"),
    'platforms.qtstore': (_is_list_of(_is_str), "a list of platform names"),
    'platforms.client': (_is_list_of(_is_str), "a list of platform names"),
    'clients': (lambda value: value is None or _is_list_of(_is_int)(value), "a list of content IDs"),
}

SECRET_KEYS = {'secret_key', 'email.password'}

# The database connection comes only from these, which Docker compose sets from .env, the
# same values the db container is created with. Unset host, port and password fall back to
# the libpq defaults; set but empty, host means the Unix socket and password means none.
DATABASE_ENV = {
    'host': 'POSTGRES_HOST',
    'port': 'POSTGRES_PORT',
    'dbname': 'POSTGRES_DB',
    'user': 'POSTGRES_USER',
    'password': 'POSTGRES_PASSWORD',
}
REQUIRED_DATABASE_ENV = ('dbname', 'user')

DATABASE = {key: os.environ[var] for key, var in DATABASE_ENV.items() if var in os.environ}


def _database_problems():
    problems = []
    for key in REQUIRED_DATABASE_ENV:
        if not DATABASE.get(key):
            problems.append(f"set the {DATABASE_ENV[key]} environment variable")
    port = DATABASE.get('port')
    if port and not port.strip().isdigit():
        problems.append(f"POSTGRES_PORT must be a port number, got {port!r}")
    return problems


_MISSING = object()


def _lookup(data, key):
    for part in key.split('.'):
        if not isinstance(data, dict) or part not in data:
            return _MISSING
        data = data[part]
    return data


def _validate(data):
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping; see config.yaml.example")

    problems = []
    # Ignoring an old section could connect to a different database than the one it names.
    if 'database' in data:
        problems.append("the database section is no longer read; remove it and set the POSTGRES_HOST, "
                        "POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD environment "
                        "variables (in Docker, in .env) to the same values")
    for key, (check, expected) in REQUIRED_KEYS.items():
        value = _lookup(data, key)
        if value is _MISSING:
            problems.append(f"{key} is missing")
        elif not check(value):
            # Never echo secrets into the startup log.
            shown = type(value).__name__ if key in SECRET_KEYS else repr(value)
            problems.append(f"{key} must be {expected}, got {shown}")

    content_dir = data.get('content_dir')
    if content_dir is not None and not (_is_str(content_dir) and content_dir.strip()):
        problems.append(f"content_dir must be a non-empty string, got {content_dir!r}")

    verification = data.get('google_site_verification')
    if verification is not None and not (_is_str(verification) and verification.strip()):
        problems.append(f"google_site_verification must be a non-empty string, got {verification!r}")

    problems += _database_problems()

    if problems:
        raise ConfigError(
            f"Invalid configuration in {path} or the environment (see config.yaml.example and .env.example):\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )


_validate(config)

secret_key = config.get('secret_key')
if not isinstance(secret_key, str) or not secret_key.strip():
    raise ValueError(f"Set secret_key in {path} to a non-empty random string before starting the store")


def _check_public_url(key, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Set {key} in {path} to the public HTTP(S) URL of the store")
    url = urlsplit(value)
    if (url.scheme not in ('http', 'https') or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment):
        raise ValueError(f"{key} must be an absolute HTTP(S) URL without credentials, query or fragment")
    return url


base_url = config.get('base_url')
public_url = _check_public_url('base_url', base_url)

# Where search engines should index the store: canonical links, og:url, the sitemap and
# structured data. Optional; it defaults to base_url over HTTPS, since devices keep using
# HTTP but search results shouldn't. base_url's port is an HTTP port, so the default drops it.
canonical_url = config.get('canonical_url')
if canonical_url is None:
    host = f"[{public_url.hostname}]" if ':' in public_url.hostname else public_url.hostname
    CANONICAL_URL = public_url._replace(scheme='https', netloc=host)
else:
    CANONICAL_URL = _check_public_url('canonical_url', canonical_url)

# Optional Search Console HTML tag verification token, printed as a meta tag on every page.
GOOGLE_SITE_VERIFICATION = config.get('google_site_verification')

# Uploaded files, icons, screenshots and news. Optional; a relative path is resolved against the repo root.
CONTENT_DIR = os.path.normpath(os.path.join(ROOT_DIR, config.get('content_dir') or 'content'))
