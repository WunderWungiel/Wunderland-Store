# Wunderland Store JSON API (v1)

A read-only JSON API for native Symbian store clients (Qt 4.x, Symbian C++). It covers browsing, search, item
details, ratings, downloads, news, update checks and old Ovi Store links.

The examples below are real responses from a test server with example data. Long ones are shortened where marked.

Contents:

1. [Basics](#1-basics)
2. [Responses](#2-responses)
3. [Errors](#3-errors)
4. [Common parameters](#4-common-parameters)
5. [Objects](#5-objects)
6. [Endpoints](#6-endpoints)
7. [Recipes](#7-recipes)

---

## 1. Basics

### Base URL

```
http://ovi.wunderwungiel.pl/api/v1
```

All paths below are relative to it. Plain HTTP works for every endpoint, and every URL the API returns uses the
scheme of your request, so a client that can't do modern TLS never gets sent to HTTPS by the store itself. (Downloads
hosted elsewhere are the exception; see [`download.external`](#download).)

A trailing slash is optional: `/api/v1/content` and `/api/v1/content/` are the same.

### Versioning

- `v1` won't change in a breaking way. A breaking change gets a new prefix (`/api/v2`), served next to v1.
- New fields and new endpoints can appear in v1 at any time. **Ignore fields you don't know.**
- Don't rely on the order of keys in an object. (Today they come in alphabetical order.)

### Methods

Every endpoint is `GET` (and `HEAD`), except [`POST /updates`](#post-updates). Nothing in v1 changes data, apart
from the view counter of [`GET /content/{id}`](#get-contentid).

### No cookies, no login

The API is stateless. It never sets cookies and ignores the ones you send. There are no accounts in v1: login,
rating items and uploads come later and will use an `Authorization: Bearer` header. Until then, those paths return
`404` like any unknown path.

### Compression

Send `Accept-Encoding: gzip` and JSON responses come back gzipped. Qt 4.7's `QNetworkAccessManager` sends the
header and decompresses on its own. JSON with many repeated keys compresses well, which matters on GPRS/EDGE.

---

## 2. Responses

### Envelope

A single object:

```json
{"data": {...}}
```

A list that isn't paginated (reference data, clients, update results):

```json
{"data": [...]}
```

A paginated list (`/content`, `/news`):

```json
{
  "data": [...],
  "meta": {"page": 2, "per_page": 10, "total": 57, "total_pages": 6}
}
```

An error, for every `4xx` and `5xx` (see [Errors](#3-errors)):

```json
{"error": {"status": 404, "code": "not_found", "message": "content not found", "details": {}}}
```

### Field rules

These hold for every object in every response, so a simple parser can rely on them:

- **Every documented key is always present.** A missing value is `null`, an empty list is `[]`. Keys are never left
  out.
- **Each field has one type.** A field that is a string is never a number, and the other way round. The only mix is
  "type or `null`", as listed in the tables below.
- **Integers fit in 32 bits** (signed). That includes IDs, counts and file sizes.
- **IDs are not all numbers.** Content, category and news IDs are integers; content type and platform IDs are
  strings (`"apps"`, `"s60v3"`). Store them as they come.
- **Strings are trimmed** of leading and trailing whitespace. An empty string becomes `null`. Line breaks in text are
  `\n`, never `\r\n`.
- **Timestamps** are ISO 8601 in UTC, always in this exact form: `"2026-11-17T10:04:00Z"` (a `Z`, no fractional
  seconds). Each is 20 characters long, so you can parse it with a fixed format.
- **URLs are absolute.** Never build paths yourself: follow the URLs in `links`, `download`, `icon_url` and so on.
  The file layout on the server may change.
- Nesting is at most two levels deep in list items.

### Encoding

The body is UTF-8 with `Content-Type: application/json; charset=utf-8`. Today every non-ASCII character is escaped
as `\uXXXX` (`"Gra żółw"`), so the bytes on the wire are plain ASCII. This may switch to raw UTF-8
later. Both are valid JSON, so **decode `\uXXXX` escapes, including surrogate pairs (`😀`), and accept raw
UTF-8 too**.

### Caching

Each response carries a `Cache-Control` header:

| Responses | `Cache-Control` |
|---|---|
| `/content-types`, `/platforms`, `/categories` and their single items | `public, max-age=3600` |
| `/content/{id}/related` (random order) and `POST /updates` | `no-store` |
| Errors and redirects | `no-store` |
| Everything else (`/`, content lists and items, ratings, news, clients, legacy lookups) | `no-cache` |

`no-cache` means "you may store it, but check with the server before reusing it". The API sends no `ETag` or
`Last-Modified`, so in practice that is a new request each time. Reference data can be kept for an hour.

---

## 3. Errors

Every error under `/api/` has the JSON envelope, including unknown paths (`404`) and wrong methods (`405`):

```json
{
  "error": {
    "code": "invalid_parameter",
    "details": {"parameter": "sort"},
    "message": "sort must be one of: updated_at, created_at, id, title, rating",
    "status": 400
  }
}
```

- `status` repeats the HTTP status code.
- `code` is a stable string. **Switch on `code`, not on `message`.**
- `message` is English text for logs and bug reports. It may change, and it isn't meant for users.
- `details` is always an object, often empty. For `invalid_parameter` it has `parameter`: the name of the bad query
  parameter or body field. For an unknown content type or platform in a query parameter it also has `values`, the
  unknown IDs:

```json
{
  "error": {
    "code": "invalid_parameter",
    "details": {"parameter": "platform", "values": ["s60v9"]},
    "message": "unknown platform: s60v9",
    "status": 400
  }
}
```

Codes:

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_parameter` | A query parameter or body field has a bad value. `details.parameter` names it. |
| 400 | `bad_request` | The request as a whole is wrong (for example a `POST /updates` body that isn't a JSON object). |
| 404 | `not_found` | Unknown path, unknown ID, or a hidden item. |
| 405 | `method_not_allowed` | Wrong method for the path. The `Allow` header lists the right ones. |
| 413 | `payload_too_large` | `POST /updates` body over 64 KiB. |
| 500 | `internal_error` | A bug on the server. |
| 503 | `service_unavailable` | The server is temporarily down. May carry `Retry-After`. |

Reserved for later versions: `401 unauthorized`, `403 forbidden`, `409 conflict`, `429 rate_limited`.

The server never answers a bad parameter with a redirect or a silent fallback: a typo in your client shows up as a
`400` at once. An unknown filter value (type, platform, category) is a `400` as well, never an empty list.

**Not every error is JSON.** A proxy in front of the app (or your operator's proxy) can answer `502`/`504` with an
HTML page, and some operator proxies replace error bodies. If the body doesn't parse or has no `error` key, fall back
to the HTTP status.

---

## 4. Common parameters

Values in the query string are case-sensitive: `apps`, not `Apps`; `true`, not `True`.

Give each parameter at most once. A repeated one (`?platform=s60v3&platform=s60v5`) is a `400 invalid_parameter`;
for several platforms or IDs, use one comma-separated value (`?platform=s60v3,s60v5`).

### Pagination

`/content` and `/news` are paginated.

| Parameter | Default | Allowed |
|---|---|---|
| `page` | `1` | an integer, 1 or more |
| `per_page` | `per_page_default` from [`/`](#get-) (10 today) | an integer from 1 to `per_page_max` (50) |

- Anything outside those ranges (`0`, `-1`, `abc`, `51`) is a `400 invalid_parameter`.
- `meta.total` is the number of matching items; `meta.total_pages` is at least 1, also when nothing matches.
- A page past the end isn't an error: it returns `200` with `"data": []` and the real `meta`. So a client can simply
  read pages until it gets an empty one.

```json
{"data": [], "meta": {"page": 9, "per_page": 10, "total": 3, "total_pages": 1}}
```

### Platform filter

The store doesn't remember the device's platform: send `?platform=` on every request that should be filtered
(`/content`, `/categories`, `/categories/{id}`, `/content/{id}/related`, and `platform` in the `POST /updates` body).

- Platform IDs come from [`/platforms`](#get-platforms).
- Several are allowed, comma-separated: `?platform=s60v3,s60v5` matches items for either.
- An unknown ID is a `400 invalid_parameter` with the unknown ones in `details.values`.
- Without `platform` nothing is filtered.
- **An item with no platforms runs everywhere.** Its `platforms` list is `[]`, and it matches every platform filter.
  Show it as "all platforms".
- Matching is exact. Asking for `s60v5` doesn't also return items tagged only with its parent `s60`. (This may change
  before the first client release.)

### Sorting

`/content` takes:

| Parameter | Default | Allowed |
|---|---|---|
| `sort` | `updated_at` | `updated_at`, `created_at`, `id`, `title`, `rating` (also in `sort_fields` of [`/`](#get-)) |
| `order` | `desc` | `asc`, `desc` |

- Anything else is a `400 invalid_parameter`.
- Ties are broken by ID, highest first, so pages don't overlap or skip items.
- `sort=rating` sorts by `rating.rounded` (the 0–5 stars the web store shows), not by the exact average.

### Booleans, lists and timestamps

- Booleans are `true` or `false`, nothing else.
- Lists are comma-separated, without spaces or empty items: `1,2,3` (`1,,3` and `1,` are a `400`).
- Timestamps are ISO 8601 **with a zone**: `2026-11-17T10:04:00Z` or `2026-11-17T12:04:00+02:00`. A timestamp without
  a zone, or a bare date, is a `400`: device clocks and zones are often wrong, so the server won't guess.

---

## 5. Objects

### Content summary

How items appear in every list (`/content`, related items, clients, update results, legacy lookups).

| Field | Type | Notes |
|---|---|---|
| `id` | integer | |
| `title` | string | |
| `content_type` | object | `{"id": string, "name": string}` |
| `category` | object | `{"id": integer, "name": string}` |
| `publisher` | string | |
| `version` | string or `null` | As the publisher wrote it: Symbian style `2.10(4)` or dotted `1.4.0`. Show it as it is. |
| `icon_url` | string | Always set; items without their own icon get the store's default icon. PNG. |
| `rating` | object | See [Rating](#rating). |
| `platforms` | list | `[{"id": string, "name": string}]`, sorted by name. `[]` means all platforms. |
| `download` | object | See [Download](#download). |
| `created_at` | timestamp | When the item was added. |
| `updated_at` | timestamp | When the item's record last changed. **Not** the same as "new version": an edit to the description changes it too. Use [`POST /updates`](#post-updates) to check for new versions. |
| `links` | object | `self`: the item's detail URL in the API. `web`: the item's page on the web store. |

```json
{
  "category": {"id": 3, "name": "Productivity"},
  "content_type": {"id": "apps", "name": "Applications"},
  "created_at": "2024-03-02T18:11:00Z",
  "download": {
    "direct_url": "http://ovi.wunderwungiel.pl/static/content/files/handynotes.sis",
    "external": false,
    "size": 184320,
    "url": "http://ovi.wunderwungiel.pl/api/v1/content/128/download"
  },
  "icon_url": "http://ovi.wunderwungiel.pl/static/content/icons/handynotes.png",
  "id": 128,
  "links": {
    "self": "http://ovi.wunderwungiel.pl/api/v1/content/128",
    "web": "http://ovi.wunderwungiel.pl/item/128"
  },
  "platforms": [
    {"id": "s60v3", "name": "S60 3rd Edition"},
    {"id": "s60v5", "name": "S60 5th Edition"}
  ],
  "publisher": "Example Soft",
  "rating": {"average": 4.2, "count": 12, "rounded": 4},
  "title": "Handy Notes",
  "updated_at": "2026-10-01T09:00:00Z",
  "version": "2.10(4)"
}
```

### Content detail

What [`GET /content/{id}`](#get-contentid) returns: every summary field, plus:

| Field | Type | Notes |
|---|---|---|
| `description` | string or `null` | Plain text with `\n` line breaks, not HTML. |
| `uid` | string or `null` | The Symbian UID of the installed app, as `0x` plus 8 hex digits (`0x2001C3A2`). Compare case-insensitively. |
| `screenshots` | list | `[{"url": string}]`, JPEG, in display order. Objects so that more fields (size) can be added. |
| `addon` | object or `null` | Extra notes and/or an extra file. `null` when there's neither. Inside it, `text` (string or `null`) and `url` (string or `null`) can each be missing. |
| `links` | object | The summary's `self` and `web`, plus `related` and `rating` (the item's sub-resources). |

### Rating

| Field | Type | Notes |
|---|---|---|
| `average` | number or `null` | Exact mean to one decimal (`4.2`). `null` when nobody has rated the item. |
| `count` | integer | Number of ratings. |
| `rounded` | integer | 0–5: the stars the web store shows, and what `sort=rating` uses. `0` when unrated. |

```json
{"average": 4.2, "count": 12, "rounded": 4}
```

### Download

| Field | Type | Notes |
|---|---|---|
| `url` | string | **Use this one.** [`GET /content/{id}/download`](#get-contentiddownload): redirects to the file. |
| `direct_url` | string | Where that redirect leads today. Shown for information; it may change. |
| `size` | integer or `null` | In bytes. `null` when the file is hosted elsewhere (`external`) or is missing on the server. |
| `external` | boolean | `true` when the file is hosted on another site (often a "latest release" link). Such hosts may need HTTPS with modern TLS, which many Symbian devices can't do: warn the user, or offer to open the item's `links.web` page instead. |

An item hosted elsewhere:

```json
{
  "direct_url": "https://github.com/example/pocketcalc/releases/latest/download/pocketcalc.sis",
  "external": true,
  "size": null,
  "url": "http://ovi.wunderwungiel.pl/api/v1/content/131/download"
}
```

### Content type

| Field | Type | Notes |
|---|---|---|
| `id` | string | `apps`, `games`, `themes`, ... |
| `name` | string | |
| `prefix` | string | The type's prefix in old Ovi Store URLs; only needed for [`/legacy`](#get-legacyprefixold_id). |
| `show_icons` | boolean | Whether the web store shows item icons for this type. |
| `show_categories` | boolean | Whether the web store has a categories page for this type. If `false`, browse the type's items directly. |

### Platform

| Field | Type | Notes |
|---|---|---|
| `id` | string | `s60v3`, `symbian3`, ... |
| `name` | string | |
| `parent_id` | string or `null` | The parent platform's ID. Not used for filtering in v1 (see [Platform filter](#platform-filter)). |

### Category

| Field | Type | Notes |
|---|---|---|
| `id` | integer | |
| `name` | string | |
| `type_id` | string | The content type it belongs to. |
| `content_count` | integer | Visible items in it, for the `platform` filter of the request if given. |

### News item

| Field | Type | Notes |
|---|---|---|
| `id` | integer | |
| `title` | string | |
| `created_at` | timestamp | |
| `body` | string | HTML rendered from Markdown (paragraphs, links, lists, emphasis and the like), the same the web store shows. Qt 4's rich text (`QLabel`, `QTextBrowser`) can show it. Links and images are absolute URLs. |
| `links` | object | `self`: the API URL. `web`: the news page on the web store. |

---

## 6. Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | [`/`](#get-) | Server info, limits and links |
| GET | [`/content-types`](#get-content-types), `/content-types/{id}` | Content types |
| GET | [`/platforms`](#get-platforms), `/platforms/{id}` | Platforms |
| GET | [`/categories`](#get-categories), `/categories/{id}` | Categories with item counts |
| GET | [`/content`](#get-content) | Browse, search and look up items (paginated) |
| GET | [`/content/{id}`](#get-contentid) | Item detail |
| GET | [`/content/{id}/related`](#get-contentidrelated) | Items from the same category |
| GET | [`/content/{id}/rating`](#get-contentidrating) | Rating with the number of ratings per star |
| GET | [`/content/{id}/download`](#get-contentiddownload) | Redirect to the file |
| POST | [`/updates`](#post-updates) | Update check for installed apps |
| GET | [`/news`](#get-news), `/news/{id}` | News (paginated) |
| GET | [`/clients`](#get-clients) | Downloadable store clients |
| GET | [`/legacy/{prefix}/{old_id}`](#get-legacyprefixold_id) | Item for an old Ovi Store link |

For every `{id}` in a path: an unknown ID, a hidden item, an ID that isn't a number and an ID over 2147483647 are
all the same `404 not_found`. A hidden item looks exactly like one that never existed.

### `GET /`

Server info. It doesn't touch the database, so it's also a cheap check that the store is reachable.

```json
{
  "data": {
    "api_version": "1.0",
    "links": {
      "categories": "http://ovi.wunderwungiel.pl/api/v1/categories",
      "clients": "http://ovi.wunderwungiel.pl/api/v1/clients",
      "content": "http://ovi.wunderwungiel.pl/api/v1/content",
      "content_types": "http://ovi.wunderwungiel.pl/api/v1/content-types",
      "news": "http://ovi.wunderwungiel.pl/api/v1/news",
      "platforms": "http://ovi.wunderwungiel.pl/api/v1/platforms",
      "web": "http://ovi.wunderwungiel.pl/home"
    },
    "name": "Wunderland Store",
    "per_page_default": 10,
    "per_page_max": 50,
    "server_time": "2026-11-21T09:10:29Z",
    "sort_fields": ["updated_at", "created_at", "id", "title", "rating"]
  }
}
```

- `server_time` is the server's clock. Old phones often have the wrong date; compare it with the device clock before
  showing "updated 3 days ago" or building an `updated_since` value.
- `links` may gain entries as endpoints are added.

### `GET /content-types`

All content types, by name. Not paginated. `GET /content-types/{id}` returns one, or `404`.

```json
{
  "data": [
    {"id": "apps", "name": "Applications", "prefix": "applications", "show_categories": true, "show_icons": true},
    {"id": "games", "name": "Games", "prefix": "games", "show_categories": true, "show_icons": true},
    {"id": "themes", "name": "Themes", "prefix": "themes", "show_categories": false, "show_icons": true}
  ]
}
```

### `GET /platforms`

All platforms, by name. Not paginated. `GET /platforms/{id}` returns one, or `404`.

```json
{
  "data": [
    {"id": "s60", "name": "S60", "parent_id": null},
    {"id": "s60v3", "name": "S60 3rd Edition", "parent_id": "s60"},
    {"id": "s60v5", "name": "S60 5th Edition", "parent_id": "s60"},
    {"id": "symbian3", "name": "Symbian^3", "parent_id": null}
  ]
}
```

### `GET /categories`

Categories, by content type and then name. Not paginated.

| Parameter | Meaning |
|---|---|
| `type` | Only categories of this content type. Unknown type → `400`. |
| `platform` | Count only items for these platforms ([Platform filter](#platform-filter)). |
| `non_empty` | `true` (default): leave out categories with no visible items, counted for `platform` if given. `false`: list every category, with its count (which may be 0). |

`GET /categories?type=apps&platform=s60v3`:

```json
{
  "data": [
    {"content_count": 2, "id": 3, "name": "Productivity", "type_id": "apps"},
    {"content_count": 1, "id": 5, "name": "Tools", "type_id": "apps"}
  ]
}
```

`GET /categories/{id}` returns one category, or `404`. It takes `platform` for its `content_count`; without it, the
count is over all platforms. It's returned even when the count is 0.

### `GET /content`

The one list of items, for browsing, category pages, search and lookups. Returns [summaries](#content-summary),
paginated. Hidden items never appear.

| Parameter | Meaning |
|---|---|
| `type` | Content type ID. Unknown → `400`. |
| `category` | Category ID. Unknown → `400`; a category of another type than `type` → `400`. |
| `platform` | [Platform filter](#platform-filter). |
| `q` | Search in titles: case-insensitive, matches anywhere in the title (`notes` finds "Handy Notes"). Trimmed; 1 to 100 characters after trimming, else `400`. |
| `uid` | Items with this Symbian UID, case-insensitive. Must be `0x` plus 8 hex digits, else `400`. |
| `updated_since` | Items whose `updated_at` is later than this timestamp. |
| `sort`, `order` | [Sorting](#sorting). |
| `page`, `per_page` | [Pagination](#pagination). |
| `ids` | Comma-separated content IDs, at most 50. See below. |

All filters combine: `?type=games&platform=s60v5&q=chess` searches the games for S60 5th Edition.

`GET /content?type=apps&per_page=2` (the first item shortened):

```json
{
  "data": [
    {"id": 3, "title": "Wunderland Store", "updated_at": "2026-11-02T19:20:00Z", "...": "..."},
    {
      "category": {"id": 3, "name": "Productivity"},
      "content_type": {"id": "apps", "name": "Applications"},
      "created_at": "2024-03-02T18:11:00Z",
      "download": {
        "direct_url": "http://ovi.wunderwungiel.pl/static/content/files/handynotes.sis",
        "external": false,
        "size": 184320,
        "url": "http://ovi.wunderwungiel.pl/api/v1/content/128/download"
      },
      "icon_url": "http://ovi.wunderwungiel.pl/static/content/icons/handynotes.png",
      "id": 128,
      "links": {
        "self": "http://ovi.wunderwungiel.pl/api/v1/content/128",
        "web": "http://ovi.wunderwungiel.pl/item/128"
      },
      "platforms": [
        {"id": "s60v3", "name": "S60 3rd Edition"},
        {"id": "s60v5", "name": "S60 5th Edition"}
      ],
      "publisher": "Example Soft",
      "rating": {"average": 4.2, "count": 12, "rounded": 4},
      "title": "Handy Notes",
      "updated_at": "2026-10-01T09:00:00Z",
      "version": "2.10(4)"
    }
  ],
  "meta": {"page": 1, "per_page": 2, "total": 3, "total_pages": 2}
}
```

**`ids`**: fetches given items in one request, for example a list of favourites the client keeps.

- Items come back **in the order you gave**, duplicates included.
- Unknown and hidden IDs are left out, without an error. Compare the returned `id`s with yours to see which are gone.
- `ids` can't be combined with the filters above (`type`, `category`, `platform`, `q`, `uid`, `updated_since`):
  that's a `400`. `page`, `per_page`, `sort` and `order` are ignored.
- `meta` says page 1 of 1, with `per_page` and `total` both the number of items returned.

`GET /content?ids=131,999,3` (999 doesn't exist; items shortened):

```json
{
  "data": [
    {"id": 131, "title": "Pocket Calc", "...": "..."},
    {"id": 3, "title": "Wunderland Store", "...": "..."}
  ],
  "meta": {"page": 1, "per_page": 2, "total": 2, "total_pages": 1}
}
```

### `GET /content/{id}`

One item as a [detail](#content-detail). Each `GET` counts as a view of the item (as on the web store); `HEAD`
doesn't.

```json
{
  "data": {
    "addon": {
      "text": "Dictionary for the spell checker",
      "url": "http://ovi.wunderwungiel.pl/static/content/files/handynotes-dict.zip"
    },
    "category": {"id": 3, "name": "Productivity"},
    "content_type": {"id": "apps", "name": "Applications"},
    "created_at": "2024-03-02T18:11:00Z",
    "description": "Quick notes with folders and search.\nWorks offline.",
    "download": {
      "direct_url": "http://ovi.wunderwungiel.pl/static/content/files/handynotes.sis",
      "external": false,
      "size": 184320,
      "url": "http://ovi.wunderwungiel.pl/api/v1/content/128/download"
    },
    "icon_url": "http://ovi.wunderwungiel.pl/static/content/icons/handynotes.png",
    "id": 128,
    "links": {
      "rating": "http://ovi.wunderwungiel.pl/api/v1/content/128/rating",
      "related": "http://ovi.wunderwungiel.pl/api/v1/content/128/related",
      "self": "http://ovi.wunderwungiel.pl/api/v1/content/128",
      "web": "http://ovi.wunderwungiel.pl/item/128"
    },
    "platforms": [
      {"id": "s60v3", "name": "S60 3rd Edition"},
      {"id": "s60v5", "name": "S60 5th Edition"}
    ],
    "publisher": "Example Soft",
    "rating": {"average": 4.2, "count": 12, "rounded": 4},
    "screenshots": [
      {"url": "http://ovi.wunderwungiel.pl/static/content/screenshots/handynotes1.jpg"},
      {"url": "http://ovi.wunderwungiel.pl/static/content/screenshots/handynotes2.jpg"}
    ],
    "title": "Handy Notes",
    "uid": "0x2001C3A2",
    "updated_at": "2026-10-01T09:00:00Z",
    "version": "2.10(4)"
  }
}
```

### `GET /content/{id}/related`

Other items from the same category, in random order, as [summaries](#content-summary). For a "you may also like"
row on the item page.

| Parameter | Meaning |
|---|---|
| `platform` | [Platform filter](#platform-filter). |
| `limit` | How many, 1 to 20 (default 10). |

Not paginated, since the order changes each time. `meta.total` is the number returned.

```json
{
  "data": [
    {"id": 131, "title": "Pocket Calc", "...": "..."}
  ],
  "meta": {"total": 1}
}
```

### `GET /content/{id}/rating`

The item's [rating](#rating) plus the number of ratings per star. `distribution` always has all five keys, as strings
(JSON object keys are always strings).

```json
{
  "data": {
    "average": 4.2,
    "content_id": 128,
    "count": 12,
    "distribution": {"1": 0, "2": 1, "3": 1, "4": 4, "5": 6},
    "rounded": 4
  }
}
```

### `GET /content/{id}/download`

Redirects to the file with `302 Found`. The `Location` header is the file's URL (the same as `download.direct_url`).

```
HTTP/1.1 302 FOUND
Location: http://ovi.wunderwungiel.pl/static/content/files/handynotes.sis
Cache-Control: no-store
```

- Use this rather than `direct_url`: later versions may count downloads here or serve files hosted elsewhere through
  the store.
- **Qt 4's `QNetworkAccessManager` doesn't follow redirects by itself.** Read the `Location` header and request it.
  The redirect's own body is a short HTML page, not JSON; ignore it.
- If the item has no file on the server, the answer is a JSON `404` instead of a redirect, so you don't save an error
  page as the download. Files hosted elsewhere (`external`) aren't checked.
- The file itself is served with a `Content-Type` the device's installer recognises: `.sis` as
  `application/vnd.symbian.install`, `.sisx` as `x-epoc/x-sisx-app`, `.jar` as `application/java-archive`, `.jad`
  as `text/vnd.sun.j2me.app-descriptor`. Local files support `Range` requests, so an interrupted download can resume.

### `POST /updates`

The update check: send the UIDs and versions of the apps installed on the device, get back which ones have a newer
version in the store. It's a `POST` because the list can be long; it changes nothing.

Request body, JSON:

```json
{
  "platform": "s60v3",
  "installed": [
    {"uid": "0x2001c3a2", "version": "2.09(0)"},
    {"uid": "0xE0001234", "version": "0.9.2"},
    {"uid": "0xE0009999", "version": "1.0"}
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `platform` | string, optional | One platform ID. Only items for that platform are matched (items with no platforms always match). Unknown → `400 invalid_parameter`. |
| `installed` | list, required | At most 100 entries. |
| `installed[n].uid` | string | `0x` plus 8 hex digits, any case. |
| `installed[n].version` | string | 1 to 64 characters, Symbian (`2.09(0)`) or dotted (`1.4.0`) style. |

Unknown keys are ignored. The `Content-Type` header isn't checked (send `application/json` if you can); the body is
read as JSON whatever it says.

Response, one entry per `installed` entry, in the same order (duplicates kept):

```json
{
  "data": [
    {
      "comparison": "numeric",
      "content": {"id": 128, "title": "Handy Notes", "version": "2.10(4)", "...": "..."},
      "installed_version": "2.09(0)",
      "uid": "0x2001c3a2",
      "update_available": true
    },
    {
      "comparison": "numeric",
      "content": {"id": 3, "title": "Wunderland Store", "version": "0.9.2", "...": "..."},
      "installed_version": "0.9.2",
      "uid": "0xE0001234",
      "update_available": false
    },
    {
      "comparison": null,
      "content": null,
      "installed_version": "1.0",
      "uid": "0xE0009999",
      "update_available": false
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `uid` | string | As you sent it. |
| `installed_version` | string | As you sent it. |
| `content` | [summary](#content-summary) or `null` | The store's item with that UID, or `null` if there's none (for the platform). If several items share a UID, the most recently updated one. |
| `comparison` | string or `null` | How the versions were compared: `"numeric"`, `"string"`, or `null` when `content` or its `version` is `null`. |
| `update_available` | boolean | See below. |

How versions are compared:

- Both versions are parsed as Symbian style (`a.b(c)`, so `2.09(0)` is 2.9.0) or dotted style (`2.9.0`), and compared
  number by number. Missing parts count as 0, so `1.2` equals `1.2.0`. This is `"comparison": "numeric"`, and
  `update_available` is `true` only when the store's version is **higher**.
- If either version can't be parsed (`1.0 beta`, `r1234`), they're compared as strings after trimming. This is
  `"comparison": "string"`, and `update_available` is `true` when they **differ**. The store's version may then be
  older, so word it as "a different version is available", not "update available".
- With no matching item, `update_available` is `false`.
- With a matching item that has no version (`content.version` is `null`), `update_available` is `false` and
  `comparison` is `null`; `content` is still set.

Errors:

| Status | `code` | When |
|---|---|---|
| 400 | `bad_request` | The body isn't JSON, isn't an object, has no `installed` list, or lists more than 100 entries. |
| 400 | `invalid_parameter` | One bad entry. `details.parameter` is its path, with 0-based indexes: `installed[3]` (not an object), `installed[3].uid`, `installed[3].version`, or `platform`. |
| 413 | `payload_too_large` | The body is over 64 KiB. |

```json
{
  "error": {
    "code": "invalid_parameter",
    "details": {"parameter": "installed[0].version"},
    "message": "installed[0].version must be a string of 1 to 64 characters",
    "status": 400
  }
}
```

### `GET /news`

News, newest first, paginated ([Pagination](#pagination)). `GET /news/{id}` returns one [news item](#news-item), or
`404`.

```json
{
  "data": [
    {
      "body": "<p>Twelve new games are in the store this week.</p>\n<p>See the <a href=\"http://ovi.wunderwungiel.pl/content/games\">games list</a>.</p>",
      "created_at": "2026-11-01T12:00:00Z",
      "id": 7,
      "links": {
        "self": "http://ovi.wunderwungiel.pl/api/v1/news/7",
        "web": "http://ovi.wunderwungiel.pl/news/7"
      },
      "title": "Winter update"
    }
  ],
  "meta": {"page": 1, "per_page": 10, "total": 1, "total_pages": 1}
}
```

**A page can be shorter than `per_page`** even when it isn't the last one (a news item whose text is missing on the
server is left out but still counted in `total`). Don't treat a short page as the end: use `page < total_pages`, or
read until an empty page.

### `GET /clients`

The store's own client apps that users can download (the web store's "Download" page), as
[summaries](#content-summary) in the store's chosen order. Not paginated; may be `[]`.

A client can look for its own UID here, or simply check for its own update with [`POST /updates`](#post-updates).

```json
{
  "data": [
    {"id": 3, "title": "Wunderland Store", "version": "0.9.2", "...": "..."}
  ]
}
```

### `GET /legacy/{prefix}/{old_id}`

Finds the store item for an old Ovi Store link, for a client that opens old URLs or QR codes. For a link like
`/applications/4242`, `prefix` is the content type's [`prefix`](#content-type) (`applications`) and `old_id` the old
number (`4242`).

`GET /legacy/applications/4242` (the summary shortened):

```json
{
  "data": {
    "content": {"id": 128, "title": "Handy Notes", "...": "..."},
    "content_id": 128
  }
}
```

`content` is the item's [summary](#content-summary). It's a normal `200`, not a redirect. An unknown prefix, an unknown
old ID and an item that's been hidden are all the same `404`.

---

## 7. Recipes

**First start.** `GET /` to check the server and read the limits, then `GET /content-types` and `GET /platforms`
(cache both for an hour). Let the user pick the platform once, or map the device model to it, and send it with every
filtered request from then on.

**Browsing.** `GET /categories?type=apps&platform=s60v3` for the category list with counts, then
`GET /content?category=3&platform=s60v3&page=1` for its items. If the type's `show_categories` is `false`, go
straight to `GET /content?type=themes&platform=s60v3`.

**Search.** `GET /content?q=notes&platform=s60v3`. Add `type=` to search one type only.

**Item page.** `GET /content/{id}` (from the summary's `links.self`), then `links.related` for the row below it.
Load the icon and screenshots lazily; on slow links, only when the user scrolls to them.

**Download.** Request `download.url`, read `Location` from the `302`, request that, and hand the file to the
installer. Check `download.external` first and warn the user when it's `true`.

**Update check.** List the installed apps' UIDs and versions (from the Symbian installer API), send them in batches
of up to 100 to `POST /updates` with the device's platform, and show the entries with `update_available: true`.

**What's new since last time.** Remember the `server_time` of your last check and send it as
`GET /content?updated_since=2026-11-01T12:00:00Z&platform=s60v3`. Remember: a newer `updated_at` means the item
changed, not necessarily that its version did.

**Error handling.** Parse the JSON body and switch on `error.code`. If the body isn't JSON (a proxy answered), fall
back to the HTTP status. A `404` on an item you had saved means it's gone or hidden: drop it from favourites.
