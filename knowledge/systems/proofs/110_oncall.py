"""On-call is sustainable only if pages are ACTIONABLE and INFREQUENT. Two numbers govern it:
  - precision = actionable pages / total pages. Low precision trains the responder to distrust the pager
    (the boy-who-cried-wolf effect), so a real page is answered slowly or missed.
  - page rate per shift. Google's SRE book caps on-call at ~2 incidents per shift so there is time to handle
    each properly; far above that is burnout and degraded response.

Model a week with the SAME real incidents under two alerting configs. Fatigue is modelled transparently: the
responder's acknowledgement delay for the real page grows with the number of false pages seen before it that
shift (each false alarm erodes trust). Deterministic; no randomness."""
SHIFTS_PER_WEEK = 7
BASE_ACK = 2          # minutes to ack a page when the pager is trusted
FATIGUE_PER_FALSE = 3  # minutes added to the real page's ack per preceding false page that shift


def week(total_pages, actionable):
    false_pages = total_pages - actionable
    precision = actionable / total_pages
    per_shift = total_pages / SHIFTS_PER_WEEK
    # The real page lands after this shift's share of false pages has already cried wolf.
    false_before_real = false_pages / SHIFTS_PER_WEEK
    ack_delay = BASE_ACK + FATIGUE_PER_FALSE * false_before_real
    sustainable = per_shift <= 2
    return precision, per_shift, ack_delay, sustainable


configs = {
    "noisy (alert on every blip)":    (63, 1),   # 63 pages/week, 1 actually actionable
    "tuned (symptom / SLO-burn only)": (3, 2),    # 3 pages/week, 2 actionable
}
for name, (total, actionable) in configs.items():
    precision, per_shift, ack, sustainable = week(total, actionable)
    print(f"{name:34s} precision {precision:4.0%}  {per_shift:4.1f} pages/shift  "
          f"real-page ack ~{ack:4.0f} min  {'sustainable' if sustainable else 'BURNOUT + cry-wolf'}")

print("\nSame real incidents both weeks; only the alerting rules differ. Noisy paging buries the real page under "
      "false ones (slow ack) and exceeds a sustainable shift load; tuned paging answers fast and stays sustainable.")
