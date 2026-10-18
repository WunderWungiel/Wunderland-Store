# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Wunderland Store is a partial revival of the Nokia/Ovi Store (circa 2015) for Symbian S60v3 and later devices: a Flask web store for apps, games and themes, plus the endpoints that the on-device Java/Qt clients call.

## Running

There is no test suite, linter config or build step. The only formatter setting is autopep8 with `--max-line-length=120` (`.vscode/settings.json`).

Config: copy `app/config.yaml.example` to `app/config.yaml` (gitignored). `app/utils/config.py` loads it at import time, so nothing under `utils` imports without it. Docker also copies it into the image, so it has to exist before `docker compose build`.

- **Docker (main path):** `cp compose.yaml.example compose.yaml && cp .env.example .env`, then `docker compose up --build`. The app listens on host port 8080 and runs gunicorn with 8 workers (`app/entrypoint.sh`). Postgres 18 is set up from `db/database.psql` through `db/init-db.sh`, which only runs when the `db_data` volume is empty. `./Ovi` on the host is mounted as `app/static/content` (the uploaded files, icons, screenshots and news). In Docker, set `database.host` in `config.yaml` to `db`.
- **Local:** `pip install -r app/requirements.txt`, then from inside `app/`: `flask --app main run --debug` or `gunicorn main:app`. Imports are relative to `app/` (`from utils import ...`), so commands must run from that directory.
- **Maintenance:** `python app/scripts/clean.py` deletes expired unconfirmed users and expired sessions.

## Architecture

- `app/main.py` creates the Flask app, registers five blueprints, applies `ProxyFix` (it expects to sit behind a reverse proxy), and in `before_request` loads `g.platform` (the device platform the user picked, kept in the session) and `g.user` (looked up from a session token in the DB `sessions` table, not from Flask session data alone).
- `app/utils/db.py` holds all SQL: raw psycopg 3 queries through one module-level `ConnectionPool` using `dict_row`. There is no ORM. `get_content()` is the central query used by most pages. It aggregates platforms and the average rating and uses `COUNT(*) OVER()` for pagination totals, and `_format_content()` reshapes the rows (nested `category`, `platforms`, `screenshots` list, `content_type`). Sorting is allowlisted through `VALID_SORT_FIELDS` because the column is put into the SQL with an f-string.
- Blueprints (`app/utils/blueprints/`):
  - `store`: the main web UI (browse, item, search, rate, news, RSS feed, admin-only `/content/upload`).
  - `auth`: login, registration with email confirmation (`utils/email.py`, SMTP over SSL), profile.
  - `legacy`: maps old Ovi Store URLs (`/<type prefix>/<old id>`) to new content IDs using the `content_legacy` table, with 307 redirects.
  - `client`: an XML API for the Java/Qt Symbian client (`/applist.php`, `/version.xml`, `/changelog.xml`). Client category IDs come from `categories.client_id`; the IDs 0 and 12 are hardcoded as "all apps" and "all games".
  - `qtstore`: the `/StoreData/...` index and file endpoints for a separate Qt store client.
- `config.yaml` decides which platform IDs the `client` and `qtstore` endpoints return (`platforms.*`), which content IDs show up as downloadable clients (`clients`), and the page size (`per_page`).
- Content files are stored by naming convention, not by DB paths: `static/content/files/<prefix>.<ext>`, `icons/<prefix>.png`, `screenshots/<prefix><n>.jpg` (the DB stores `screenshot_prefix` and `screenshot_count`). A content row can have a `latest_url` (for example a "latest release" link) in place of or as well as `file`, and `latest_url` takes priority. Always build download links, sizes and paths with `get_download_url` / `get_file_size` / `get_file_path` in `utils/utils.py` rather than reading `item['file']` directly.
- `utils/utils.py` converts between Symbian version strings (`1.02(3)`) and dotted versions (`1.2.3`).
- DB schema: `db/database.psql` (a pg_dump). Schema changes go there by hand; there is no migration tool. The `update_updated_at_column` trigger maintains `content.updated_at`.
