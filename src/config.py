"""Project-wide settings: paths, data URLs, projection, and the map palette."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
OUTPUTS = ROOT / "outputs"

ORDINANCE_XLSX = DATA / "PA_MUN_DataCenterOrds.xlsx"
MUNI_SHEET = "Sheet1"      # municipality-level ordinances
COUNTY_SHEET = "Sheet2"    # county-level ordinances / guides

# US Census cartographic boundary files (generalized, good for statewide cartography).
# PA FIPS = 42. Census county subdivisions == PA's cities, boroughs, townships (+ Bloomsburg town).
CB_YEAR = 2024
COUSUB_URL = f"https://www2.census.gov/geo/tiger/GENZ{CB_YEAR}/shp/cb_{CB_YEAR}_42_cousub_500k.zip"
COUNTY_URL = f"https://www2.census.gov/geo/tiger/GENZ{CB_YEAR}/shp/cb_{CB_YEAR}_us_county_500k.zip"
STATE_URL = f"https://www2.census.gov/geo/tiger/GENZ{CB_YEAR}/shp/cb_{CB_YEAR}_us_state_500k.zip"
PA_FIPS = "42"

# Existing data centers (context layer). Downloaded by hand: MSD-LIVE serves files through its
# record page / msdlive CLI, not a plain URL. Put the GeoPackage anywhere under DATACENTER_DIR.
DATACENTER_ATLAS = {
    "name": "IM3 Open Source Data Center Atlas",
    "publisher": "Pacific Northwest National Laboratory (PNNL)",
    "version": "v2026.02.09",
    "doi": "10.57931/3017294",
    "url": "https://data.msdlive.org/records/p147s-4h760",
    "license": "Open Database License (ODbL) 1.0",
}
DATACENTER_DIR = RAW / "pnnl_datacenter_atlas"
DATACENTER_LEGEND = ("Data centers mapped in PNNL IM3 Atlas (partial inventory)",
                     "built from OpenStreetMap, so incomplete")
# Context layer only on the interactive map (off by default) for now; True adds it to the static maps.
STATIC_DATACENTERS = False

# Draft inventory of operating data centers (src/build_dc_inventory.py). The draft includes
# PeeringDB discovery rows and is gitignored; maps may read only the public file.
DC_INVENTORY_DRAFT = PROCESSED / "pa_dc_inventory_draft.csv"
DC_INVENTORY_PUBLIC = PROCESSED / "pa_dc_inventory_public.csv"

# NAD83 / Pennsylvania North (meters) - conformal, keeps PA "upright"
CRS = "EPSG:32128"

# Status categories, in legend order. Dark-canvas palette.
STATUS_ORDER = ["Adopted", "Moratorium", "Proposed / Under Review"]
STATUS_COLORS = {
    "Adopted": "#f2b134",                  # amber
    "Moratorium": "#e8505b",               # coral red
    "Proposed / Under Review": "#4fc3d9",  # cyan
}

# Plain-language legend text for each status: (label, description).
STATUS_LEGEND = {
    "Adopted": ("Rules adopted", "data center zoning is now law"),
    "Moratorium": ("Temporary pause", "moratorium while rules are written or challenged"),
    "Proposed / Under Review": ("Rules proposed", "draft, hearing, or under review"),
}

# County-level actions (Sheet2), drawn as outlines + a wash in the theme's county_ord_fill.
# Dash patterns are in points (matplotlib) / pixels (Leaflet dashArray); "" = solid.
# "fill" is the wash opacity (0 = none). Legend labels/notes live here too, so the
# legend swatches and the map are drawn from the same style.
COUNTY_STATUS_ORDER = ["Adopted", "Proposed", "Guide Published"]
COUNTY_STATUS_STYLES = {
    "Adopted":         {"dash": "",    "opacity": 0.9,  "width": 1.3, "fill": 0.10,
                        "label": "County rules adopted", "note": ""},
    "Proposed":        {"dash": "4 3", "opacity": 0.75, "width": 1.1, "fill": 0.05,
                        "label": "County rules proposed", "note": ""},
    "Guide Published": {"dash": "1 3", "opacity": 0.6,  "width": 1.0, "fill": 0,
                        "label": "County guidance only", "note": "model ordinance, not binding"},
}

# Neighboring states (STATEFP -> label), drawn as faint context outside PA.
NEIGHBOR_STATES = {"36": "NEW YORK", "34": "NEW JERSEY", "10": "DELAWARE",
                   "24": "MARYLAND", "54": "WEST VIRGINIA", "39": "OHIO"}

# Off while the insets (below) cover these same regions; the callouts would collide with the
# inset rectangles on the statewide map.
SHOW_REGION_CALLOUTS = False
# Static-map callouts: counties that make up each region (counts come from the data),
# and where the label sits relative to the region's municipalities, in km (dx, dy).
REGION_CALLOUTS = {
    "Cumberland Valley": {"counties": ["Cumberland", "Franklin"], "offset": (-45, -32)},
    "Lehigh Valley":     {"counties": ["Lehigh", "Northampton"], "offset": (-35, -30)},
    "Poconos":           {"counties": ["Monroe", "Pike", "Carbon", "Wayne"], "offset": (42, 38)},
    "Butler County":     {"counties": ["Butler"], "offset": (45, 30)},
}

# Static-map insets (and web zoom buttons) for the most crowded clusters of ordinance
# municipalities. "extent" = (minx, miny, maxx, maxy) in CRS meters; edit by hand. Suggested
# values come from `python -m src.insets`: municipalities within INSET_LINK_KM of each other form
# a cluster, the INSET_COUNT largest are kept, and each box is the cluster's polygons padded by
# INSET_PAD, held to INSET_MIN_SIZE_KM wide and widened to INSET_ASPECT (w/h). Ordered west to east.
INSET_ASPECT = 1.1
INSET_LINK_KM = 25
INSET_COUNT = 4
INSET_PAD = 0.10
INSET_MIN_SIZE_KM = 30
INSETS = {
    # 8 municipalities: Allegheny, Butler, Westmoreland
    "A": {"title": "Pittsburgh & Butler", "extent": (385400, 34400, 452200, 95200)},
    # 18: Cumberland, Dauphin, Lancaster, York
    "B": {"title": "South-central PA", "extent": (606200, -59100, 724800, 48700)},
    # 9: Columbia, Luzerne, Northumberland, Schuylkill
    "C": {"title": "Coal Region", "extent": (688600, 60300, 767700, 132300)},
    # 11: Carbon, Lehigh, Monroe, Northampton, Pike
    "D": {"title": "Lehigh Valley & Poconos", "extent": (755000, 37600, 853500, 127200)},
}

# Point outlines use each theme's background color, so they read as a halo.
DARK_THEME = {
    "background": "#14161a",
    "land": "#22252b",
    "muni_line": "#2c3037",
    "county_line": "#5a606b",
    "state_line": "#9aa0a8",
    "text": "#e6e6e6",
    "subtext": "#9aa0a8",
    "county_ord_fill": "#ffffff",  # wash + outline for county-level ordinances
    "panel": "rgba(20,22,26,.85)",  # web title/legend boxes
    "neighbor_line": "#3a3f47",
    "hillshade": 0.35,  # relief strength (0 = off)
    "datacenter": "#ffffff",  # existing data centers: small diamonds, slightly transparent
    "status_colors": STATUS_COLORS,
}

LIGHT_THEME = {
    "background": "#f5f4f0",
    "land": "#e3e2de",
    "muni_line": "#d3d2ce",
    "county_line": "#9a9ea6",
    "state_line": "#3d4148",
    "text": "#1f2226",
    "subtext": "#5c616a",
    "county_ord_fill": "#3d4148",
    "panel": "rgba(245,244,240,.9)",
    "neighbor_line": "#c9c8c3",
    "hillshade": 0.3,
    "datacenter": "#2b2e33",
    # amber darkened slightly for contrast on the light ground
    "status_colors": {**STATUS_COLORS, "Adopted": "#d9960f"},
}

THEMES = {"dark": DARK_THEME, "light": LIGHT_THEME}
