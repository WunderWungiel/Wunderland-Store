"""Turn the dicts db.py returns into JSON API representations.

The blueprint stays thin: views fetch rows through db.py and pass them here, so the
SQL stays in db.py and the field names and formats of the API live in one place.

Every URL is absolute (external_url_for), so clients never build paths. Links to API
views use the endpoint names in API_ENDPOINTS; those views must exist before a
serializer that links to them runs, or Flask raises a BuildError.
"""
import mimetypes
import os
import re
from datetime import timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .helpers import external_url_for, get_download_url, get_file_size, to_version

API_ENDPOINTS = {
    'content': 'api.content_item',
    'related': 'api.content_related',
    'rating': 'api.content_rating',
    'download': 'api.content_download',
    'news': 'api.news_item',
}

# Symbian UIDs are 32-bit hex, stored as free text: 2001c3a2, 0x2001C3A2, [2001c3a2].
# Without 0x, only all 8 digits count as hex; a shorter bare number could be decimal.
UID_PATTERN = re.compile(r'\[?(?:0x([0-9a-f]{1,8})|([0-9a-f]{8}))\]?', re.IGNORECASE)


def iso(value):
    """Format a timestamptz as ISO 8601 in UTC with a Z and no fractional seconds."""
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def text(value):
    """Strip a string field, turn Windows line breaks into \\n, and turn an empty string into None."""
    if not isinstance(value, str):
        return value
    value = value.replace('\r\n', '\n').strip()
    return value or None


def normalize_uid(value):
    """Return a UID as lowercase 0x plus 8 hex digits, or the stripped value if it isn't one."""
    value = text(value)
    if value is None:
        return None
    match = UID_PATTERN.fullmatch(value)
    if not match:
        return value
    return '0x' + (match.group(1) or match.group(2)).lower().zfill(8)


def normalized_version(version):
    """The dotted form of a Symbian version (1.02(3) -> 1.2.3), or None for free-form versions."""
    try:
        return to_version(version)
    except (TypeError, ValueError):
        return None


def _content_file_url(folder, filename):
    return external_url_for('content', filename=os.path.join(folder, filename))


def _extension(path):
    extension = os.path.splitext(path)[1].lstrip('.').lower()
    return extension or None


def download(item):
    """The download block of a content item; latest_url takes priority over the local file."""
    external = bool(item['latest_url'])
    if external:
        extension = _extension(urlsplit(item['latest_url']).path)
        # The size of a local file says nothing about what latest_url serves.
        size = None
    else:
        extension = _extension(item['file'])
        # get_file_size() returns 0 for a missing file; a client would show "0 B".
        size = get_file_size(item) or None

    return {
        'url': external_url_for(API_ENDPOINTS['download'], content_id=item['id']),
        'direct_url': get_download_url(item, external=True),
        'size': size,
        'extension': extension,
        # From the mimetypes table, so it matches what the content endpoint sends for local files.
        'mime_type': mimetypes.guess_type(f'file.{extension}')[0] if extension else None,
        'external': external,
    }


def rating(item):
    """The rating block of a content item.

    rounded is what the web UI's stars show and what sort=rating uses. average and
    count need rating_average and rating_count from db.get_content(); they are None
    until it returns them.
    """
    count = item.get('rating_count')
    average = item.get('rating_average')
    return {
        'average': round(float(average), 1) if count and average is not None else None,
        'count': count,
        'rounded': item['rating'],
    }


def rating_detail(item, distribution):
    """GET /content/{id}/rating: the rating block plus the number of ratings per star.

    distribution maps star values (1-5) to counts; missing stars count as 0.
    """
    return {
        'content_id': item['id'],
        **rating(item),
        'distribution': {str(star): distribution.get(star, 0) for star in range(1, 6)},
    }


def content_type(row):
    return {
        'id': row['id'],
        'name': row['name'],
        'prefix': row['prefix'],
        'show_icons': row['show_icons'],
        'show_categories': row['show_categories'],
    }


def platform(row):
    return {'id': row['id'], 'name': row['name'], 'parent_id': row['parent_id']}


def category(row):
    """A category from db.get_categories(); content_count is None unless it was asked for counts."""
    return {
        'id': row['id'],
        'name': row['name'],
        'type_id': row['type_id'],
        'content_count': row.get('content_count'),
    }


def content_summary(item):
    """A content item as list rows show it, from db.get_content()."""
    item_type = item['content_type']
    return {
        'id': item['id'],
        'title': text(item['title']),
        'content_type': {'id': item_type['id'], 'name': item_type['name']} if item_type else None,
        'category': {'id': item['category']['id'], 'name': item['category']['name']},
        'publisher': text(item['publisher']),
        'version': text(item['version']),
        'version_normalized': normalized_version(item['version']),
        # icon defaults to Store.png, a real file, so this is never None.
        'icon_url': _content_file_url('icons', item['icon']),
        'rating': rating(item),
        'platforms': sorted(item['platforms'], key=lambda p: p['name']),
        'download': download(item),
        'created_at': iso(item['created_at']),
        'updated_at': iso(item['updated_at']),
        'links': {
            'self': external_url_for(API_ENDPOINTS['content'], content_id=item['id']),
            'web': external_url_for('store.item', content_id=item['id']),
        },
    }


def content_detail(item):
    """GET /content/{id}: the summary plus description, uid, screenshots and addon."""
    data = content_summary(item)

    addon_text = text(item['addon_text'])
    addon_file = item['addon_file']
    addon = None
    if addon_text or addon_file:
        addon = {
            'text': addon_text,
            'url': _content_file_url('files', addon_file) if addon_file else None,
        }

    data.update({
        'description': text(item['description']),
        'uid': normalize_uid(item['uid']),
        # Objects rather than strings, so width and height can be added later.
        'screenshots': [{'url': _content_file_url('screenshots', name)} for name in item['screenshots']],
        'addon': addon,
    })
    data['links'].update({
        'related': external_url_for(API_ENDPOINTS['related'], content_id=item['id']),
        'rating': external_url_for(API_ENDPOINTS['rating'], content_id=item['id']),
    })
    return data


class _TextExtractor(HTMLParser):
    """Plain text from the HTML that Python-Markdown emits, with blocks split by blank lines."""

    # Each list item goes on its own line, without a blank line between items.
    BLOCKS = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'pre', 'blockquote', 'hr', 'table', 'tr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.in_pre = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')
        elif tag == 'li':
            self.parts.append('\n- ')
        elif tag in self.BLOCKS:
            self.parts.append('\n\n')
        if tag == 'pre':
            self.in_pre += 1

    def handle_endtag(self, tag):
        # A closing li adds nothing: the next item's '\n- ' or the list's end breaks the line.
        if tag in self.BLOCKS:
            self.parts.append('\n\n')
        if tag == 'pre':
            self.in_pre = max(0, self.in_pre - 1)

    def handle_data(self, data):
        self.parts.append(data if self.in_pre else re.sub(r'\s+', ' ', data))

    def result(self):
        joined = ''.join(self.parts)
        # Trim spaces around line breaks, then keep at most one blank line between blocks.
        joined = re.sub(r' *\n *', '\n', joined)
        return re.sub(r'\n{3,}', '\n\n', joined).strip()


def html_to_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.result()


NEWS_FORMATS = ('html', 'markdown', 'text')


def news(row, fmt='html'):
    """A news item from db.get_news(), with its body in fmt (one of NEWS_FORMATS).

    created_at and, for fmt='markdown', the Markdown source (markdown) need db.get_news()
    to return them; until it does they are None.
    """
    if fmt == 'html':
        body = row['content']
    elif fmt == 'markdown':
        body = row.get('markdown')
    elif fmt == 'text':
        body = html_to_text(row['content'])
    else:
        raise ValueError(f"Unknown news format: {fmt!r}")

    return {
        'id': row['id'],
        'title': text(row['title']),
        'created_at': iso(row.get('created_at')),
        'body': body,
        'body_format': fmt,
        'links': {
            'self': external_url_for(API_ENDPOINTS['news'], news_id=row['id']),
            'web': external_url_for('store.news', news_id=row['id']),
        },
    }
