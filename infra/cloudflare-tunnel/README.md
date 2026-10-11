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

Every path on the adapter is reachable, not just `/trigger`:

- `POST /trigger` needs a valid, fresh, unreplayed signature. Anything else is a 401.
- `GET /health` answers `{"status":"ok"}` to anyone.
- `GET /status/<run_id>` returns a run's task text and PR link to anyone who knows its 8-character id.

To expose only what a sender needs, restrict the ingress rule in `config.yml` with `path: ^/(trigger|health)$`.
