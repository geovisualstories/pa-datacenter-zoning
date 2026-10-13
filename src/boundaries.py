"""Download (once) and load Census cartographic boundary files for Pennsylvania."""
import urllib.request
from pathlib import Path
import geopandas as gpd
from . import config


def _cached(url: str) -> Path:
    config.RAW.mkdir(parents=True, exist_ok=True)
    dest = config.RAW / Path(url).name
    if not dest.exists():
        print(f"Downloading {dest.name} ...")
        urllib.request.urlretrieve(url, dest)
    return dest


def load_state() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(_cached(config.STATE_URL))
    return gdf[gdf["STATEFP"] == config.PA_FIPS].to_crs(config.CRS)


def load_counties() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(_cached(config.COUNTY_URL))
    gdf = gdf[gdf["STATEFP"] == config.PA_FIPS].copy()
    gdf["county_key"] = gdf["NAME"].str.lower()
    return gdf[["COUNTYFP", "NAME", "county_key", "geometry"]].to_crs(config.CRS)


def load_municipalities(counties: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """PA county subdivisions = municipalities. Adds county name for joining."""
    gdf = gpd.read_file(_cached(config.COUSUB_URL)).to_crs(config.CRS)
    gdf = gdf.merge(counties[["COUNTYFP", "county_key"]], on="COUNTYFP", how="left")
    return gdf[["GEOID", "NAME", "NAMELSAD", "COUNTYFP", "county_key", "geometry"]]
