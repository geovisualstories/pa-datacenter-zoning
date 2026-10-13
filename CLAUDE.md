# Context for Claude (VS Code / Claude Code)

Project: statewide map of Pennsylvania municipalities with data center zoning
ordinances (adopted, moratorium, or proposed). Python + geopandas; output is a
static portfolio map (PNG/SVG) and an interactive Leaflet map on GitHub Pages.

## Layout
- `data/PA_MUN_DataCenterOrds.xlsx` — source of truth. Sheet1 = municipalities, Sheet2 = counties.
- `src/config.py` — paths, Census URLs, CRS (EPSG:32128), palette, DARK_THEME / LIGHT_THEME.
- `src/clean.py` — loads sheet, collapses free-text status into 3 categories.
- `src/boundaries.py` — downloads/caches Census cartographic boundary files.
- `src/join.py` — matches municipalities on county + name + type; writes GeoPackage + match report.
- `src/map_static.py`, `src/map_web.py` — the two map outputs.
- `make_maps.py` — CLI entry point.

## Conventions
- Valerie Holt (Lehigh University) is the Principal Investigator and must be credited on all
  outputs (README, static map credits, web map title box). Cartography: Geovisual Stories.
- Never edit the xlsx programmatically; fix data issues by hand or via `MANUAL_OVERRIDES` in join.py.
- Dark canvas aesthetic; keep the 3 status colors consistent between static and web maps.
- Match on county + name + municipal type (Butler County has both Butler city and Butler township).
- After any change, run `python make_maps.py` and check `data/processed/match_report.csv`.
