"""USGS 3DEP elevation for Pennsylvania (~90 m), cached to data/raw, plus a hillshade overlay.

Fetched straight from the 3DEP ImageServer (the service py3dep wraps) in the map CRS,
so no rasterio/GDAL is needed: tiles are read with Pillow, stitched, and saved as a
plain float TIFF whose extent (the bbox we asked for) is stored in a .json beside it.
"""
import io
import json
import time
import urllib.parse
import urllib.request
import numpy as np
from PIL import Image
from matplotlib.colors import LightSource
from . import config

DEM_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
RES = 90  # meters
EPSG = int(config.CRS.split(":")[1])
TILE = 1200  # px per request; one big request times out at the gateway


def _fetch(minx, miny, maxx, maxy, w, h, tries=4):
    q = {"bbox": f"{minx},{miny},{maxx},{maxy}", "bboxSR": EPSG, "imageSR": EPSG,
         "size": f"{w},{h}", "format": "tiff", "pixelType": "F32", "noData": -9999,
         "interpolation": "RSP_BilinearInterpolation", "f": "image"}
    url = f"{DEM_URL}?{urllib.parse.urlencode(q)}"
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                a = np.asarray(Image.open(io.BytesIO(r.read())), dtype="float32")
            if a.shape != (h, w):
                raise ValueError(f"got {a.shape}, wanted {(h, w)}")
            return a
        except Exception as e:  # noqa: BLE001 - transient gateway errors are common
            if i == tries - 1:
                raise
            print(f"  retry ({e})")
            time.sleep(5 * (i + 1))


def load_dem(state):
    """-> (elevation array [m], extent (minx, maxx, miny, maxy)) in config.CRS."""
    tif, meta = config.RAW / f"pa_dem_{RES}m.tif", config.RAW / f"pa_dem_{RES}m.json"
    if not (tif.exists() and meta.exists()):
        minx, miny, maxx, maxy = state.total_bounds
        pad = 2 * RES
        minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
        w, h = round((maxx - minx) / RES), round((maxy - miny) / RES)
        maxx, maxy = minx + w * RES, miny + h * RES
        print(f"Downloading 3DEP DEM ({w}x{h} @ {RES} m, in tiles) ...")
        dem = np.full((h, w), -9999, dtype="float32")
        for r0 in range(0, h, TILE):          # row 0 = north edge
            for c0 in range(0, w, TILE):
                tw, th = min(TILE, w - c0), min(TILE, h - r0)
                x0, y1 = minx + c0 * RES, maxy - r0 * RES
                dem[r0:r0 + th, c0:c0 + tw] = _fetch(x0, y1 - th * RES, x0 + tw * RES, y1, tw, th)
        config.RAW.mkdir(parents=True, exist_ok=True)
        Image.fromarray(dem, mode="F").save(tif)
        meta.write_text(json.dumps({"extent": [minx, maxx, miny, maxy], "crs": config.CRS}))
    dem = np.array(Image.open(tif), dtype="float32")
    dem[dem <= -9999] = np.nan
    return dem, tuple(json.loads(meta.read_text())["extent"])


def hillshade_rgba(dem, extent, strength, step=2, azdeg=315, altdeg=45, vert_exag=2.0):
    """Shadows -> black, highlights -> white, flat ground -> transparent, so the
    land color underneath is unchanged and only relief shows. Shaded at full
    resolution, then block-averaged by `step` (softer, and far smaller PNG/SVG).
    -> (rgba, extent)"""
    z = np.where(np.isnan(dem), np.nanmin(dem), dem)
    hs = LightSource(azdeg=azdeg, altdeg=altdeg).hillshade(z, vert_exag=vert_exag, dx=RES, dy=RES)
    h, w = (s // step * step for s in hs.shape)
    hs = hs[:h, :w].reshape(h // step, step, w // step, step).mean(axis=(1, 3))
    nodata = np.isnan(dem[:h, :w]).reshape(h // step, step, w // step, step).any(axis=(1, 3))
    d = hs - np.sin(np.radians(altdeg))  # 0 on flat ground
    rgba = np.zeros(hs.shape + (4,), dtype="float32")
    rgba[..., :3] = (d > 0)[..., None]
    rgba[..., 3] = np.clip(np.abs(d) * strength, 0, 1)
    rgba[nodata, 3] = 0
    minx, maxx, miny, maxy = extent  # crop happened at the right/bottom edges
    return rgba, (minx, minx + w * RES, maxy - h * RES, maxy)
