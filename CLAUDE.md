# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Wunderland Store is a partial revival of the Nokia/Ovi Store (circa 2015) for Symbian S60v3 and later devices: a Flask web store for apps, games and themes, plus the endpoints that the on-device Java/Qt clients call.

## Running

There is no test suite, linter config or build step, but `python -m tests.smoke_test` requests every route against an empty database (see the README). The only formatter setting is autopep8 with a max line length of 120 (`pyproject.toml`, mirrored in `.vscode/settings.json`).

Run every command from the repo root; `wunderland/` is a package with relative imports.

Config: copy `config.yaml.example` to `config.yaml` at the repo root (gitignored), or point `WUNDERLAND_CONFIG` at another file. `wunderland/config.py` loads and validates it at import time, so nothing in the package imports without it. The `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` env vars override the `database` section when set.

- **Docker (main path):** `cp .env.example .env`, then `docker compose up --build`. `compose.yaml` is committed; local changes go in `.env` or a gitignored `compose.override.yaml`. The image holds only the code (`.dockerignore` is an allowlist); `config.yaml` and `./content` are mounted at run time under `/srv`. gunicorn listens on port 8000 inside the container (`gunicorn.conf.py`, `WEB_CONCURRENCY` workers), and the nginx `proxy` service (`docker/nginx.conf`) publishes it on `${BIND_ADDRESS}:${PORT}` (default `127.0.0.1:8080`). The app and db services have healthchecks; the app's uses `/healthz`, which checks the DB and skips the session lookup. Postgres 18 is set up from `db/schema.sql`, which the postgres image's entrypoint only runs when the `db_data` volume is empty. The compose file sets no project name or container names, so the volume is named after the checkout directory; use `docker compose exec db ...`.
- **Local:** `pip install -r requirements.txt`, then `flask --app wunderland.app run --debug` or `gunicorn wunderland.app:app`.
- **Maintenance:** `flask --app wunderland.app clean` (`wunderland/cli.py`) deletes expired unconfirmed users and expired sessions. In Docker the `clean` compose service runs it once a day; outside Docker it needs a cron job.

## Architecture

- `wunderland/app.py` creates the Flask app, registers five blueprints, applies `ProxyFix` (it expects to sit behind a reverse proxy), and in `before_request` loads `g.platform` (the device platform the user picked, kept in the session) and `g.user` (looked up from a session token in the DB `sessions` table, not from Flask session data alone). File endpoints and `/healthz` skip that lookup (`SESSIONLESS_ENDPOINTS`).
- `wunderland/db.py` holds all SQL: raw psycopg 3 queries through one module-level `ConnectionPool` using `dict_row`. There is no ORM. `get_content()` is the central query used by most pages. It aggregates platforms and the average rating and uses `COUNT(*) OVER()` for pagination totals, and `_format_content()` reshapes the rows (nested `category`, `platforms`, `screenshots` list, `content_type`). Sorting is allowlisted through `VALID_SORT_FIELDS` because the column is put into the SQL with an f-string.
- Blueprints (`wunderland/blueprints/`):
  - `store`: the main web UI (browse, item, search, rate, news, RSS feed, admin-only `/content/upload`).
  - `auth`: login, registration with email confirmation (`wunderland/mail.py`, SMTP over SSL), profile.
  - `legacy` (endpoint prefix `legacy_store`): maps old Ovi Store URLs (`/<type prefix>/<old id>`) to new content IDs using the `content_legacy` table, with 307 redirects.
  - `client`: an XML API for the Java/Qt Symbian client (`/applist.php`, `/version.xml`, `/changelog.xml`). Client category IDs come from `categories.client_id`; the IDs 0 and 12 are hardcoded as "all apps" and "all games".
  - `qtstore`: the `/StoreData/...` index and file endpoints for a separate Qt store client.
- `config.yaml` decides which platform IDs the `client` and `qtstore` endpoints return (`platforms.*`), which content IDs show up as downloadable clients (`clients`), and the page size (`per_page`).
- Uploaded content lives outside the package, in `content_dir` (default `content/` at the repo root; `CONTENT_DIR` in `config.py`). The `content` endpoint in `app.py` serves it at the old `/static/content/...` URLs, which device clients and old links rely on. Only the directory skeleton and the default icon `content/icons/Store.png` are tracked.
- Content files are stored by naming convention, not by DB paths: `files/<prefix>.<ext>`, `icons/<prefix>.png`, `screenshots/<prefix><n>.jpg` under the content directory (the DB stores `screenshot_prefix` and `screenshot_count`). A content row can have a `latest_url` (for example a "latest release" link) in place of or as well as `file`, and `latest_url` takes priority. Always build download links, sizes and paths with `get_download_url` / `get_file_size` / `get_file_path` in `wunderland/helpers.py` rather than reading `item['file']` directly.
- `wunderland/helpers.py` also converts between Symbian version strings (`1.02(3)`) and dotted versions (`1.2.3`).
- DB schema: `db/schema.sql` (a pg_dump). Schema changes go there by hand; there is no migration tool. The `update_updated_at_column` trigger maintains `content.updated_at`.
