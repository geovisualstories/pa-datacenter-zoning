"""Existing data centers in PA from PNNL's IM3 Open Source Data Center Atlas (context layer).

The Atlas is OpenStreetMap-derived and licensed ODbL 1.0. Download it by hand (see
config.DATACENTER_ATLAS) into data/raw/pnnl_datacenter_atlas/; this module reads the
GeoPackage there, keeps Pennsylvania, and collapses its three layers into one point per
facility. The PA extract written to data/processed is a derived database, so it stays ODbL.
"""
import geopandas as gpd
import pandas as pd
from . import config

OUT = config.PROCESSED / "pa_existing_datacenters.gpkg"
FIELDS = ["id", "name", "operator", "sqft", "type"]


def _find_gpkg():
    hits = sorted(config.DATACENTER_DIR.rglob("*.gpkg"))
    return hits[0] if hits else None


def load(state: gpd.GeoDataFrame) -> gpd.GeoDataFrame | None:
    """-> one point per PA facility (config.CRS), or None if the Atlas isn't downloaded."""
    src = _find_gpkg()
    if src is None:
        print(f"Existing data centers: no Atlas GeoPackage in {config.DATACENTER_DIR.relative_to(config.ROOT)}"
              f" -> layer skipped. Download: {config.DATACENTER_ATLAS['url']}")
        return None
    layers = {}
    for name in ("campus", "building", "point"):
        gdf = gpd.read_file(src, layer=name)
        gdf = gdf[gdf["state_abb"] == "PA"].to_crs(config.CRS)
        # Facilities straddling a county line appear once per county: keep one row per id.
        layers[name] = gdf.drop_duplicates("id")

    # Campuses and their buildings overlap (both are kept in the Atlas). Count a building only
    # if it isn't inside a campus, and a point only if it isn't inside either polygon layer.
    campus = layers["campus"]
    building = layers["building"]
    if len(campus):
        building = building[~building.representative_point().within(campus.union_all())]
    polys = pd.concat([campus, building])
    point = layers["point"]
    if len(polys):
        point = point[~point.within(polys.union_all())]

    out = pd.concat([polys.assign(geometry=polys.representative_point()), point], ignore_index=True)
    for f in FIELDS:
        if f not in out:
            out[f] = None
    out = gpd.GeoDataFrame(out[FIELDS + ["geometry"]], geometry="geometry", crs=config.CRS)
    out = out[out.within(state.union_all().buffer(1000))]  # guard against mis-tagged state
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT, driver="GPKG")
    return out


def load_inventory_public() -> gpd.GeoDataFrame | None:
    """The data center inventory for map layers (config.CRS points). Reads only the public file:
    the draft holds PeeringDB rows, which may not be redistributed."""
    if not config.DC_INVENTORY_PUBLIC.exists():
        return None
    df = pd.read_csv(config.DC_INVENTORY_PUBLIC, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert not df.apply(lambda c: c.str.contains("peeringdb", case=False)).any().any(), \
        f"PeeringDB content in {config.DC_INVENTORY_PUBLIC.name}"
    df = df[(df["lat"] != "") & (df["lon"] != "")]
    pts = gpd.points_from_xy(df["lon"].astype(float), df["lat"].astype(float))
    return gpd.GeoDataFrame(df, geometry=pts, crs=4326).to_crs(config.CRS)


def assert_no_peeringdb(paths) -> None:
    """Fail the build if a published output mentions PeeringDB (the draft inventory leaking in)."""
    for p in paths:
        if p.exists() and b"peeringdb" in p.read_bytes().lower():
            raise RuntimeError(f"{p.relative_to(config.ROOT)} contains PeeringDB data; "
                               "map layers must read config.DC_INVENTORY_PUBLIC only")


def summary(dcs: gpd.GeoDataFrame, munis: gpd.GeoDataFrame, polys: gpd.GeoDataFrame) -> dict:
    """How mapped data centers line up with municipalities that have ordinances (console only;
    the Atlas is a partial inventory, so no share/percentage is derived from it)."""
    hit = gpd.sjoin(dcs, munis[["GEOID", "geometry"]], how="left", predicate="within")
    hit = hit[~hit.index.duplicated()]  # a point exactly on a shared boundary matches twice
    in_ord = hit["GEOID"].isin(polys["GEOID"])
    per_muni = hit[in_ord].groupby("GEOID").size()
    return {
        "total": len(dcs),
        "inside_ordinance_munis": int(in_ord.sum()),
        "outside_ordinance_munis": int((~in_ord).sum()),
        "ordinance_munis": len(polys),
        "ordinance_munis_with_dc": int(len(per_muni)),
    }


def print_summary(s: dict) -> None:
    print(f"Data centers mapped in PNNL IM3 Atlas, PA: {s['total']}\n"
          f"  inside municipalities with ordinances:  {s['inside_ordinance_munis']}\n"
          f"  outside them:                           {s['outside_ordinance_munis']}\n"
          f"  ordinance municipalities with >=1 existing data center: "
          f"{s['ordinance_munis_with_dc']} of {s['ordinance_munis']}  (partial inventory: not for publication)")
