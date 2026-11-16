## Wunderland Store

This project aims to partially revive the functionality of the Nokia Store.
This will allow users to use web version of Nokia/Ovi Store as in 2015, and also it will be a place for downloading apps, games and themes.

To do:

 - [x] Revive web interface
 - [x] Create and fill the apps / games / themes database
 - [x] Create a Java / Qt client that would open / embed website.

Compatibility: Symbian S60v3 and later.

### Running with Docker

The app container runs as UID/GID 1000, so the host's `./Ovi` directory (mounted as the store content) must be writable by that user for admin uploads to work:

```sh
sudo chown -R 1000:1000 Ovi
```

This also applies when upgrading: older images ran as root, so an existing `./Ovi` is root-owned and uploads fail with a permission error until it is chowned.

To use a different UID, set `APP_UID` and `APP_GID` in `.env`.

The `clean` service runs `flask --app wunderland.app clean` once a day to delete expired unconfirmed users and expired sessions. Without Docker, run that command from cron instead.

`compose.yaml` is committed. Put local changes in `.env` or in a `compose.override.yaml`, which compose reads automatically and git ignores.

### Upgrading from an untracked compose.yaml

`compose.yaml` used to be copied from `compose.yaml.example` and is now committed. It no longer sets container names, so the containers are now called `<project>-app-1`, `<project>-db-1` and so on, where the project name is the checkout directory's name in lowercase. Use `docker compose exec db ...` instead of `docker exec wunderland-db ...`. The database volume keeps its name, so the data stays where it is.

1. Stop the old stack while the old file is still in place: `docker compose down`.
2. Rename the old file so `git pull` can create the new one: `mv compose.yaml compose.yaml.old`. Move anything it changed (such as `TZ`) into `.env`.
3. `git pull`.
4. `docker compose up -d --build`.

The app containers now connect with `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` from `.env`, and with `db` as the host, so the `database` section of `config.yaml` is ignored in Docker. Check that `.env` holds the credentials the database was created with.

Don't rename the checkout directory: the volume name comes from it, and compose would start on a new, empty volume.

### Smoke test

`app/scripts/smoke_test.py` requests every route, including `/applist.php` and `/StoreData/storeIndex.xml`, through the Flask test client and checks the responses. It needs an empty database created from `db/schema.sql`, with `config.yaml` pointing at it. It fills the tables with its own fixtures, writes a few files under `static/content`, and removes both when it finishes. It refuses to run if those tables already hold data.

```sh
cd app && python scripts/smoke_test.py
```
