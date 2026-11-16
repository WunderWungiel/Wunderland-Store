## Wunderland Store

This project aims to partially revive the functionality of the Nokia Store.
This will allow users to use web version of Nokia/Ovi Store as in 2015, and also it will be a place for downloading apps, games and themes.

To do:

 - [x] Revive web interface
 - [x] Create and fill the apps / games / themes database
 - [x] Create a Java / Qt client that would open / embed website.

Compatibility: Symbian S60v3 and later.

Configure `base_url` in `app/config.yaml` to the public HTTP(S) URL of the store
(including any deployment path prefix). Confirmation emails, feeds and client
links use this value rather than the incoming Host or forwarded headers.

Run the app behind a trusted reverse proxy that replaces forwarded headers.
Port 8080 must only be reachable through that proxy; the Compose example binds
it to localhost. For a proxy on another host or container network, restrict
access with network/firewall rules rather than publishing it to the Internet.

Set `secret_key` in `app/config.yaml` to a random signing key (for example,
from `python -c 'import secrets; print(secrets.token_hex(32))'`). The store
refuses to start if the key is missing or empty.
