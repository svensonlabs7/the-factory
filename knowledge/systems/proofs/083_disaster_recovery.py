"""Disaster recovery: restoring service after the whole environment is lost (dead disk, lost host, destroyed
region). It is defined by two targets -- RPO (how much data loss is tolerable) and RTO (how long recovery may
take) -- and AWS's four strategies trade cost for those: backup & restore (hours), pilot light, warm standby,
multi-site active/active (near-zero, most expensive). The rule the factory needs: an untested DR plan has an
UNKNOWN RTO, because a step whose input is neither backed up nor in a runbook must be improvised during the
outage (reissue each secret at its provider, recreate the tunnel), and you only discover how long that takes
when it happens.

Model the factory's rebuild as an ordered runbook. Each step has a time estimate; a step whose required input
is not backed up is IMPROVISED -- recoverable but unestimated and not runbooked, so total RTO is unknown.
Compute RTO today vs after the Backups fix (the .env secrets + tunnel credentials copied off-machine)."""

# (step, minutes, requires an input that must be recoverable)
steps = [
    ("install deps (brew, uv, colima, cloudflared, gh)", 20, None),
    ("git clone the repo from GitHub",                    2, "github"),      # backed up off-machine
    ("colima start + docker pull agent-server (by digest)", 10, "github"),
    ("restore .env secrets (OAuth, HMAC, CF Access)",      5, "env_secrets"),
    ("restore / recreate tunnel credentials",              5, "tunnel_creds"),
    ("cp config.yml + plists into place, launchctl load",  5, "github"),
    ("gh auth login",                                      3, "operator"),    # interactive, always available
]

BACKED_UP_TODAY = {"github", "operator"}                 # only GitHub + the human are guaranteed recoverable
BACKED_UP_FIXED = BACKED_UP_TODAY | {"env_secrets", "tunnel_creds"}  # after the Backups-gap fix


def rto(available):
    runbooked, improvised = 0, []
    for name, minutes, needs in steps:
        if needs and needs not in available:
            improvised.append(name)
        else:
            runbooked += minutes
    return runbooked, improvised


for label, avail in (("today (secrets/creds NOT backed up)", BACKED_UP_TODAY),
                     ("after Backups fix (off-machine copy)", BACKED_UP_FIXED)):
    runbooked, improvised = rto(avail)
    if improvised:
        print(f"{label:38s}: RTO = {runbooked} min runbooked + UNKNOWN (improvised: {improvised})")
    else:
        print(f"{label:38s}: RTO ~= {runbooked} min, every step runbooked")
