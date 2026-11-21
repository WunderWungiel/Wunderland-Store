# JSON API plan (v1)

Status: v1 done. Every step of the implementation outline (section 6) is built: the blueprint at `/api/v1` with
JSON errors and caching headers, the query parameter parsers, the serializers in `wunderland/api_format.py`, the
`db.py` queries they need, every phase 1 endpoint of section 4, gzip for JSON in nginx, the download MIME types and
the smoke tests. The reference for client authors is `docs/api.md` (step 9). Still to do on a real device: install a
`.sis`/`.sisx` and a JAD/JAR (5.7) and settle open question 2.

Goal: a REST/JSON API that covers every store feature, for a new native Symbian client (Qt 4.x / Symbian C++).
Login, ratings by users and admin uploads come in a later phase; this plan reserves their shape so v1 doesn't have
to change when they arrive.

The existing XML endpoints (`client`, `qtstore`, `legacy` blueprints) stay as they are. Old devices depend on their
exact output, and the API doesn't replace them.

---

## 1. What the store does today (feature inventory)

Every feature the API has to cover, with where it lives now:

| Feature | Web route | Code | Login? |
|---|---|---|---|
| Content types (apps, games, themes) | nav, `/content/<type>` | `db.get_content_types()` (cached per worker) | no |
| Platforms, pick one | `/platforms` (kept in the cookie session) | `db.get_platforms()` (cached per worker) | no |
| Categories of a type, only non-empty, filtered by platform | `/content/<type>/browse` | `db.get_categories(only_with_content=True, platform_id=...)` | no |
| Browse a type, optionally one category, sorted, paginated | `/content/<type>?category_id&sort&order&page` | `db.get_content()` | no |
| Item detail (size, file URL, platforms, screenshots, addon, rating) | `/item/<id>` | `db.get_item()`, `helpers.get_file_size()` | no |
| View counter (non-admins only) | `/item/<id>` | `db.increment_counter()` → `content_stats.visited` | no |
| Recommended items (same category, random 10, platform-filtered) | `/item/<id>` | `db.get_content(random_order=True)` | no |
| Screenshot gallery | `/content/<id>/images` | `item['screenshots']` | no |
| Search (title ILIKE), sorted, paginated | `/search?query&sort&order&page` | `db.get_content(search=...)` | no |
| News list (paginated) and one news item (Markdown files rendered to HTML) | `/home`, `/news/<id>` | `db.get_news()` | no |
| RSS news feed | `/feed.xml` | | no |
| Store clients download page | `/download` | `config['clients']` | no |
| Old Ovi Store URLs → new IDs | `/<prefix>/<old_id>[/images\|/rate]` | `db.get_legacy_content_id()` | no |
| Client self-update metadata | `/version.xml`, `/changelog.xml` | static files | no |
| Update check for installed apps (UID + version) | `/applist.php?widget=1&id=...` | `client.format_results(widget=True)` | no |
| Rate an item 1–5 | `/content/<id>/rate` | `db.rate()` | **yes** |
| Register / confirm / login / logout / profile / change password / delete account | `auth` blueprint | | partly |
| Upload content | `/content/upload` | admin only | **admin** |

Everything above the "Rate" row goes into v1. The rest is phase 2 (auth) and phase 3 (admin).

---

## 2. Design rules

### 2.1 Base URL and versioning

- Prefix: `/api/v1`. A new blueprint `api` in `wunderland/blueprints/api.py`, registered with `url_prefix='/api/v1'`.
- A breaking change means `/api/v2`, served next to v1. Adding fields or endpoints is not breaking; clients must
  ignore fields they don't know.
- `GET /api/v1/` is the discovery document (section 4.1), so the client can check the server and its limits with
  one request.

### 2.2 Transport constraints of Symbian devices

These drive most of the quirks below:

- **Plain HTTP must work.** Many S60 devices can't negotiate modern TLS, which is why `external_url_for` keeps the
  request's scheme. Every API URL and every URL the API returns must work over `http://`. Absolute URLs in responses
  use the scheme of the request, through `helpers.external_url_for`, exactly like the XML clients.
- **Slow, metered links (GPRS/EDGE/3G).** Keep list payloads small (summary vs detail representations, 2.4), support
  and support gzip.
  - `docker/nginx.conf` lists `application/json` in `gzip_types`. Qt 4.7+'s
    `QNetworkAccessManager` sends `Accept-Encoding: gzip` and decompresses on its own.
- **JSON parsing on the device is weak.** Qt 4 has no `QJsonDocument` (that's Qt 5); the client will use
  `QScriptEngine` or a small C++ parser. So:
  - Shallow, predictable objects. At most two levels of nesting in list items.
  - **Every documented key is always present.** Missing values are `null`, empty lists are `[]`. Never omit keys.
  - Each field has one type. A field is never sometimes a string and sometimes a number.
  - Integers fit in 32 bits (all our IDs and sizes do; file sizes are under 2 GiB).
  - Output is UTF-8 (`application/json; charset=utf-8`). Set `app.json.ensure_ascii = False` for the API's provider,
    or keep Flask's default `\uXXXX` escapes if the device parser turns out to mishandle raw UTF-8 (to test on a
    device; see open questions).
- **Some HTTP stacks and operator proxies drop `PUT`/`PATCH`/`DELETE`** or rewrite error bodies. For the later write
  endpoints, accept `POST` with `X-HTTP-Method-Override: PATCH|PUT|DELETE` (only on POST), added in a
  `before_request` of the blueprint.
- **No `204 No Content`.** Some clients treat an empty body as a failure. Return `200` with a small JSON body instead.

### 2.3 Response envelope

Single resource:

```json
{"data": { ... }}
```

Collection:

```json
{
  "data": [ ... ],
  "meta": {"page": 2, "per_page": 10, "total": 57, "total_pages": 6}
}
```

Error (every 4xx/5xx under `/api/`, including 404 for unknown paths and 405):

```json
{
  "error": {
    "status": 400,
    "code": "invalid_parameter",
    "message": "sort must be one of: updated_at, created_at, id, title, rating",
    "details": {"parameter": "sort"}
  }
}
```

`code` is a stable machine string the client can switch on; `message` is English text for logs, not for display.
Codes: `bad_request`, `invalid_parameter`, `not_found`, `method_not_allowed`, `unauthorized` (reserved),
`forbidden` (reserved), `conflict` (reserved), `payload_too_large` (`POST /updates`), `rate_limited` (reserved),
`internal_error`, `service_unavailable`.

### 2.4 Representations

- **Summary** (in lists): what a list row needs: id, title, type, category, publisher, version, icon, rating, dates,
  platforms, download URL and size. No description, no screenshots.
- **Detail** (`GET /content/{id}`): summary + description, screenshots, addon, uid, file info.
- Field names are `snake_case`.
- IDs keep their DB types: content, category and news IDs are integers; content type and platform IDs are strings
  (`"apps"`, `"s60v3"`). The client must not assume all IDs are numeric.
- Timestamps: ISO 8601 in UTC with a `Z` suffix and no fractional seconds, e.g. `"2026-11-17T10:04:00Z"`.
  (News dates are RFC 1123 strings in `db.get_news()` today; the API must format from `created_at` itself; see 5.6.)
- URLs in responses are absolute (`external_url_for`), so the client never builds paths itself. That also lets the
  file layout (section 5.3) change later without breaking clients.

### 2.5 Pagination

- `?page=` (1-based, default 1) and `?per_page=` (default `config['per_page']`, max 50).
- `page < 1`, `per_page < 1` or `per_page > 50` → `400 invalid_parameter`. The web UI redirects in those cases; the
  API never redirects for parameter problems.
- `page > total_pages` → `200` with `"data": []` and the real `meta`. That way the client can stop at an empty page
  without a special case.
- `total_pages` is at least 1, like `max(1, ceil(total / per_page))` in the web views.
- Every list endpoint that reads `content` must pass a `limit`: `db.get_content()` returns the whole table when
  `limit` is `None`.

### 2.6 Filtering by platform

The web UI keeps the chosen platform in the cookie session. The API is stateless: the client sends
`?platform=<id>` on every request that filters (`/content`, `/categories`, `/content/{id}/related`).

- Comma-separated values are allowed (`?platform=s60v3,s60v5`); `db.get_content(platforms=[...])` already takes a
  list.
- Unknown platform IDs → `400 invalid_parameter` (not silently ignored), so a typo in the client shows up at once.
- No `platform` → no filtering, like the web UI with no platform selected.
- Quirk to keep: content with **no** rows in `content_platforms` matches every platform
  (`OR NOT EXISTS (...)` in `get_content` and `get_categories`).
- Quirk to decide: `platforms.parent_id` exists but no query uses it. See open question 1.

### 2.7 Sorting

- `?sort=` one of `VALID_SORT_FIELDS` keys (`updated_at`, `created_at`, `id`, `title`, `rating`), default `updated_at`.
- `?order=asc|desc`, default `desc`. The web UI uses `order=1|-1`; the API uses words. An unknown `sort` or `order`
  → `400` (the web UI silently falls back).
- The tiebreaker `content.id DESC` stays, so pages are stable.

### 2.8 Caching headers

- Reference data (`/content-types`, `/platforms`, `/categories`): `Cache-Control: public, max-age=3600`.
  `content_types` and `platforms` are cached per worker until restart anyway.
- Content lists, detail, news: `Cache-Control: no-cache`.
- `/content/{id}/related` (random order): `Cache-Control: no-store`.
- No ETags or `304`s: the old clients wouldn't send `If-None-Match`.
- The API never sets cookies (2.9), so there's no `Vary: Cookie`.

### 2.9 No cookie session, no CSRF

- API requests skip `load_global_data()` and `csrf.protect()`: no `g.platform` from the session, no session token
  lookup, and the session interface doesn't send `Set-Cookie`. Today those hooks check `request.endpoint in
  SESSIONLESS_ENDPOINTS`; extend the checks to `request.blueprint == 'api'`.
- CSRF protection isn't needed: the API won't accept cookie auth, and the later `Authorization: Bearer` header isn't
  sent by browsers on their own.
- `g.user` is `None` in v1. Phase 2 sets it from the `Authorization` header in the blueprint's own `before_request`.

---

## 3. Endpoint list

All paths are relative to `/api/v1`. All are `GET` (and `HEAD`) in v1 unless marked.

| Method | Path | Purpose | Phase |
|---|---|---|---|
| GET | `/` | Discovery: API version, limits, server time, links | 1 |
| GET | `/content-types` | All content types | 1 |
| GET | `/content-types/{type_id}` | One content type | 1 |
| GET | `/platforms` | All platforms | 1 |
| GET | `/platforms/{platform_id}` | One platform | 1 |
| GET | `/categories` | Categories, filter by type/platform/non-empty | 1 |
| GET | `/categories/{category_id}` | One category | 1 |
| GET | `/content` | Browse and search content | 1 |
| GET | `/content/{content_id}` | Item detail (counts a view) | 1 |
| GET | `/content/{content_id}/related` | Recommended items | 1 |
| GET | `/content/{content_id}/download` | Redirect to the file | 1 |
| GET | `/content/{content_id}/rating` | Rating aggregate | 1 |
| POST | `/updates` | Update check for installed apps (read-only POST) | 1 |
| GET | `/news` | News list | 1 |
| GET | `/news/{news_id}` | One news item | 1 |
| GET | `/clients` | Downloadable store clients (`config['clients']`) | 1 |
| GET | `/legacy/{prefix}/{old_id}` | Old Ovi Store ID → content | 1 |
| PUT | `/content/{content_id}/rating` | Rate 1–5 (own rating) | 2 |
| DELETE | `/content/{content_id}/rating` | Remove own rating | 2 |
| POST | `/auth/register`, `/auth/token`, `/auth/refresh`; DELETE `/auth/token` | Accounts and tokens | 2 |
| GET/PATCH/DELETE | `/me`; GET `/me/ratings`; POST `/me/password` | Own account | 2 |
| POST | `/content` (multipart) | Upload | 3 |
| PATCH/DELETE | `/content/{content_id}` | Edit / hide | 3 |

Phase 2 and 3 endpoints don't exist in v1: they return `404` like any unknown path, not `401`.

---

## 4. Endpoints in detail (phase 1)

### 4.1 `GET /`

```json
{
  "data": {
    "name": "Wunderland Store",
    "api_version": "1.0",
    "server_time": "2026-11-17T10:04:00Z",
    "per_page_default": 10,
    "per_page_max": 50,
    "sort_fields": ["updated_at", "created_at", "id", "title", "rating"],
    "links": {
      "content_types": "http://ovi.wunderwungiel.pl/api/v1/content-types",
      "platforms": "http://ovi.wunderwungiel.pl/api/v1/platforms",
      "categories": "http://ovi.wunderwungiel.pl/api/v1/categories",
      "content": "http://ovi.wunderwungiel.pl/api/v1/content",
      "news": "http://ovi.wunderwungiel.pl/api/v1/news",
      "clients": "http://ovi.wunderwungiel.pl/api/v1/clients",
      "web": "http://ovi.wunderwungiel.pl/home"
    }
  }
}
```

`server_time` lets the client spot a wrong device clock (common on old phones), which matters once tokens expire.
No DB access, so it's also a cheap reachability check (`/healthz` stays the infrastructure probe).

### 4.2 `GET /content-types`, `GET /content-types/{type_id}`

```json
{
  "data": [
    {"id": "apps", "name": "Applications", "prefix": "applications", "show_icons": true, "show_categories": true}
  ]
}
```

- `show_icons` / `show_categories` are UI hints the web templates use (themes, for example, may have no categories
  page). The client should honour them.
- `prefix` is the old Ovi Store URL prefix, needed only for `/legacy`.
- Order: by name, as `get_content_types()` returns. Not paginated (a handful of rows).
- Unknown `type_id` → `404 not_found`.
- Quirk: the web route `/content/<content_type_id>` takes the type ID; `qtstore` lower-cases it. The API matches
  exactly (`apps`, not `Apps`).

### 4.3 `GET /platforms`, `GET /platforms/{platform_id}`

```json
{"data": [{"id": "s60v3", "name": "S60 3rd Edition", "parent_id": "s60"}]}
```

Not paginated. Ordered by name.

### 4.4 `GET /categories`

Query: `type` (content type ID), `platform`, `non_empty` (`true`/`false`, default `true`).

```json
{
  "data": [
    {"id": 3, "name": "Utilities", "type_id": "apps", "content_count": 42}
  ]
}
```

- Default `non_empty=true` matches the web browse page (`only_with_content=True`): a category is listed only if it
  has visible content for the given platform.
- `content_count` is new: the number of visible items for that platform, which the client shows next to the name.
  It needs a change in `db.get_categories()` (a `LEFT JOIN LATERAL (SELECT COUNT(*) ...)` with the same platform
  clause, replacing the `EXISTS` when counts are requested). Cheap at this table size.
- Ordered by `type_id`, then `name`.
- `client_id` (the old Java client's category number) isn't exposed. It belongs to the XML API only.
- `GET /categories/{id}` returns one category (with `content_count` over all platforms, or for `?platform=`).
  Unknown ID → `404`.

### 4.5 `GET /content`

The single list endpoint for browsing, category pages and search.

Query:

| Param | Meaning |
|---|---|
| `type` | Content type ID (`apps`) |
| `category` | Category ID. If `type` is also given and the category belongs to another type → `400` (web flashes "Invalid category") |
| `platform` | Platform ID(s), section 2.6 |
| `q` | Title search, case-insensitive substring (`ILIKE`, metacharacters escaped as today). Trimmed; empty after trimming → `400`. Max 100 chars |
| `ids` | Comma-separated content IDs, max 50. Returns those items **in the given order**, like `db.get_items()`. Ignores `page`/`sort` |
| `uid` | Symbian UID (section 5.4), exact match. For "is this installed app in the store?" |
| `updated_since` | ISO 8601 timestamp; only items with `updated_at` later than it. For incremental sync / "what's new" |
| `sort`, `order` | Section 2.7 |
| `page`, `per_page` | Section 2.5 |

Response: collection of **summary** items.

```json
{
  "data": [
    {
      "id": 128,
      "title": "Opera Mini",
      "content_type": {"id": "apps", "name": "Applications"},
      "category": {"id": 3, "name": "Internet"},
      "publisher": "Opera Software",
      "version": "4.21(0)",
      "icon_url": "http://ovi.wunderwungiel.pl/static/content/icons/operamini.png",
      "rating": {"average": 4.3, "count": 12, "rounded": 4},
      "platforms": [{"id": "s60v3", "name": "S60 3rd Edition"}],
      "download": {
        "url": "http://ovi.wunderwungiel.pl/api/v1/content/128/download",
        "direct_url": "http://ovi.wunderwungiel.pl/static/content/files/operamini.sis",
        "size": 1048576,
        "external": false
      },
      "created_at": "2024-03-02T18:11:00Z",
      "updated_at": "2026-10-01T09:00:00Z",
      "links": {
        "self": "http://ovi.wunderwungiel.pl/api/v1/content/128",
        "web": "http://ovi.wunderwungiel.pl/item/128"
      }
    }
  ],
  "meta": {"page": 1, "per_page": 10, "total": 1, "total_pages": 1}
}
```

Notes:

- Only `visible = TRUE` rows, always (`get_content` already enforces it).
- `platforms` is sorted by name; an empty list means "all platforms" (2.6). The client should show that as "All".
- `rating`: see 4.8. Rating sort today sorts by the **rounded** average; keep that in v1 for parity with the web UI,
  or switch both to the exact average (open question 4).
- For `ids=`: unknown or hidden IDs are left out (no error); `meta.total` is the number returned. Duplicates are kept,
  as in `get_items()`. More than 50 IDs or a non-integer → `400`.
- Combining `q` with `type`/`category` is allowed. (The web search page can't, but `get_content` supports it.)

### 4.6 `GET /content/{content_id}`

**Detail** representation: summary fields plus:

```json
{
  "data": {
    "...": "all summary fields",
    "description": "Fast web browser.\nWorks on S60v3.",
    "uid": "0x2001C3A2",
    "screenshots": [
      {"url": "http://ovi.wunderwungiel.pl/static/content/screenshots/operamini1.jpg"}
    ],
    "addon": {
      "text": "Language pack",
      "url": "http://ovi.wunderwungiel.pl/static/content/files/operamini_addon.zip"
    },
    "links": {
      "self": "...", "web": "...",
      "related": "http://ovi.wunderwungiel.pl/api/v1/content/128/related",
      "rating": "http://ovi.wunderwungiel.pl/api/v1/content/128/rating"
    }
  }
}
```

- `description` is the raw text with `\n` line breaks, not HTML (the web UI runs `nl2br` and `qtstore` builds HTML
  around it; the native client renders text itself). `null` if empty.
- `addon` is `null` when there's neither `addon_text` nor `addon_file`; inside it, either field can be `null`
  (the upload form allows text without a file).
- `screenshots` are objects, not bare strings, so width/height can be added later without a breaking change.
  The list comes from `screenshot_prefix` + `screenshot_count`; files aren't checked on disk (same as the web UI).
- Unknown or hidden ID → `404 not_found`. A non-integer ID → `404` (Flask's `<int:>` converter).
- **View counting:** the web item page calls `db.increment_counter()` for non-admins. The API counts too, on this
  endpoint only (not on lists), and only when the response status is 200. That keeps
  `content_stats.visited` comparable across web and app. It's a side effect on a `GET`, which is a deliberate
  exception (like page-view counters elsewhere). The counter isn't exposed in v1 (the web UI doesn't show it either;
  open question 5).

### 4.7 `GET /content/{content_id}/related`

Query: `platform`, `limit` (default 10, max 20).

Same category and type, excluding the item, random order, platform-filtered (the web item page). Returns summary
items, no `meta` pagination (it's not pageable: random), but `meta.total` = number returned.
`Cache-Control: no-store`. Unknown item → `404`.

### 4.8 `GET /content/{content_id}/rating`

```json
{"data": {"content_id": 128, "average": 4.3, "count": 12, "rounded": 4, "distribution": {"1": 0, "2": 1, "3": 1, "4": 4, "5": 6}}}
```

- `average`: exact mean rounded to one decimal, `null` when `count` is 0.
- `rounded`: integer 0–5 as the web UI's stars show today (`ROUND(AVG(...))`, 0 when unrated).
- `distribution` keys are strings because JSON object keys are strings; all five are always present.
- `get_content()` today returns only the rounded average. The summary's `rating.average` and `rating.count` need the
  lateral subquery to return `AVG(rating)` and `COUNT(*)` too (keep `rating` as the rounded one for sorting).
- Phase 2 adds `"mine": 4` (or `null`) when the request carries a token.

### 4.9 `GET /content/{content_id}/download`

- `302` to the actual file. Target is `helpers.get_download_url(item, external=True)`: `latest_url` if set (it takes
  priority), otherwise the `/static/content/files/...` URL.
- Clients should use `download.url` (this endpoint) rather than `direct_url`. It gives one place to later add download
  counting, a TLS-downgrade proxy for HTTPS-only `latest_url` targets (5.5), or auth for paid/hidden content.
- `302`, not `307`/`308`: Symbian download managers and Qt 4 follow 302 reliably. (`QNetworkAccessManager` in Qt 4
  doesn't follow redirects by itself; the client must follow `Location`. Note in the client docs.)
- The response must not be JSON on success. If the item has no downloadable file, or the local file is missing →
  `404` JSON error.
- The file itself is served by the existing `content` endpoint (`send_from_directory`), which already supports
  `Range` requests, so downloads can resume.

### 4.10 `POST /updates`

The update check the old client does with `/applist.php?widget=1&id=...`, but by UID, which is what an installed
app actually knows. It's `POST` because the body can list many apps; it doesn't change anything.

Request (`Content-Type: application/json`):

```json
{"platform": "s60v3", "installed": [{"uid": "0x2001C3A2", "version": "4.20(0)"}, {"uid": "0xE0001234", "version": "1.0.0"}]}
```

Response:

```json
{
  "data": [
    {
      "uid": "0x2001C3A2",
      "installed_version": "4.20(0)",
      "update_available": true,
      "comparison": "numeric",
      "content": { "...": "summary item" }
    },
    {"uid": "0xE0001234", "installed_version": "1.0.0", "update_available": false, "comparison": null,
     "content": null}
  ]
}
```

- Max 100 entries, else `400`. Entries come back in request order; `content` is `null` when no visible item has
  that UID (for that platform, if given).
- Version comparison: normalise both sides with `helpers.to_version()` when they match the Symbian pattern, also
  accept dotted `a.b.c`, compare as integer tuples. If either side can't be parsed, `update_available` is
  `stored != installed` (string inequality), and the entry gets `"comparison": "string"` instead of `"numeric"`, so
  the client can word it as "different version" instead of "newer". `comparison` is always present.
- If several visible items share a UID (nothing prevents it), pick the most recently updated one.
- UIDs match case-insensitively (5.4); `uid` in the response is the one the client sent.
- Needs a `uid` filter in `get_content()` and an index on `content.uid` (later; table is small).
- As built:
  - `platform` is optional, one platform ID string; an unknown one is `400 invalid_parameter` (`parameter:
    "platform"`). Any `Content-Type` is accepted, since some device HTTP stacks can't set it. A body over 64 KiB is
    `413 payload_too_large`.
  - `400 bad_request`: the body isn't JSON, isn't an object, has no `installed` list, or lists more than 100
    entries. `400 invalid_parameter`: one bad field, with `parameter` set to its path and 0-based indexes:
    `installed[3]` (not an object), `installed[3].uid` (not `0x` plus 8 hex digits), `installed[3].version` (not a
    string of 1 to 64 characters). Unknown keys are ignored.
  - Versions: Symbian `a.b(c)` (through `to_version()`) or dotted `a[.b...]`, compared as integer tuples padded with
    zeros, so `1.2` equals `1.2.0`. `update_available` is `true` only when the stored version is higher. With
    `comparison: "string"`, both sides are compared after stripping whitespace.
  - When `content` is `null`, `update_available` is `false` and `comparison` is `null` (nothing was compared).
  - `Cache-Control: no-store` (the answer depends on the body). All UIDs are looked up in one query
    (`get_content(uids=[...])`, `lower(uid) = ANY(...)`). The response is unpaginated `{"data": [...]}`, duplicates
    kept.

### 4.11 `GET /news`, `GET /news/{news_id}`

Query: `page`, `per_page`.

```json
{
  "data": [
    {
      "id": 7,
      "title": "New games added",
      "created_at": "2026-11-01T12:00:00Z",
      "body": "<p>...</p>",
      "links": {"self": "...", "web": "http://ovi.wunderwungiel.pl/news/7"}
    }
  ],
  "meta": { "...": "pagination" }
}
```

- `body` is the HTML the web UI shows, the cached Markdown render from `_render_news()`. Qt 4's rich text
  (QLabel/QTextBrowser) understands a subset of HTML 4, which covers what Python-Markdown emits.
- **Quirk to fix:** `db.get_news()` silently drops rows whose Markdown file is missing, but `total` still counts them
  (and a page can come back short). For the API, either filter missing files before counting or accept the
  mismatch; the client must not assume `len(data) == per_page` on full pages anyway. Recommended: leave
  `get_news()` as is and document "pages may be short".
- `get_news()` returns `date` as a formatted RFC 1123 string; the API needs the raw `created_at`. Add it to the dict
  `get_news()` builds (`'created_at': row['created_at']`), keep `date` for the RSS feed and templates.
- Relative links/images inside news HTML (if any) should be made absolute, or the client can't follow them. Check
  current news files; if they only use absolute URLs, note that as a rule for authors instead.
- Unknown `news_id` → `404` (the web UI redirects home).

### 4.12 `GET /clients`

The `/download` page: `db.get_items(config['clients'])` as summary items, in config order. Empty list if
`clients` is empty (the web UI redirects). Lets the native client offer "other store clients" and, more usefully,
find **its own** latest version (open question 6 about a dedicated self-update endpoint).

### 4.13 `GET /legacy/{prefix}/{old_id}`

Resolves an old Ovi Store link (`/applications/4242`) to the new item, for a client that opens old URLs or QR codes.

- `200` with `{"data": {"content_id": 128, "content": { ...summary... }}}`, not a redirect: redirects to another
  JSON document are awkward for Qt 4 clients that don't auto-follow.
- Unknown prefix, unknown old ID, or hidden content → `404`.
- `categories_legacy` exists in the schema but no code reads it. If old category URLs exist in the wild, add
  `GET /legacy/{prefix}/categories/{old_id}` the same way; otherwise leave the table alone.

---

## 5. Data quirks the API has to handle

### 5.1 Hidden content

`content.visible = FALSE` hides an item everywhere: lists, detail, related, `ids=`, `uid` lookups, `updates`,
legacy lookups. Hidden items are `404`, never `403` or `410`, so their existence isn't revealed.

### 5.2 `file` vs `latest_url`

- A row has `file`, `latest_url`, or both (`CHECK` constraint). `latest_url` wins for downloads.
- Always go through `helpers.get_download_url` / `get_file_size` / `get_file_path`; never read `item['file']`.
- `download.size`: `get_file_size()` returns `None` when there's no local file (latest_url only) and **`0` when the
  file is missing on disk**. In the API, both become `null`; `0` would make a client show "0 B" or refuse to download.
- `download.external`: `true` when the URL is `latest_url` (another host). The client can warn that it may need
  HTTPS.

### 5.3 File naming convention

Files live under `content_dir` by convention (`files/<prefix>.<ext>`, `icons/<prefix>.png`,
`screenshots/<prefix><n>.jpg`). The API only ever returns full URLs, so clients never see this. `icon` defaults to
`Store.png`, which is a real file, so `icon_url` is never `null`.

### 5.4 UIDs

`content.uid` is either `NULL` or `0x` plus 8 hex digits (`0x2001C3A2`), set by hand in the DB (the upload form has
no UID field). The API returns it as stored and matches `uid=` and `/updates` case-insensitively.

### 5.5 HTTPS-only download targets

`latest_url` often points at hosts that require modern TLS (GitHub releases, for example), which many Symbian
devices can't connect to. v1 just marks these with `download.external`. Later the `/download` endpoint could proxy
or mirror them over plain HTTP (open question 3).

### 5.6 Dates

`content.created_at` / `updated_at` and `news.created_at` are `timestamptz`. Format with
`value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')`. The XML client's `versiondate` uses local server
time with no zone; the API doesn't copy that.

`updated_at` changes on any `UPDATE` (trigger), including edits that don't change the file. The client must not
treat a newer `updated_at` as "new version"; `/updates` compares versions.

### 5.7 MIME types of downloads

`send_from_directory` and `send_file` guess the MIME type from the extension. Python's built-in table doesn't know
`.sis`, `.sisx`, `.jar` or `.jad`; it learns them only from the host's `/etc/mime.types`. A desktop Linux usually has
that file, but the `python:*-alpine` image doesn't, so in Docker they went out as `application/octet-stream`, and
the Symbian download manager may then save instead of installing. Register them at startup (`mimetypes.add_type`):
`.sis` → `application/vnd.symbian.install`, `.sisx` → `x-epoc/x-sisx-app`, `.jar` → `application/java-archive`,
`.jad` → `text/vnd.sun.j2me.app-descriptor`. This also changes what the existing web and XML downloads send, which is
a fix, but should be tested on a device.

As built: the `add_type` calls are at the top of `wunderland/app.py`. Werkzeug adds `; charset=utf-8` to the JAD
type, as to every `text/*` type, which matches MIDP 2 (JAD files are UTF-8). The smoke test checks the exact
`Content-Type` of all four through `/static/content/files/` and of `file.sis` through `/StoreData/`; it fails with
the registration removed and `mimetypes.knownfiles` emptied, so it doesn't depend on the host. Still to do: install
a `.sis`/`.sisx` and a JAD/JAR from a real device once deployed.

### 5.8 Text fields

`title`, `description`, `publisher`, `addon_text` may have stray whitespace (the XML client `.strip()`s every
string). The API strips leading/trailing whitespace of string fields and turns empty strings into `null`.

### 5.9 Legacy route collision

The `legacy` blueprint has `/<prefix>/<int:legacy_id>`. `/api/<number>` would match it (and 404 because `api` isn't
a content type prefix). Harmless, but the API's 404 handler must decide by **path prefix** (`/api/`), because for an
unmatched URL `request.blueprint` is `None`; and for this collision it's `legacy_store`. Also, no content type may
ever get the prefix `api`.

---

## 6. Implementation outline

Order matters only where noted.

1. **Blueprint skeleton** (`wunderland/blueprints/api.py`, export it from `blueprints/__init__.py`, register in
   `app.py` with `url_prefix='/api/v1'`).
   - `app.py`: skip `load_global_data()`, `csrf.protect()` and cookie refresh for `request.blueprint == 'api'`.
   - JSON error handlers: the app-level 404/500 handlers check `request.path.startswith('/api/')` and return the error
     envelope (keep the XML-blueprint branch as is). Add 400 and 405. A helper `api_error(status, code, message,
     **details)` raises an `HTTPException` subclass carrying the JSON response, so views can `raise` it.
   - `after_request` for the blueprint: `Content-Type` charset, `Cache-Control` per endpoint
     (a small decorator `@cache('public', 3600)` / `@cache('no-store')`).
   - Done. The decorator is `@cache('public', max_age=3600)`; unknown `/api/` URLs get the JSON treatment by path
     (`is_api_request()`), not by blueprint.
2. **Parameter parsing helpers** in the blueprint: `parse_page()`, `parse_platforms()`, `parse_sort()`,
   `parse_bool()`, `parse_ids()`, `parse_timestamp()`. Each raises `api_error(400, 'invalid_parameter', ...)`.
   Werkzeug's `type=int` silently returns the default on bad input; the API must not, so parse manually.
   - Done.
3. **Serializers** in a new `wunderland/api_format.py` (keep the blueprint thin): `content_summary(item)`,
   `content_detail(item)`, `category(row)`, `news(row)`, `rating(...)`, `iso(dt)`. They take the dicts
   `_format_content()` already produces, so `db.py` stays the single place for SQL.
   - Done. Also there: `content_type()`, `platform()`, `download()`, `rating_detail(item, distribution)` (4.8),
     `text()` (5.8; also turns `\r\n` into `\n`).
   - Links to API views use the endpoint names in `API_ENDPOINTS` (`api.content_item`, `api.content_related`,
     `api.content_rating`, `api.content_download`, `api.news_item`). Step 5 must name its views that way; until
     they exist, serializers that link to them raise `BuildError`.
   - `category.content_count` is `null` unless the rows come from `get_categories(with_counts=True)`.
   - `download.size` is `null` for external downloads (the local file's size says nothing about `latest_url`) and
     for missing files.
4. **`db.py` changes**:
   - `get_content()`: return `rating_average` and `rating_count` next to `rating`; add `uid`, `updated_since`
     filters. No change to existing callers' results except the extra keys.
   - `get_categories()`: optional `with_counts=True`.
   - `get_news()`: add raw `created_at`.
   - New `get_rating_distribution(content_id)`.
   - Done. Details:
     - `get_content(uid=...)` compares case-insensitively (5.4). `updated_since` matches `updated_at` strictly
       later than the timestamp.
     - `rating_average` is the exact `AVG()` (a `Decimal`, `None` when unrated); `rating_count` is an `int`.
     - `get_categories(with_counts=True)` adds `content_count` (visible items, on `platform_id` if given), and only
       `only_with_content` drops empty categories. Without counts, `platform_id` still implies "non-empty", as the
       web UI expects. So `/categories?non_empty=false&platform=...` lists every category with that platform's counts.
     - `get_news()` returns `created_at`. Pages may still come back short (4.11).
5. **Endpoints** in the order of section 4. Reference data first (simplest, exercises the envelope and caching),
   then `/content`, detail, related, download, rating, news, clients, legacy, updates.
   - Reference data done. `/` lists links only to endpoints that exist; add each one as it's built.
     `/categories` takes several platforms like `/content` (`get_categories(platforms=[...])`), and an unknown
     `type` is `400 invalid_parameter`. Integer path IDs are capped at 2³¹−1, so bigger ones are `404`, not a
     Postgres error.
   - Content endpoints done. `ids=` can't be combined with the other filters of `/content` (`400`); it still
     ignores `page`, `per_page` and `sort`, and its `meta` says page 1 with `per_page` = the number returned.
     An unknown `category` is `400`, and `uid=` must be `0x` plus 8 hex digits. `/download` checks that a local
     file exists before redirecting; `latest_url` targets aren't checked. `HEAD` on the detail doesn't count a
     view.
   - News done. Pages may be short (4.11), and `/` links to `/news`. There were no news files in the local
     `content/news/` to check for relative links, so the rule for authors is: news Markdown uses absolute URLs
     only (links and images), because the API passes the HTML through unchanged. The files on the production
     server still need that check once.
   - Clients done. `/clients` is an unpaginated `{"data": [...]}` like the reference data, but `no-cache`, since
     items change. Hidden and unknown IDs in `config['clients']` are left out; `/` links to it.
   - Legacy done. `/legacy/{prefix}/{old_id}` is `no-cache` (the summary changes) and has no link in `/`, since it's
     a URL template. Unknown prefix, unknown or oversized old ID and hidden content are all the same `404`. The
     smoke test checks that `/api/42`, which the `legacy` blueprint matches (5.9), is still a JSON 404.
   - Updates done (details at the end of 4.10). That completes step 5.
6. **nginx**: add `application/json` to `gzip_types`.
   - Done.
7. **MIME types** (5.7), separately, since it affects the existing endpoints too. Done; see "As built" in 5.7.
8. **Tests**: extend `tests/smoke_test.py` (it already seeds a content row, category, platform, legacy row and news):
   - every v1 endpoint returns 200 and valid JSON with the envelope;
   - unknown path under `/api/v1/` → JSON 404; wrong method → JSON 405;
   - bad `page`/`sort`/`platform` → 400 with `invalid_parameter`;
   - no `Set-Cookie` on API responses;
   - `/content/{id}/download` → 302 to the file URL;
   - `/updates` with the fixture's UID and an older version → `update_available: true`;
   - the existing web/XML checks still pass (regression guard for the `app.py` hook changes).
9. **Reference doc** for client authors: turn sections 2–4 into `docs/api.md` once the endpoints exist, with the
   examples taken from real responses.
   - Done. The examples come from a throwaway database seeded with example data. `docs/api.md` describes the API as
     built; where this plan and the code differ, the code and `docs/api.md` are right.

---

## 7. Phase 2: authentication (reserved, not built in v1)

Constraints worked out now so v1 doesn't block it:

- **Transport:** tokens will often travel over plain HTTP (2.2). Anything sent in `Authorization` can be sniffed on
  those devices. That argues for **opaque, revocable, DB-backed tokens** (the existing `sessions` table, or a new
  `api_tokens` table with a `client`/`device_name` column) over long-lived JWTs: a stolen JWT can't be revoked before
  it expires without a denylist, which brings back the DB lookup anyway. If JWTs are still wanted: short-lived
  access JWT (15–60 min) + opaque refresh token in the DB.
- Store only a hash (SHA-256) of each token in the DB, unlike the current `sessions.token`.
- `POST /auth/token` with `{"email", "password"}` → `{"access_token", "token_type": "Bearer", "expires_at",
  "refresh_token"}`. Unconfirmed users → `403 email_not_confirmed`. Reuse `db.check_credentials()` (it already
  rejects passwords over 72 bytes for bcrypt).
- `POST /auth/refresh`, `DELETE /auth/token` (logout; via method override where needed).
- `POST /auth/register`: same validation as the web form (`auth.register`), sends the same confirmation email; the
  confirmation link stays a web page.
- `GET /me`, `PATCH /me`, `POST /me/password` (`db.change_password()` already revokes other sessions; make it revoke
  API tokens too), `DELETE /me`.
- `PUT /content/{id}/rating` `{"rating": 1..5}` → upsert via `db.rate()`; `DELETE` removes it (new DB function).
  `GET /content/{id}/rating` gains `mine`.
- Brute-force protection on `/auth/token` (rate limiting per IP/account) before going live; the web login has none
  either.
- Clock skew: `server_time` in `/` (4.1) lets the client compute `expires_at` relative to the server clock.
- Admins: `role = 'admin'` from `users`. View counting skips admins, as on the web.

## 8. Phase 3: admin (reserved)

- `POST /content` multipart, same fields and checks as `store.upload` (prefix, icon PNG, screenshots JPG,
  file or `latest_url`, exclusive file creation and cleanup on error). Move that logic out of the view into a shared
  function first, so the web form and the API can't drift.
- `PATCH /content/{id}` for metadata; `DELETE /content/{id}` sets `visible = FALSE` (soft delete).
- `POST /news`, `PATCH /news/{id}`: news are DB rows + Markdown files; same pattern.
- `client_max_body_size 0` in nginx already allows large uploads.

---

## 9. Open questions

1. **Platform hierarchy.** `platforms.parent_id` is unused. Should `?platform=s60v5` also return content tagged
   with its ancestors (or descendants, depending on how the tree is modelled)? Recommendation: v1 matches exactly,
   like the web UI; if the hierarchy means "can run", add expansion server-side later (it's a non-breaking change
   to results, but it changes what clients see, so decide before the client ships).
2. **Raw UTF-8 vs `\u` escapes** in JSON: depends on the device-side parser. Test with the first client build.
3. **HTTPS-only `latest_url` targets**: mirror, proxy, or leave to the user?
4. **Rating sort**: keep sorting by the rounded average (web parity), or switch web and API to the exact average with
   `count` as tiebreaker?
5. **Expose view counts** (`content_stats.visited`) as `views`, and add `sort=popular`? Cheap to add.
6. **Client self-update**: `version.xml`/`changelog.xml` serve the old Java/Qt client. The new native client can use
   `/updates` with its own UID, or a dedicated `GET /client-release?client=<name>` returning version, changelog and
   download URL. Recommendation: `/updates` with its own UID, no special endpoint.
7. **Rate limiting** for the public read API: none today on the web either. Leave to nginx (`limit_req`) if needed.
8. **`categories_legacy`**: needed by anything, or dead data?
