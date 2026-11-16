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

To use a different UID, build with `docker compose build --build-arg APP_UID=<uid> --build-arg APP_GID=<gid>`.
