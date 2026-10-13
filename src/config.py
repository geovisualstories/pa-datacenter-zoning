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

# NAD83 / Pennsylvania North (meters) - conformal, keeps PA "upright"
CRS = "EPSG:32128"

# Status categories, in legend order. Dark-canvas palette.
STATUS_ORDER = ["Adopted", "Moratorium", "Proposed / Under Review"]
STATUS_COLORS = {
    "Adopted": "#f2b134",                  # amber
    "Moratorium": "#e8505b",               # coral red
    "Proposed / Under Review": "#4fc3d9",  # cyan
}

# County-level actions (Sheet2), drawn as white outlines. Dash patterns are in
# points (matplotlib) / pixels (Leaflet dashArray); "" = solid.
COUNTY_STATUS_ORDER = ["Adopted", "Proposed", "Guide Published"]
COUNTY_STATUS_STYLES = {
    "Adopted":         {"dash": "",    "opacity": 0.9,  "width": 1.3},
    "Proposed":        {"dash": "4 3", "opacity": 0.75, "width": 1.1},
    "Guide Published": {"dash": "1 3", "opacity": 0.45, "width": 1.0},
}

# Neighboring states (STATEFP -> label), drawn as faint context outside PA.
NEIGHBOR_STATES = {"36": "NEW YORK", "34": "NEW JERSEY", "10": "DELAWARE",
                   "24": "MARYLAND", "54": "WEST VIRGINIA", "39": "OHIO"}

# Static-map callouts: counties that make up each region (counts come from the data),
# and where the label sits relative to the region's municipalities, in km (dx, dy).
REGION_CALLOUTS = {
    "Cumberland Valley": {"counties": ["Cumberland", "Franklin"], "offset": (-45, -32)},
    "Lehigh Valley":     {"counties": ["Lehigh", "Northampton"], "offset": (-35, -30)},
    "Poconos":           {"counties": ["Monroe", "Pike", "Carbon", "Wayne"], "offset": (42, 38)},
    "Butler County":     {"counties": ["Butler"], "offset": (45, 30)},
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
    # amber darkened slightly for contrast on the light ground
    "status_colors": {**STATUS_COLORS, "Adopted": "#d9960f"},
}

THEMES = {"dark": DARK_THEME, "light": LIGHT_THEME}
