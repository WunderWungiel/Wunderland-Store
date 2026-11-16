import yaml
import os
from urllib.parse import urlsplit

path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.yaml")

with open(path, "r") as f:
    config = yaml.safe_load(f.read())

secret_key = config.get('secret_key')
if not isinstance(secret_key, str) or not secret_key.strip():
    raise ValueError("Set secret_key in config.yaml to a non-empty random string before starting the store")

base_url = config.get('base_url')
if not isinstance(base_url, str) or not base_url.strip():
    raise ValueError("Set base_url in config.yaml to the public HTTP(S) URL of the store")
public_url = urlsplit(base_url)
if (public_url.scheme not in ('http', 'https') or not public_url.hostname
        or public_url.username is not None or public_url.password is not None
        or public_url.query or public_url.fragment):
    raise ValueError("base_url must be an absolute HTTP(S) URL without credentials, query or fragment")
