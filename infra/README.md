# Rebuild the factory host

Everything the factory needs is in this repo except three secrets: `.env`, and the tunnel's
`~/.cloudflared/<tunnel-id>.json` and `cert.pem`. `infra/backup-secrets.sh` keeps those recoverable. With a backup,
a rebuild is about 50 minutes of the steps below. Without one, every secret must be reissued at its provider, and the
tunnel recreated, which changes its id in `config.yml`.

## Keep a secrets backup

After setting up, and after any secret rotation:

```bash
infra/backup-secrets.sh ~/factory-secrets-$(date +%F).dmg    # asks for a passphrase
```

It writes an AES-256 encrypted disk image. Store it off this machine (a password-manager attachment, or a drive kept
elsewhere), and keep the passphrase in the password manager. Never commit it. Check it opens:
`hdiutil attach <file>.dmg`, then compare with the originals and `hdiutil detach`.

## Rebuild, in order

The launch agents name `/Users/labs/projects/the-factory`, so use the same user name and path, or edit the plists.

1. **Tools:** `brew install colima docker gh gitleaks cloudflared`, then uv with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
2. **GitHub:** `gh auth login`, then `git clone https://github.com/svensonlabs7/the-factory ~/projects/the-factory`.
3. **Secrets:** `hdiutil attach factory-secrets-<date>.dmg`. Then copy `env` to `~/projects/the-factory/.env` (`chmod 600`)
   and `cloudflared/*` to `~/.cloudflared/`.
4. **Docker VM:** `colima start --cpu 2 --memory 4`. The first build pulls the pinned agent-server image (about 9 GB).
5. **Services:** from the repo, `mkdir -p .factory-logs && infra/install.sh`. It installs the tunnel config and the
   tunnel, adapter and beacon launch agents, and starts them.
6. **Check:**
   - `infra/install.sh --check` lists every file as `ok`;
   - `curl -s 127.0.0.1:7654/health` returns `{"status":"ok"}`;
   - `factory/build/egress.sh` exits 0;
   - `gh variable get FACTORY_ALIVE_AT` is from the last 10 minutes;
   - `~/Library/Logs/com.cloudflare.cloudflared.err.log` shows four `Registered tunnel connection` lines.

## Drift

`infra/install.sh --check` compares the installed service files with the repo and exits 1 on any difference. Run it after
pulling a change to `config.yml` or a plist; `infra/install.sh` (no flag) then installs only what changed and reloads it.
Reloading the adapter ends a run in progress, so do it when `HEARTBEAT.md` shows `idle`.

## Drill

A plan that has never run has an unknown recovery time. Once a year, or after a large infra change, run the steps above
on a spare Mac or a new macOS user, time each one, and record the result in `knowledge/systems/083-disaster-recovery.md`.
