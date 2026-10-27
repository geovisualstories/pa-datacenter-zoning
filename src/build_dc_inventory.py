"""Draft list of operating Pennsylvania data centers, compiled from two open sources.

- PeeringDB API: interconnection / colocation facilities with state = PA.
- OpenStreetMap via Overpass: features in PA tagged telecom=data_center or building=data_center
  (© OpenStreetMap contributors, ODbL 1.0; the draft CSV is a derived database, so it is ODbL too).

Every row starts as status "Needs check": this is a research worksheet, not a finished inventory.
Rows from the two sources that look like the same facility (same name or operator within
DUP_RADIUS_M) are kept and flagged in `notes`, so a person decides which to merge. No commercial
directories are used.

Two files are written:
- DRAFT (gitignored): every row, for checking by hand. PeeringDB's Acceptable Use Policy restricts
  redistributing its data, so PeeringDB is used for discovery only and this file is never published.
  Hand edits to the HAND_COLUMNS are kept when the script is rerun (rows are matched on source_1).
- PUBLIC (committed): only rows with published_ok = True, with PeeringDB links and notes removed.
  A row may be published_ok only if it comes from OpenStreetMap, or if a primary source (operator
  website, PA DEP permit, news article) has been recorded in source_2. PeeringDB alone never
  qualifies. Any map layer built from this inventory reads the PUBLIC file only
  (datacenters.load_inventory_public).

    python -m src.build_dc_inventory
"""
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd
from . import boundaries, config

DRAFT = config.DC_INVENTORY_DRAFT
PUBLIC = config.DC_INVENTORY_PUBLIC
COLUMNS = ["name", "operator", "address", "municipality", "county", "lat", "lon", "type", "status",
           "capacity_mw", "mw_measure", "source_1", "source_2", "date_checked", "published_ok", "notes"]
# Filled in by hand in the draft; kept across reruns.
HAND_COLUMNS = ["status", "capacity_mw", "mw_measure", "source_2", "date_checked", "published_ok", "notes"]
DUP_RADIUS_M = 500
USER_AGENT = "pa-datacenter-zoning/1.0 (research map; github.com/geovisualstories/pa-datacenter-zoning)"

PEERINGDB_URL = "https://www.peeringdb.com/api/fac?country=US&state=PA"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:120];
area["ISO3166-2"="US-PA"][admin_level=4]->.pa;
(
  nwr["telecom"="data_center"](area.pa);
  nwr["building"="data_center"](area.pa);
);
out center tags;
"""


def _get_json(url, data=None, tries=3):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:  # Overpass answers 429/502/504 when busy
            if e.code not in (429, 502, 503, 504) or attempt == tries - 1:
                raise
            time.sleep(30 * (attempt + 1))


def peeringdb() -> pd.DataFrame:
    rows = []
    for f in _get_json(PEERINGDB_URL)["data"]:
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


def osm() -> pd.DataFrame:
    data = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode()
    rows = []
    for e in _get_json(OVERPASS_URL, data)["elements"]:
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


def _norm(s) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())
    s = re.sub(r"\b(inc|llc|corp|corporation|co|the|data ?cent(er|re)s?|dc)\b", " ", s)
    return " ".join(s.split())


def flag_duplicates(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Note pairs within DUP_RADIUS_M sharing a (normalized) name or operator. Rows are not dropped."""
    keys = [{k for k in (_norm(n), _norm(o)) if k} for n, o in zip(gdf["name"], gdf["operator"])]
    located = gdf.loc[gdf["lat"].notna(), ["geometry"]]
    near = gpd.sjoin(located, located, predicate="dwithin", distance=DUP_RADIUS_M)
    near = near[near.index < near["index_right"]]
    for i, j in zip(near.index, near["index_right"]):
        a, b = keys[i], keys[j]
        if a & b or any(x in y or y in x for x in a for y in b if min(len(x), len(y)) >= 4):
            for me, other in ((i, j), (j, i)):
                note = f"Possible duplicate of row {other + 2} ({gdf.at[other, 'source_1']})"
                gdf.at[me, "notes"] = "; ".join(n for n in (gdf.at[me, "notes"], note) if n)
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
            note = f"One of {len(members)} unnamed OSM features within {DUP_RADIUS_M} m: likely one site"
            for i in members.index:
                gdf.at[i, "notes"] = "; ".join(n for n in (gdf.at[i, "notes"], note) if n)
    return gdf


def is_peeringdb(s) -> bool:
    return "peeringdb" in str(s).lower()


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "yes", "y", "1", "x")


def eligible(row) -> bool:
    """published_ok may be True only for OSM rows, or rows with a non-PeeringDB primary source in source_2."""
    if "openstreetmap.org" in str(row["source_1"]):
        return True
    return bool(str(row["source_2"]).strip()) and not is_peeringdb(row["source_2"])


def carry_over(new: pd.DataFrame) -> pd.DataFrame:
    """Keep hand edits from the previous draft (matched on source_1). Rows that dropped out of
    the sources are kept, with a note, if someone already worked on them."""
    if not DRAFT.exists():
        return new
    old = pd.read_csv(DRAFT, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    old = old.drop_duplicates("source_1").set_index("source_1")
    for c in HAND_COLUMNS:
        if c not in old:
            old[c] = new[c].iloc[0] if c == "published_ok" and len(new) else ""
    new = new.set_index("source_1")
    both = new.index.intersection(old.index)
    new.loc[both, HAND_COLUMNS] = old.loc[both, HAND_COLUMNS].to_numpy()
    worked = old[(old["status"] != "Needs check") | old["published_ok"].map(_truthy) | (old["source_2"] != "")]
    gone = worked.loc[worked.index.difference(new.index)].copy()
    if len(gone):
        note = "No longer in source as of"
        gone["notes"] = [n if note in n else "; ".join(x for x in (n, f"{note} {dt.date.today()}") if x)
                         for n in gone["notes"]]
        new = pd.concat([new, gone[[c for c in new.columns if c in gone]]])
    return new.reset_index()


def enforce_published_ok(df: pd.DataFrame) -> pd.DataFrame:
    df["published_ok"] = df["published_ok"].map(_truthy)
    bad = df["published_ok"] & ~df.apply(eligible, axis=1)
    for i in df.index[bad]:
        print(f"  published_ok reset to False (PeeringDB only, no primary source in source_2): {df.at[i, 'name']}")
    df.loc[bad, "published_ok"] = False
    return df


def public(df: pd.DataFrame) -> pd.DataFrame:
    """published_ok rows with every PeeringDB link and reference removed."""
    pub = df[df["published_ok"]].copy()
    for i in pub.index:
        srcs = [s for s in (pub.at[i, "source_1"], pub.at[i, "source_2"]) if s and not is_peeringdb(s)]
        pub.at[i, "source_1"], pub.at[i, "source_2"] = (srcs + ["", ""])[:2]
        pub.at[i, "notes"] = "; ".join(n for n in str(pub.at[i, "notes"]).split("; ")
                                       if n and not is_peeringdb(n) and "duplicate of row" not in n)
    pub["type"] = pub["type"].str.replace(" (PeeringDB)", "", regex=False)
    pub = pub.drop(columns="published_ok")
    assert not pub.map(is_peeringdb).any().any(), "PeeringDB content in the public inventory"
    return pub


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    counties = boundaries.load_counties()
    munis = boundaries.load_municipalities(counties)
    state = boundaries.load_state()

    df = pd.concat([peeringdb(), osm()], ignore_index=True)
    df[["lat", "lon"]] = df[["lat", "lon"]].apply(pd.to_numeric, errors="coerce")
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326).to_crs(config.CRS)

    hit = gpd.sjoin(pts, munis[["NAMELSAD", "county_key", "geometry"]], how="left", predicate="within")
    hit = hit[~hit.index.duplicated()]
    pts["municipality"] = hit["NAMELSAD"]
    pts["county"] = hit["county_key"].str.title()
    outside = pts["lat"].notna() & ~pts.within(state.union_all())
    pts.loc[outside, "notes"] = pts.loc[outside, "notes"].str.cat(
        ["Point falls outside PA boundary"] * outside.sum(), sep="; ").str.strip("; ")

    pts = flag_unnamed_clusters(flag_duplicates(pts.reset_index(drop=True)))
    pts["status"] = "Needs check"
    pts["capacity_mw"] = ""
    pts["mw_measure"] = ""
    pts["date_checked"] = dt.date.today().isoformat()
    pts["published_ok"] = "False"
    pts[["lat", "lon"]] = pts[["lat", "lon"]].round(6)
    out = pd.DataFrame(pts)[COLUMNS].fillna("").astype(str)
    out = enforce_published_ok(carry_over(out)[COLUMNS])
    out = out.sort_values(["county", "municipality", "name"], key=lambda s: s.str.lower()).reset_index(drop=True)
    # Row references in notes point at the sheet order, so recompute them after sorting.
    out = _renumber_notes(out)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(DRAFT, index=False, encoding="utf-8-sig")
    pub = public(out)
    pub.to_csv(PUBLIC, index=False, encoding="utf-8-sig")
    return out, pub


def _renumber_notes(df: pd.DataFrame) -> pd.DataFrame:
    """Rewrite 'row N (source)' references to the sorted spreadsheet row (header = row 1)."""
    row_of = {s: i + 2 for i, s in enumerate(df["source_1"])}
    df["notes"] = df["notes"].str.replace(
        r"row \d+ \((\S+)\)", lambda m: f"row {row_of.get(m.group(1), '?')} ({m.group(1)})", regex=True)
    return df


if __name__ == "__main__":
    out, pub = build()
    print(f"Wrote {DRAFT.relative_to(config.ROOT)}: {len(out)} rows "
          f"({out['source_1'].str.contains('peeringdb').sum()} PeeringDB, "
          f"{out['source_1'].str.contains('openstreetmap').sum()} OSM; "
          f"{out['notes'].str.contains('duplicate').sum()} flagged as possible duplicates, "
          f"{out['notes'].str.contains('unnamed OSM').sum()} unnamed OSM features in multi-building sites)\n"
          f"Wrote {PUBLIC.relative_to(config.ROOT)}: {len(pub)} rows (published_ok = True)")
