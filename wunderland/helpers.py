import logging
import os
import re
from urllib.parse import urlsplit

from flask import current_app, url_for
from markupsafe import Markup, escape

from .config import config

logger = logging.getLogger(__name__)


def external_url_for(endpoint, **values):
    """Build public URLs from configuration, never request/proxy headers."""
    base = urlsplit(config['base_url'])
    adapter = current_app.url_map.bind(base.netloc, script_name=base.path or '/', url_scheme=base.scheme)
    return adapter.build(endpoint, values, force_external=True)

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
    return os.path.join(current_app.static_folder, "content", "files", item['file'])

def get_file_url(item, external=False):
    if not item['file']:
        return None
    builder = external_url_for if external else url_for
    return builder('static', filename=os.path.join("content", "files", item['file']))

def get_download_url(item, external=False):
    # Clients that take a single link get latest_url when set
    return item['latest_url'] or get_file_url(item, external)

def get_file_size(item):
    # Size of the local file only; a remote latest_url has no known size
    path = get_file_path(item)
    if not path:
        return None
    return os.path.getsize(path) if os.path.isfile(path) else 0
