# Fit Funnel

A lead-scoring tool for the Good-Fit Rubric (Segment alignment, Platform
compatibility, Revenue threshold, Compliance complexity fit, Use case
clarity) plus a channel/attribution dashboard, built to sit alongside
Pipedrive rather than inside it.

Lead data (organization, value, status, channel, pathway, etc.) syncs
automatically from Pipedrive on a schedule via GitHub Actions. Scoring —
the rubric, notes, and flags your team adds — stays local to each
person's browser and is never written back to Pipedrive. Use Export/Import
to share or combine scoring between teammates.

## How it's wired together

- `index.html` — the page itself. Renders instantly from whatever's in
  this browser's local storage, then fetches `data/leads.json` and merges
  in fresh Pipedrive fields without touching anyone's scoring.
- `data/leads.json` — the last 30 days of deals from Pipedrive, refreshed
  automatically. This file is *not* a secret; only base deal data lives in
  it, and it's fine for it to be public on GitHub Pages.
- `scripts/sync_pipedrive.py` — pulls deals from the Pipedrive API and
  writes `data/leads.json`. Runs only inside GitHub Actions, where your
  API token is available as a secret — never in the browser.
- `.github/workflows/sync-pipedrive.yml` — runs the sync script daily
  (13:00 UTC) and commits the updated `data/leads.json`. Can also be run
  manually any time from the Actions tab.

Your Pipedrive API token never appears in the page, in this repository's
code, or in `data/leads.json` — it lives only as a GitHub Actions secret.

## One-time setup

1. **Create a GitHub repository** and push this folder's contents to it
   (keep the folder structure, including the hidden `.github/` directory).

2. **Add your Pipedrive API token as a secret.**
   In the repo: Settings → Secrets and variables → Actions → New repository
   secret.
   - Name: `PIPEDRIVE_API_TOKEN`
   - Value: your token from Pipedrive (Settings → Personal preferences →
     API). Use the token for whichever Pipedrive login you want the sync
     to run as.

3. **(Optional) Set your Pipedrive subdomain**, if it isn't
   `tokenoftrust` — check the URL when Pipedrive is open in your browser,
   it'll look like `https://<subdomain>.pipedrive.com/...`.
   In the repo: Settings → Secrets and variables → Actions → Variables tab
   → New repository variable.
   - Name: `PIPEDRIVE_DOMAIN`
   - Value: your subdomain (just the part before `.pipedrive.com`)

4. **Enable GitHub Pages.**
   Settings → Pages → Source: "Deploy from a branch" → pick your default
   branch and the root folder. GitHub will give you a URL like
   `https://<your-username>.github.io/<repo-name>/`.

5. **Run the sync once manually** so `data/leads.json` reflects a real,
   current pull before anyone starts scoring: go to the Actions tab →
   "Sync Pipedrive data" → "Run workflow". It should finish in well under
   a minute and commit an updated `data/leads.json`.

6. Open the Pages URL — you should see the current leads, refreshed daily
   from Pipedrive from then on.

## Adjusting the sync

- **Change the schedule**: edit the `cron` line in
  `.github/workflows/sync-pipedrive.yml` (cron is always in UTC).
- **Change the lookback window** (default 30 days, matching the manual
  process this replaces): add a `PIPEDRIVE_LOOKBACK_DAYS` repository
  variable, or edit the workflow's `env` block.
- **Run it on demand**: Actions tab → "Sync Pipedrive data" → "Run workflow"
  — useful right after a big batch of new leads comes in.

## Notes on the data model

Nothing here writes to Pipedrive — no new custom fields, no updates to
existing deals. All rubric scores, tiers, notes, and flags live only in
each browser's local storage (and in JSON exports people choose to share),
kept intentionally separate from your shared, org-wide Pipedrive account.

"Clear all scoring" resets rubric scores/notes/flags in the current
browser back to blank — it does not touch the synced lead data, which
keeps refreshing from Pipedrive regardless.
