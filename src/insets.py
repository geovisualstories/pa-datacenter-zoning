"""Inset extents around clusters of ordinance municipalities.

The extents used by the maps live in config.INSETS (edit them by hand there). This module
computes suggested values from the data; run it and paste the output into config.py:

    python -m src.insets
"""
import geopandas as gpd
from shapely.geometry import box
from . import config


def clusters(polys, points, link_km=None, count=None):
    """Group ordinance municipalities whose points are within link_km of each other (single
    linkage), keep the `count` largest groups. -> list of row subsets of polys, west to east."""
    link_km = config.INSET_LINK_KM if link_km is None else link_km
    count = config.INSET_COUNT if count is None else count
    blobs = gpd.GeoSeries([points.buffer(link_km * 500).union_all()],
                          crs=points.crs).explode(index_parts=False)
    groups = [polys[points.within(g).to_numpy()] for g in blobs]
    groups = sorted(groups, key=len, reverse=True)[:count]
    return sorted(groups, key=lambda g: g.total_bounds[0])


def extent(group, aspect=None, pad=None, min_size=None):
    """Bounding box of the group's polygons, padded, held to min_size wide, widened to the
    panel aspect (w/h). -> (minx, miny, maxx, maxy) in config.CRS, rounded to 100 m."""
    aspect = aspect or config.INSET_ASPECT
    pad = config.INSET_PAD if pad is None else pad
    min_size = (config.INSET_MIN_SIZE_KM if min_size is None else min_size) * 1000
    minx, miny, maxx, maxy = group.total_bounds
    w, h = maxx - minx, maxy - miny
    w, h = max(w * (1 + 2 * pad), min_size), max(h * (1 + 2 * pad), min_size / aspect)
    w, h = max(w, h * aspect), max(h, w / aspect)  # grow the short side to the panel shape
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    return tuple(int(round(v, -2)) for v in (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))


def bounds_4326(ext):
    """(minx, miny, maxx, maxy) in config.CRS -> [[south, west], [north, east]] for Leaflet."""
    g = gpd.GeoSeries([box(*ext)], crs=config.CRS).to_crs(4326)
    w, s, e, n = g.total_bounds
    return [[s, w], [n, e]]


if __name__ == "__main__":
    from . import join
    state, counties, munis, polys, points = join.load()
    for key, g in zip("ABCDEFGH", clusters(polys, points)):
        cty = ", ".join(sorted(g["county"].unique()))
        print(f'    "{key}": {{"title": "?", "extent": {extent(g)}}},  # {len(g)} munis: {cty}')
