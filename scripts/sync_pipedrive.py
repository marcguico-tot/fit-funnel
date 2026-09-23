#!/usr/bin/env python3
"""
Pull recent Pipedrive deals and write them to data/leads.json for the
Fit Funnel static page to fetch at runtime.

Run by .github/workflows/sync-pipedrive.yml on a schedule (and manually via
"Run workflow"). The Pipedrive API token is read from the environment only —
it is never hardcoded here and never written to the output file.

Required environment variables:
  PIPEDRIVE_API_TOKEN   Personal API token (Pipedrive: Settings > Personal
                         preferences > API). Must be set as a GitHub Actions
                         secret, never committed.

Optional environment variables:
  PIPEDRIVE_DOMAIN       Company subdomain, i.e. the part before
                          ".pipedrive.com" in your Pipedrive URL.
                          Defaults to "tokenoftrust".
  PIPEDRIVE_LOOKBACK_DAYS How many days of deals to pull, by creation date.
                          Defaults to 30 (matches the manual process this
                          tool replaces).
  OUTPUT_PATH             Where to write the JSON file. Defaults to
                          "data/leads.json".
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

PIPEDRIVE_DOMAIN = os.environ.get("PIPEDRIVE_DOMAIN", "tokenoftrust")
API_TOKEN = os.environ.get("PIPEDRIVE_API_TOKEN")
LOOKBACK_DAYS = int(os.environ.get("PIPEDRIVE_LOOKBACK_DAYS", "30"))
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "data/leads.json")

BASE_URL = "https://{}.pipedrive.com/api/v1".format(PIPEDRIVE_DOMAIN)


def api_get(path, params=None):
    params = dict(params or {})
    params["api_token"] = API_TOKEN
    resp = requests.get(BASE_URL + path, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success", False):
        raise RuntimeError("Pipedrive API error for {}: {}".format(path, payload))
    return payload


def build_field_map():
    """{field_key: {"name", "options": {option_id: label}}} for deal fields
    (built-in fields with an enum, like Channel, and every custom field)."""
    payload = api_get("/dealFields")
    field_map = {}
    for f in payload.get("data") or []:
        options = {}
        for opt in f.get("options") or []:
            options[opt.get("id")] = opt.get("label")
        field_map[f.get("key")] = {
            "name": f.get("name"),
            "options": options,
        }
    return field_map


def find_field_key_by_name(field_map, name):
    for key, meta in field_map.items():
        if meta.get("name") == name:
            return key
    return None


def resolve_value(field_map, key, raw_value):
    """Map an enum/set field's stored id(s) to its human-readable label(s).
    Falls back to the raw value untouched for plain text fields or unknown ids."""
    if raw_value is None or not key or key not in field_map:
        return raw_value
    options = field_map[key].get("options") or {}
    if not options:
        return raw_value
    if isinstance(raw_value, list):
        return ", ".join(str(options.get(v, v)) for v in raw_value)
    if raw_value in options:
        return options[raw_value]
    try:
        return options.get(int(raw_value), raw_value)
    except (TypeError, ValueError):
        return raw_value


def extract_name(field_value):
    """org_id / user_id / person_id come back as nested objects with a name."""
    if isinstance(field_value, dict):
        return field_value.get("name")
    return None


def fetch_recent_deals(cutoff_dt):
    deals = []
    start = 0
    page_size = 100
    while True:
        payload = api_get("/deals", {
            "start": start,
            "limit": page_size,
            "sort": "add_time DESC",
        })
        batch = payload.get("data") or []
        if not batch:
            break

        stop = False
        for d in batch:
            add_dt = parse_pd_time(d.get("add_time"))
            if add_dt is not None and add_dt < cutoff_dt:
                stop = True
                break
            deals.append(d)

        pagination = (payload.get("additional_data") or {}).get("pagination") or {}
        more = pagination.get("more_items_in_collection")
        if stop or not more:
            break
        start += page_size
        time.sleep(0.2)  # be polite to the API
    return deals


def parse_pd_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def build_lead_records(deals, field_map):
    pathway_key = find_field_key_by_name(field_map, "Pathway")
    source_env_key = find_field_key_by_name(field_map, "Source Environment Label")
    channel_key = "channel" if "channel" in field_map else find_field_key_by_name(field_map, "Channel")

    records = []
    for d in deals:
        records.append({
            "id": str(d.get("id")),
            "title": d.get("title"),
            "org": extract_name(d.get("org_id")),
            "owner": extract_name(d.get("user_id")),
            "status": d.get("status"),
            "value": d.get("value") or 0,
            "currency": d.get("currency"),
            "sourceChannel": resolve_value(field_map, channel_key, d.get("channel")),
            "sourceOrigin": d.get("origin"),
            "pathway": resolve_value(field_map, pathway_key, d.get(pathway_key)) if pathway_key else None,
            "sourceEnv": resolve_value(field_map, source_env_key, d.get(source_env_key)) if source_env_key else None,
            "createdAt": d.get("add_time"),
            "closedAt": d.get("close_time"),
        })
    return records


def main():
    if not API_TOKEN:
        print("ERROR: PIPEDRIVE_API_TOKEN is not set. Add it as a GitHub Actions secret.", file=sys.stderr)
        sys.exit(1)

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    field_map = build_field_map()
    deals = fetch_recent_deals(cutoff_dt)
    leads = build_lead_records(deals, field_map)

    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    payload = {
        "syncedAt": datetime.now(timezone.utc).isoformat(),
        "dealCount": len(leads),
        "lookbackDays": LOOKBACK_DAYS,
        "leads": leads,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    print("Wrote {} leads to {}".format(len(leads), OUTPUT_PATH))


if __name__ == "__main__":
    main()
