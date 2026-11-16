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


def _is_optional_str(value):
    # Blank means the libpq default: the Unix socket, or no password.
    return value is None or isinstance(value, (str, int))


# Every key the app reads, with a check for the value and what the check expects.
REQUIRED_KEYS = {
    'secret_key': (_is_str, "a string"),
    'base_url': (_is_str, "a string"),
    'database.host': (_is_optional_str, "a string"),
    'database.port': (_is_port, "a port number"),
    'database.name': (_is_str, "a string"),
    'database.user': (_is_str, "a string"),
    'database.password': (_is_optional_str, "a string"),
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

SECRET_KEYS = {'secret_key', 'database.password', 'email.password'}

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

    if problems:
        raise ConfigError(
            f"Invalid {path} (see config.yaml.example):\n" + "\n".join(f"  - {problem}" for problem in problems)
        )


_validate(config)

secret_key = config.get('secret_key')
if not isinstance(secret_key, str) or not secret_key.strip():
    raise ValueError(f"Set secret_key in {path} to a non-empty random string before starting the store")

base_url = config.get('base_url')
if not isinstance(base_url, str) or not base_url.strip():
    raise ValueError(f"Set base_url in {path} to the public HTTP(S) URL of the store")
public_url = urlsplit(base_url)
if (public_url.scheme not in ('http', 'https') or not public_url.hostname
        or public_url.username is not None or public_url.password is not None
        or public_url.query or public_url.fragment):
    raise ValueError("base_url must be an absolute HTTP(S) URL without credentials, query or fragment")

# Uploaded files, icons, screenshots and news. Optional; a relative path is resolved against the repo root.
CONTENT_DIR = os.path.normpath(os.path.join(ROOT_DIR, config.get('content_dir') or 'content'))
