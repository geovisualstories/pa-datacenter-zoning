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

THEME = {
    "background": "#14161a",
    "land": "#22252b",
    "muni_line": "#2c3037",
    "county_line": "#5a606b",
    "state_line": "#9aa0a8",
    "text": "#e6e6e6",
    "subtext": "#9aa0a8",
    "county_ord_fill": "#ffffff",  # low-alpha wash for county-level ordinances
}
