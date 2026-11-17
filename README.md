# Wunderland Store

A revival project of the Nokia/Ovi Store. It's a web store for apps, games and themes for Symbian devices, with support for native clients.

## Running with Docker

```sh
cp .env.example .env
cp config.yaml.example config.yaml
sudo chown -R 1000:1000 content
docker compose up -d --build
```

Before the first start:

- In `.env`, set a real `POSTGRES_PASSWORD`. The other values have working defaults, and each one is explained in the file.
- In `config.yaml`, set `secret_key` to a long random string and `base_url` to the store's public address. Fill in `email` if you want registration emails to go out. You can leave out the `database` section, because in Docker the app reads it from `.env`.
- The app runs as UID 1000, and `content/` (uploaded files, icons, screenshots and news) must be writable by that user. To use another UID, set `APP_UID` and `APP_GID` in `.env`.

The store then listens on `127.0.0.1:8080`, which you can change with `BIND_ADDRESS` and `PORT`. It's meant to sit behind your own reverse proxy (with HTTPS). On the first start, Postgres creates the database from `db/schema.sql`.

`docker compose ps` should show `app` and `db` as healthy. A `clean` service deletes expired unconfirmed accounts and sessions once a day.

To change something in `compose.yaml` only on your machine, put it in a `compose.override.yaml`. Compose reads that file automatically and git ignores it.

## Running without Docker

You need Python 3 and a PostgreSQL database loaded from `db/schema.sql`.

```sh
pip install -r requirements.txt
cp config.yaml.example config.yaml   # then fill in secret_key, base_url and database
flask --app wunderland.app run --debug
```

Run commands from the repo root. For production, use `gunicorn wunderland.app:app`, which reads `gunicorn.conf.py` and listens on `127.0.0.1:8000`. Put a reverse proxy in front of it. The app trusts the proxy's `X-Forwarded-*` headers, so anyone who can reach the port directly can fake the client address, host and scheme. If you change the address with `GUNICORN_BIND`, keep the port closed to everything but the proxy. Add a daily cron job for the cleanup:

```sh
flask --app wunderland.app clean
```

To use a config file somewhere else, point `WUNDERLAND_CONFIG` at it.

## Smoke test

There is no test suite, but there is a script that requests every page and both client APIs and checks the responses:

```sh
python -m tests.smoke_test
```

Run it against an empty, throwaway database created from `db/schema.sql`. Point `config.yaml` at it, and remember that the `POSTGRES_*` environment variables override that section when set. It refuses to start if the tables already hold data. It adds its own test data, plus a few files under `content/`, and removes all of it when it finishes.

## Upgrading from the old layout

Older checkouts kept the code and `config.yaml` in `app/`, uploads in `Ovi/` and an untracked `compose.yaml`. To move a server to the current layout:

1. Stop the stack while the old files are still in place: `docker compose down`.
2. Move the old `compose.yaml` aside so `git pull` can create the new one: `mv compose.yaml compose.yaml.old`.
3. `git pull`.
4. `mv app/config.yaml config.yaml`
5. Copy the uploads: `sudo cp -a Ovi/. content/`, then `sudo chown -R 1000:1000 content`. Delete `Ovi/` once the store shows them.
6. Add the new settings from `.env.example` to your `.env`. The `POSTGRES_*` values must stay the ones the database was created with. Copy any local changes from `compose.yaml.old` (such as `TZ`) too.

   In Docker the app now ignores the `database` section of `config.yaml` and connects with the `POSTGRES_*` values from `.env`. If the two name different databases (for example, you created a second one by hand and pointed `config.yaml` at it), the upgraded store would open the other one and look empty, without any error. Compare `name` in `config.yaml` with `POSTGRES_DB` in `.env` and, if they differ, set `POSTGRES_DB` to the database that holds the data. Do the same for `user` and `password`.
7. `docker compose up -d --build`, then check `docker compose ps`.

The database volume keeps its name, so the data stays where it was. Don't rename the checkout directory, because compose names the volume after it and would start on a new, empty one. Containers no longer have fixed names, so use `docker compose exec db psql ...` instead of `docker exec wunderland-db ...`.
