"""Turn the dicts db.py returns into JSON API representations.

The blueprint stays thin: views fetch rows through db.py and pass them here, so the
SQL stays in db.py and the field names and formats of the API live in one place.

Every URL is absolute (external_url_for), so clients never build paths. Links to API
views use the endpoint names in API_ENDPOINTS; those views must exist before a
serializer that links to them runs, or Flask raises a BuildError.
"""
import os
from datetime import timezone

from .helpers import external_url_for, get_download_url, get_file_size

API_ENDPOINTS = {
    'content': 'api.content_item',
    'related': 'api.content_related',
    'rating': 'api.content_rating',
    'download': 'api.content_download',
    'news': 'api.news_item',
}

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


def _content_file_url(folder, filename):
    return external_url_for('content', filename=os.path.join(folder, filename))


def download(item):
    """The download block of a content item; latest_url takes priority over the local file."""
    external = bool(item['latest_url'])
    # The size of a local file says nothing about what latest_url serves, and
    # get_file_size() returns 0 for a missing file, which a client would show as "0 B".
    size = None if external else get_file_size(item) or None

    return {
        'url': external_url_for(API_ENDPOINTS['download'], content_id=item['id']),
        'direct_url': get_download_url(item, external=True),
        'size': size,
        'external': external,
    }


def rating(item):
    """The rating block of a content item.

    rounded is what the web UI's stars show and what sort=rating uses; average is the
    exact mean to one decimal, None when nobody has rated the item.
    """
    count = item['rating_count']
    average = item['rating_average']
    return {
        'average': round(float(average), 1) if count else None,
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
    """A category from db.get_categories(); content_count is None unless with_counts was passed."""
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
        'uid': text(item['uid']),
        # Objects rather than strings, so width and height can be added later.
        'screenshots': [{'url': _content_file_url('screenshots', name)} for name in item['screenshots']],
        'addon': addon,
    })
    data['links'].update({
        'related': external_url_for(API_ENDPOINTS['related'], content_id=item['id']),
        'rating': external_url_for(API_ENDPOINTS['rating'], content_id=item['id']),
    })
    return data


def news(row):
    """A news item from db.get_news(); body is the HTML the web UI shows."""
    return {
        'id': row['id'],
        'title': text(row['title']),
        'created_at': iso(row['created_at']),
        'body': row['content'],
        'links': {
            'self': external_url_for(API_ENDPOINTS['news'], news_id=row['id']),
            'web': external_url_for('store.news', news_id=row['id']),
        },
    }
