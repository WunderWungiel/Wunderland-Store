import os
import re

from flask import current_app, url_for

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
        print(symbian_version)
        raise ValueError("Invalid Symbian version format")
    
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

def get_download_url(item, external=False):
    if item['latest_url']:
        return item['latest_url']
    if item['file']:
        return url_for('static', _external=external, filename=os.path.join("content", "files", item['file']))
    return None

def get_file_size(item):
    # Size of a remote latest_url is unknown
    if item['latest_url']:
        return None
    path = get_file_path(item)
    return os.path.getsize(path) if path and os.path.isfile(path) else 0
