"""Match spreadsheet municipalities to Census polygons; write a GeoPackage.

Matching key = county + base name + municipal type (township/borough/city/town).
Type matters: e.g. Butler County has both Butler city AND Butler township.
If the spreadsheet omits the type (e.g. 'Allentown'), we accept a unique
base-name match within the county. Anything unresolved is written to
data/processed/unmatched.csv -> fix it in MANUAL_OVERRIDES below.
"""
import pandas as pd
import geopandas as gpd
from . import config, clean, boundaries

# (spreadsheet municipality, county) -> Census GEOID (10-digit). Fill as needed.
MANUAL_OVERRIDES: dict[tuple[str, str], str] = {
    # ("Some Township", "Somecounty"): "42xxxxxxxx",
}

GPKG = config.PROCESSED / "pa_datacenter_ordinances.gpkg"


def match(ords: pd.DataFrame, munis: gpd.GeoDataFrame) -> pd.DataFrame:
    parts = munis["NAMELSAD"].map(clean.split_name)
    m = munis.assign(base_name=parts.str[0], muni_type=parts.str[1])
    geoids, notes = [], []
    for _, r in ords.iterrows():
        key = (r["municipality"], r["county"])
        if key in MANUAL_OVERRIDES:
            geoids.append(MANUAL_OVERRIDES[key]); notes.append("manual"); continue
        cand = m[(m["county_key"] == r["county_key"]) & (m["base_name"] == r["base_name"])]
        has_type = pd.notna(r["muni_type"])
        exact = cand[cand["muni_type"] == r["muni_type"]] if has_type else cand
        if len(exact) == 1:
            geoids.append(exact.iloc[0]["GEOID"]); notes.append("exact" if has_type else "name-only")
        elif len(cand) == 1:  # type in sheet disagrees w/ Census (e.g. borough vs town)
            geoids.append(cand.iloc[0]["GEOID"]); notes.append(f"type-mismatch->{cand.iloc[0]['NAMELSAD']}")
        else:
            geoids.append(None); notes.append("UNMATCHED" if cand.empty else "AMBIGUOUS")
    return ords.assign(GEOID=geoids, match_note=notes)


def build():
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    state = boundaries.load_state()
    counties = boundaries.load_counties()
    munis = boundaries.load_municipalities(counties)

    ords = match(clean.load_municipal(), munis)
    bad = ords[ords["GEOID"].isna()]
    flagged = ords[ords["match_note"].str.startswith(("type-mismatch", "name-only"))]
    ords.to_csv(config.PROCESSED / "match_report.csv", index=False)
    bad.to_csv(config.PROCESSED / "unmatched.csv", index=False)
    print(f"Matched {ords['GEOID'].notna().sum()}/{len(ords)} municipalities")
    if len(flagged):
        print("Check these (matched, but loosely):\n",
              flagged[["municipality", "county", "match_note"]].to_string(index=False))
    if len(bad):
        print("UNMATCHED -> add to MANUAL_OVERRIDES:\n",
              bad[["municipality", "county", "match_note"]].to_string(index=False))

    keep = ["municipality", "county", "status", "status_raw", "action_date", "year", "source", "GEOID"]
    polys = munis[["GEOID", "NAMELSAD", "geometry"]].merge(
        ords.dropna(subset=["GEOID"])[keep], on="GEOID", how="inner")
    points = polys.copy()
    points["geometry"] = polys.geometry.representative_point()  # always inside the polygon

    county_ords = clean.load_county()
    counties = counties.merge(
        county_ords[["county_key", "county_status", "action_date", "source"]],
        on="county_key", how="left")
    counties["has_muni_activity"] = counties["county_key"].isin(ords["county_key"])
    missing = set(county_ords["county_key"]) - set(counties["county_key"])
    if missing:
        print("County-sheet names not found:", missing)

    for name, layer in [("state", state), ("counties", counties), ("all_municipalities", munis),
                        ("ordinance_polygons", polys), ("ordinance_points", points)]:
        layer.to_file(GPKG, layer=name, driver="GPKG")
    print(f"Wrote {GPKG.relative_to(config.ROOT)}  (open in ArcGIS Pro to style by hand, too)")
    return state, counties, munis, polys, points


def load():
    """Read layers back from the GeoPackage (run build() first)."""
    return tuple(gpd.read_file(GPKG, layer=l) for l in
                 ["state", "counties", "all_municipalities", "ordinance_polygons", "ordinance_points"])


if __name__ == "__main__":
    build()
