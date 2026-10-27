"""Draft list of operating Pennsylvania data centers, compiled from two open sources.

- PeeringDB API: interconnection / colocation facilities with state = PA.
- OpenStreetMap via Overpass: features in PA tagged telecom=data_center or building=data_center
  (© OpenStreetMap contributors, ODbL 1.0; the public CSV is a derived database, so it is ODbL too).

Two modes:

    python -m src.build_dc_inventory            # offline: draft -> public CSV, no network calls
    python -m src.build_dc_inventory --fetch    # download both sources, merge new facilities into the draft

--fetch caches the raw responses in RAW_DIR, backs up the draft, then only appends facilities that
aren't in it yet (matched on source_1) and notes existing ones that dropped out of their source.
Existing rows are never rewritten, so hand edits (status, source_2, published_ok, capacity, notes...)
are safe. New rows start as status "Needs check", published_ok False. Rows from the two sources
that look like the same facility (same name or operator within DUP_RADIUS_M) are flagged in
`notes`, so a person decides which to merge. No commercial directories are used.

Two files:
- DRAFT (gitignored): every row, for checking by hand. PeeringDB's Acceptable Use Policy restricts
  redistributing its data, so PeeringDB is used for discovery only and this file is never published.
- PUBLIC (committed): only rows with published_ok = True, with PeeringDB links and notes removed.
  A row may be published_ok only if it comes from OpenStreetMap, or if a primary source (operator
  website, PA DEP permit, news article) has been recorded in source_2. PeeringDB alone never
  qualifies. Any map layer built from this inventory reads the PUBLIC file only
  (datacenters.load_inventory_public).
"""
import argparse
import datetime as dt
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd
from . import boundaries, config

DRAFT = config.DC_INVENTORY_DRAFT
PUBLIC = config.DC_INVENTORY_PUBLIC
RAW_DIR = config.RAW / "dc_inventory"   # gitignored: raw responses + draft backups (hold PeeringDB data)
BACKUP_DIR = RAW_DIR / "draft_backups"
COLUMNS = ["name", "operator", "address", "municipality", "county", "lat", "lon", "type", "status",
           "capacity_mw", "mw_measure", "source_1", "source_2", "date_checked", "published_ok", "notes"]
DUP_RADIUS_M = 500
USER_AGENT = "pa-datacenter-zoning/1.0 (research map; github.com/geovisualstories/pa-datacenter-zoning)"

PEERINGDB_URL = "https://www.peeringdb.com/api/fac?country=US&state=PA"
# Main public Overpass instance first, then alternates (tried in order if the main one keeps failing).
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_WAITS = [15, 30, 60, 120]  # seconds between attempts on one endpoint (exponential, ~2 min cap)
OVERPASS_QUERY = """
[out:json][timeout:120];
area["ISO3166-2"="US-PA"][admin_level=4]->.pa;
(
  nwr["telecom"="data_center"](area.pa);
  nwr["building"="data_center"](area.pa);
);
out center tags;
"""
RETRY_CODES = (429, 500, 502, 503, 504)


# --- fetching ---------------------------------------------------------------------------------

def _get_json(url, data=None, waits=(10, 30)):
    """GET/POST -> parsed JSON, retrying busy-server errors after each wait in `waits`."""
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    for wait in [*waits, None]:
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            busy = not isinstance(e, urllib.error.HTTPError) or e.code in RETRY_CODES
            if not busy or wait is None:
                raise
            print(f"  {urllib.parse.urlsplit(url).netloc}: {e}; retrying in {wait} s")
            time.sleep(wait)


def _cache(name: str, payload) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}_{dt.date.today():%Y%m%d}.json").write_text(json.dumps(payload), encoding="utf-8")


def fetch_peeringdb() -> dict:
    payload = _get_json(PEERINGDB_URL)
    _cache("peeringdb_fac_PA", payload)
    return payload


def fetch_overpass() -> dict:
    """Try each endpoint with exponential backoff. If all fail, fall back to the newest cached
    response (with a warning) rather than losing the run."""
    data = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode()
    for url in OVERPASS_URLS:
        try:
            payload = _get_json(url, data, waits=OVERPASS_WAITS)
            _cache("overpass_datacenters_PA", payload)
            return payload
        except Exception as e:  # noqa: BLE001 - any failure moves on to the next endpoint
            print(f"  Overpass endpoint failed: {url} ({e})")
    cached = sorted(RAW_DIR.glob("overpass_datacenters_PA_*.json"))
    if not cached:
        raise RuntimeError("All Overpass endpoints failed and there is no cached response")
    print(f"  WARNING: all Overpass endpoints failed; using cached {cached[-1].name}")
    return json.loads(cached[-1].read_text(encoding="utf-8"))


# --- parsing ----------------------------------------------------------------------------------

def parse_peeringdb(payload: dict) -> pd.DataFrame:
    rows = []
    for f in payload["data"]:
        if (f.get("state") or "").strip().upper() not in ("PA", "PENNSYLVANIA"):
            continue
        address = ", ".join(p for p in (f.get("address1"), f.get("address2"), f.get("city"),
                                        f"{f.get('state', '')} {f.get('zipcode', '')}".strip()) if p)
        # PeeringDB's website field is a lead, not a verification: it goes in notes, not source_2.
        notes = [f"PeeringDB lists website {f['website']}"] if f.get("website") else []
        if not f.get("latitude"):
            notes.append("PeeringDB has no coordinates")
        if not re.fullmatch(r"1[5-9]\d{3}(-\d{4})?", (f.get("zipcode") or "").strip()):
            notes.append(f"ZIP code {f.get('zipcode')!r} is not a Pennsylvania ZIP; check the address")
        rows.append({
            "name": f.get("name"), "operator": f.get("org_name"), "address": address,
            "lat": f.get("latitude"), "lon": f.get("longitude"),
            "type": "Interconnection / colocation facility (PeeringDB)",
            "source_1": f"https://www.peeringdb.com/fac/{f['id']}",
            "source_2": "",  # a primary source, recorded by hand once the row is verified
            "notes": "; ".join(notes),
        })
    return pd.DataFrame(rows)


def parse_overpass(payload: dict) -> pd.DataFrame:
    rows = []
    for e in payload["elements"]:
        t = e.get("tags", {})
        c = e if e["type"] == "node" else e.get("center", {})
        tag = "telecom=data_center" if t.get("telecom") == "data_center" else "building=data_center"
        address = " ".join(p for p in (t.get("addr:housenumber"), t.get("addr:street")) if p)
        address = ", ".join(p for p in (address, t.get("addr:city"),
                                        f"PA {t.get('addr:postcode', '')}".strip() if address else "") if p)
        rows.append({
            "name": t.get("name") or "", "operator": t.get("operator") or "", "address": address,
            "lat": c.get("lat"), "lon": c.get("lon"),
            "type": f"OSM {e['type']} ({tag})",
            "source_1": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
            "source_2": t.get("website") or t.get("contact:website") or "",
            "notes": "",
        })
    return pd.DataFrame(rows)


# --- flags ------------------------------------------------------------------------------------

def _norm(s) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())
    s = re.sub(r"\b(inc|llc|corp|corporation|co|the|data ?cent(er|re)s?|dc)\b", " ", s)
    return " ".join(s.split())


def _add_note(gdf, i, note):
    gdf.at[i, "notes"] = "; ".join(n for n in (gdf.at[i, "notes"], note) if n)


def flag_duplicates(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Note pairs within DUP_RADIUS_M sharing a (normalized) name or operator. Rows are not dropped.
    The note names the other row by its source_1 link, which stays valid however the sheet is sorted."""
    keys = [{k for k in (_norm(n), _norm(o)) if k} for n, o in zip(gdf["name"], gdf["operator"])]
    located = gdf.loc[gdf["lat"].notna(), ["geometry"]]
    near = gpd.sjoin(located, located, predicate="dwithin", distance=DUP_RADIUS_M)
    near = near[near.index < near["index_right"]]
    for i, j in zip(near.index, near["index_right"]):
        a, b = keys[i], keys[j]
        if a & b or any(x in y or y in x for x in a for y in b if min(len(x), len(y)) >= 4):
            _add_note(gdf, i, f"Possible duplicate of {gdf.at[j, 'source_1']}")
            _add_note(gdf, j, f"Possible duplicate of {gdf.at[i, 'source_1']}")
    return gdf


def flag_unnamed_clusters(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """OSM often tags each building of one site separately and without a name. Note how many
    unnamed features sit within DUP_RADIUS_M of each other, so they can be merged into one site."""
    unnamed = gdf[(gdf["name"] == "") & gdf["lat"].notna()]
    if unnamed.empty:
        return gdf
    blobs = gpd.GeoSeries([unnamed.buffer(DUP_RADIUS_M / 2).union_all()], crs=gdf.crs).explode(index_parts=False)
    for blob in blobs:
        members = unnamed[unnamed.within(blob)]
        if len(members) > 1:
            for i in members.index:
                _add_note(gdf, i, f"One of {len(members)} unnamed OSM features within {DUP_RADIUS_M} m: likely one site")
    return gdf


def candidates(pdb: dict, osm: dict) -> pd.DataFrame:
    """Raw source payloads -> rows in COLUMNS order, joined to municipality/county and flagged."""
    counties = boundaries.load_counties()
    munis = boundaries.load_municipalities(counties)
    state = boundaries.load_state()

    df = pd.concat([parse_peeringdb(pdb), parse_overpass(osm)], ignore_index=True)
    df[["lat", "lon"]] = df[["lat", "lon"]].apply(pd.to_numeric, errors="coerce")
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326).to_crs(config.CRS)

    hit = gpd.sjoin(pts, munis[["NAMELSAD", "county_key", "geometry"]], how="left", predicate="within")
    hit = hit[~hit.index.duplicated()]
    pts["municipality"] = hit["NAMELSAD"]
    pts["county"] = hit["county_key"].str.title()
    for i in pts.index[pts["lat"].notna() & ~pts.within(state.union_all())]:
        _add_note(pts, i, "Point falls outside PA boundary")

    pts = flag_unnamed_clusters(flag_duplicates(pts.reset_index(drop=True)))
    pts["status"] = "Needs check"
    pts["capacity_mw"] = ""
    pts["mw_measure"] = ""
    pts["date_checked"] = dt.date.today().isoformat()
    pts["published_ok"] = "False"
    pts[["lat", "lon"]] = pts[["lat", "lon"]].round(6)
    out = pd.DataFrame(pts)[COLUMNS].fillna("").astype(str)
    return out.sort_values(["county", "municipality", "name"], key=lambda s: s.str.lower()).reset_index(drop=True)


# --- draft and public files -------------------------------------------------------------------

def read_draft() -> pd.DataFrame:
    df = pd.read_csv(DRAFT, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for c in COLUMNS:  # tolerate a column deleted by hand
        if c not in df:
            df[c] = ""
    return df


def has_primary_source(row) -> bool:
    """source_2 holds evidence other than PeeringDB or OpenStreetMap (operator site, DEP permit, news)."""
    s = str(row["source_2"]).strip()
    return bool(s) and not is_peeringdb(s) and "openstreetmap.org" not in s


def merge(fresh: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Append facilities not yet in the draft; note draft rows that dropped out of their source.
    A newly dropped row with no primary source in source_2 goes back to status "Needs check",
    published_ok False. Existing rows are otherwise left exactly as they are.
    -> (draft, n_added, n_newly_removed)."""
    if not DRAFT.exists():
        return fresh, len(fresh), 0
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{DRAFT.stem}_{dt.datetime.now():%Y%m%d-%H%M%S}.csv"
    shutil.copy2(DRAFT, backup)
    print(f"Backed up draft -> {backup.relative_to(config.ROOT)}")

    old = read_draft()
    added = fresh[~fresh["source_1"].isin(old["source_1"])]
    # Only rows that came from a fetched source can drop out of it; rows added by hand never do.
    from_source = old["source_1"].str.contains("peeringdb.com|openstreetmap.org", regex=True)
    gone = from_source & ~old["source_1"].isin(fresh["source_1"]) & ~old["notes"].str.contains("Not in source as of")
    note = f"Not in source as of {dt.date.today().isoformat()}"
    old.loc[gone, "notes"] = [f"{n}; {note}" if n else note for n in old.loc[gone, "notes"]]
    # Only on the run that first notices the drop, so a row re-verified by hand later stays as set.
    unbacked = gone & ~old.apply(has_primary_source, axis=1)
    old.loc[unbacked, ["status", "published_ok"]] = ["Needs check", "False"]
    return pd.concat([old, added], ignore_index=True), len(added), int(gone.sum())


def print_dropped(draft: pd.DataFrame) -> None:
    """Every draft row noted as no longer in its source, and whether it can still be published."""
    dropped = draft[draft["notes"].str.contains("Not in source as of")]
    print(f"\nRows no longer in their source: {len(dropped)}")
    for _, r in dropped.iterrows():
        when = re.search(r"Not in source as of (\S+)", r["notes"]).group(1)
        state = ("kept published (primary source in source_2)" if has_primary_source(r) and _truthy(r["published_ok"])
                 else f"status {r['status']!r}, published_ok {r['published_ok']}")
        print(f"  {r['name'] or '(unnamed)'} | {r['source_1']} | dropped {when} | {state}")


def is_peeringdb(s) -> bool:
    return "peeringdb" in str(s).lower()


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "yes", "y", "1", "x")


def eligible(row) -> bool:
    """published_ok may be True only for OSM rows, or rows with a non-PeeringDB primary source in source_2."""
    if "openstreetmap.org" in str(row["source_1"]):
        return True
    return bool(str(row["source_2"]).strip()) and not is_peeringdb(row["source_2"])


def public(draft: pd.DataFrame) -> pd.DataFrame:
    """published_ok rows that pass the rule, with every PeeringDB link and reference removed.
    Rows marked published_ok that break the rule are left out (and reported); the draft is untouched."""
    ok = draft["published_ok"].map(_truthy)
    bad = ok & ~draft.apply(eligible, axis=1)
    for name in draft.loc[bad, "name"]:
        print(f"  Not published (PeeringDB only, no primary source in source_2): {name}")
    pub = draft[ok & ~bad].copy()
    for i in pub.index:
        srcs = [s for s in (pub.at[i, "source_1"], pub.at[i, "source_2"]) if s and not is_peeringdb(s)]
        pub.at[i, "source_1"], pub.at[i, "source_2"] = (srcs + ["", ""])[:2]
        pub.at[i, "notes"] = "; ".join(n for n in str(pub.at[i, "notes"]).split("; ")
                                       if n and not is_peeringdb(n) and "duplicate of" not in n)
    pub["type"] = pub["type"].str.replace(" (PeeringDB)", "", regex=False)
    pub = pub[[c for c in COLUMNS if c != "published_ok"]]
    assert not pub.map(is_peeringdb).any().any(), "PeeringDB content in the public inventory"
    return pub


def fetch() -> None:
    print("Fetching PeeringDB ...")
    pdb = fetch_peeringdb()
    print("Fetching OpenStreetMap (Overpass) ...")
    osm = fetch_overpass()
    draft, added, removed = merge(candidates(pdb, osm))
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    draft[COLUMNS].to_csv(DRAFT, index=False, encoding="utf-8-sig")
    print(f"Wrote {DRAFT.relative_to(config.ROOT)}: {len(draft)} rows "
          f"({added} new, {removed} newly noted as no longer in their source)")
    print_dropped(draft)


def write_public() -> None:
    if not DRAFT.exists():
        raise SystemExit(f"No draft at {DRAFT.relative_to(config.ROOT)}; run with --fetch first")
    pub = public(read_draft())
    pub.to_csv(PUBLIC, index=False, encoding="utf-8-sig")
    print(f"Wrote {PUBLIC.relative_to(config.ROOT)}: {len(pub)} rows (published_ok = True)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true",
                    help="download PeeringDB + OpenStreetMap and merge new facilities into the draft")
    if ap.parse_args().fetch:
        fetch()
    write_public()
