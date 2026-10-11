# Cloudflare Tunnel: factory.svensonlabs.dev

Exposes the intake adapter, which listens on `127.0.0.1:7654`, at `https://factory.svensonlabs.dev`.
The adapter stays bound to localhost. Only the tunnel reaches the internet.

| File | Installed at |
|---|---|
| `config.yml` | `~/.cloudflared/config.yml` |
| `com.cloudflare.cloudflared.plist` | `~/Library/LaunchAgents/` |

The tunnel's credentials file (`~/.cloudflared/<tunnel-id>.json`) and `cert.pem` are secrets. They are never committed.

## Set up again

```bash
cloudflared tunnel login                                    # authorize in a browser
cloudflared tunnel create the-factory                       # prints the tunnel id
# put the id in config.yml, then copy it to ~/.cloudflared/
cloudflared tunnel route dns the-factory factory.svensonlabs.dev
cp com.cloudflare.cloudflared.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

## Why the plist is checked in

`cloudflared service install` writes a plist that runs bare `cloudflared`. That prints "use `cloudflared tunnel run`" and exits 1,
so launchd keeps restarting it. The checked-in plist adds `tunnel run`.

It is a per-user agent, so it starts at login, like the factory adapter. `sudo cloudflared service install` would start at boot
but reads `/etc/cloudflared/`, not `~/.cloudflared/`, so the config and credentials would have to be copied there.

## What is public

The ingress rule in `config.yml` routes only `^/(trigger|health)$`. Every other path gets the tunnel's 404, so `/status/<run_id>`
and the API docs are not reachable from outside. The adapter has no docs routes at all.

- `POST /trigger` needs a valid, fresh, unreplayed signature, else 401. A signed request is refused with 429 while 5 runs are
  pending or 30 were queued in the last 24 hours.
- `GET /health` answers `{"status":"ok"}` to anyone.

`/status/<run_id>` still works on `127.0.0.1:7654`.
