# Cloudflare Tunnel: factory.svensonlabs.dev and dash.svensonlabs.dev

Exposes the intake adapter, which listens on `127.0.0.1:7654`, at `https://factory.svensonlabs.dev` (intake) and `https://dash.svensonlabs.dev` (the Command dashboard).
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
cloudflared tunnel route dns the-factory dash.svensonlabs.dev
cp com.cloudflare.cloudflared.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

## Why the plist is checked in

`cloudflared service install` writes a plist that runs bare `cloudflared`. That prints "use `cloudflared tunnel run`" and exits 1,
so launchd keeps restarting it. The checked-in plist adds `tunnel run`.

It is a per-user agent, so it starts at login, like the factory adapter. `sudo cloudflared service install` would start at boot
but reads `/etc/cloudflared/`, not `~/.cloudflared/`, so the config and credentials would have to be copied there.

## Version

`cloudflared` 2026.10.0 (upgraded from 2026.5.0 with `brew upgrade cloudflared`, then `launchctl kickstart -k gui/$(id -u)/com.cloudflare.cloudflared`).
After an upgrade, check the agent's error log for four `Registered tunnel connection` lines and `/health` for a 200.

## Who can reach it

Three layers, outermost first:

1. **Cloudflare rate limit** on `/trigger`: more than 5 requests in 10 seconds from one IP are blocked with a 429 for 10 seconds.
2. **Cloudflare Access**, on the whole hostname. Application `factory`, policy `Machine clients`, action Service Auth, with a 401 response for
   anything else. Two service tokens are allowed: `grok-bot` (for the intake bot) and `factory-ops` (for the operator's own checks; its
   id and secret are `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` in `.env`). A request sends them as `CF-Access-Client-Id` and
   `CF-Access-Client-Secret` headers.
3. **The adapter's signature** on `/trigger`: every call also needs the HMAC headers (`X-Hub-Signature-256`, `X-Factory-Timestamp`),
   which the Access token does not replace.

The ingress rule in `config.yml` routes only `^/(trigger|health)$` on this hostname. Every other path gets the tunnel's 404. The adapter has no docs
routes, and `/status/<run_id>` works only on `127.0.0.1:7654`.

`POST /trigger` needs a valid, fresh, unreplayed signature, else 401. A signed request is refused with 429 while 5 runs are pending
or 30 were queued in the last 24 hours. Rejected requests are logged to `.factory-logs/rejected.jsonl` (never the body or signature).

Measured on 2026-10-11 against the live host (status codes):

| Path | No token | Wrong token | `factory-ops` token |
|---|---|---|---|
| `GET /health` | 401 | 401 | 200 |
| `POST /trigger` (unsigned) | 401 | 401 | 401 (from the adapter) |
| `GET /docs`, `/redoc`, `/openapi.json` | 401 | 401 | 404 |
| `GET /status/<id>` | 401 | 401 | 404 |
| `GET /` | 401 | 401 | 404 |

Twelve unsigned `POST /trigger` calls in a row with the token gave 401 five times, then 429 seven times.

## dash.svensonlabs.dev

The operator's dashboard. Cloudflare Access application `command` covers the whole hostname with an email login policy for the operator. The ingress rule routes only `^/(command(/data)?)?$`, so `/`, `/command` and `/command/data` reach the adapter. `/trigger`, `/status/<id>`, `/heartbeat` and every other path get the tunnel's 404 on this hostname, and `/command` gets a 404 on `factory.svensonlabs.dev`. Checked with `cloudflared tunnel --config config.yml ingress rule <url>`.

Rotate the `grok-bot` token in the Cloudflare dashboard (Zero Trust, Access, Service credentials). Rotating the webhook secret is a separate
step, described in `factory/intake/README.md`.
