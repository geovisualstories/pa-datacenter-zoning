# Zoning for the Cloud: Pennsylvania's Data Center Ordinances

Principal Investigator: Valerie Holt, Teaching Associate Professor, Mechanical Engineering, P.C. Rossin College of Engineering and Applied Science, Lehigh University<br>
Data Collection: Anant Raj Verma, Data Science Graduate Student<br>
Cartography & analysis: Geovisual Stories

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="outputs/pa_datacenter_zoning_both_dark.png">
  <source media="(prefers-color-scheme: light)" srcset="outputs/pa_datacenter_zoning_both_light.png">
  <img alt="Map of Pennsylvania municipalities with data center zoning ordinances" src="outputs/pa_datacenter_zoning_both_dark.png">
</picture>

**WHO** — Local governments in Pennsylvania deciding where data centers can be built:<br>
66 towns and townships in 26 of the state's 67 counties, plus 14 county governments

**WHAT** — Local zoning response to data center development: adopted ordinances/overlays, moratoria, and proposed or draft amendments

**WHERE** — Statewide, municipal-scale; concentrations in the Harrisburg/Cumberland Valley, Lehigh Valley, Poconos, and Butler County

**WHEN** — Actions dated 2025–2026 (compiled October 2026)

**WHY** — Data center siting is being decided township by township. This map shows where local governments have moved first, and how unevenly.

🗺️ **[Explore the interactive map →](https://geovisualstories.github.io/pa-datacenter-zoning/)**

## Quick start
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python make_maps.py             # downloads Census boundaries on first run
```

### Options
| Flag | Effect |
|---|---|
| `--style polygons\|points\|both` | Fill municipal polygons, draw points, or both (default) |
| `--no-counties` | Hide county boundaries |
| `--no-county-ordinances` | Hide the dashed wash for county-level ordinances |
| `--label-counties` | Label counties with municipal activity |
| `--all-variants` | Export every style × county-boundary combination |
| `--no-datacenters` | Leave off the PNNL data center layer (interactive map) |

## Method
- **Status categories:** free-text status collapsed by precedence: *Adopted* > *Moratorium* > *Proposed / Under Review* (includes drafts, curative-amendment processes, county reviews).
- **Geometry:** U.S. Census cartographic boundary files (county subdivisions = PA municipalities), 2024.
- **Matching:** county + municipal name + type. Results in `data/processed/match_report.csv`.
- **Projection:** NAD83 / Pennsylvania North (EPSG:32128).
- **Insets:** four close-ups of the most crowded clusters of ordinance municipalities: A Pittsburgh & Butler, B South-central PA, C Coal Region, D Lehigh Valley & Poconos. Municipalities within 25 km of each other form a cluster, and the four largest get an inset. The extents are hand-editable in `src/config.py` (`INSETS`); `python -m src.insets` prints suggested extents computed from the data. The interactive map has one zoom button per inset.
- **GIS-ready output:** `data/processed/pa_datacenter_ordinances.gpkg` opens directly in ArcGIS Pro.

## Data sources
Ordinance research led by Valerie Holt (Principal Investigator, Lehigh University). Status compiled from municipal codes, public hearing notices, county planning reviews, Protect Our Poconos, Protect Cumberland County, and SAVRN. Boundaries: U.S. Census Bureau. Relief: USGS 3D Elevation Program (~90 m, fetched on first run). Typeface: Barlow Condensed (SIL Open Font License, `fonts/OFL.txt`).

**Data centers mapped in PNNL IM3 Atlas (partial inventory)**: a context layer on the interactive map only, off by default. It is built from OpenStreetMap and is incomplete: it lists 9 Pennsylvania facilities, far fewer than operate in the state, so it should not be read as a full inventory or used to compute shares.
- **Dataset:** IM3 Open Source Data Center Atlas, Pacific Northwest National Laboratory (PNNL)
- **Version:** v2026.02.09 (published 2026-02-09), DOI [10.57931/3017294](https://doi.org/10.57931/3017294)
- **URL:** <https://data.msdlive.org/records/p147s-4h760>
- **License:** [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Locations are derived from OpenStreetMap, © OpenStreetMap contributors. Redistribution is allowed with attribution; the PA extract in `data/processed/pa_existing_datacenters.gpkg` and the data center points embedded in `docs/index.html` are derived databases and are likewise available under the ODbL.
- **Setup:** MSD-LIVE serves the files from the record page (or its `msdlive` CLI), not a direct URL, so download the GeoPackage by hand into `data/raw/pnnl_datacenter_atlas/`. Without it the maps build without this layer.
- **Caveats:** crowd-sourced, so coverage may be incomplete. There is no capacity (MW) field, so symbols are not size-scaled. Overlapping campus, building and point records are collapsed to one point per facility.

**Inventory of operating data centers**: a research worksheet, not yet a map layer. **PeeringDB is used for discovery only. Published data comes from OpenStreetMap and primary sources.** No commercial directories are used.

```bash
python -m src.build_dc_inventory --fetch   # download PeeringDB + OpenStreetMap, add new facilities to the draft
python -m src.build_dc_inventory           # offline: rebuild the public CSV from the draft (no network calls)
```

- `--fetch` caches the raw responses in `data/raw/dc_inventory/` and backs up the draft to `data/raw/dc_inventory/draft_backups/` before merging. Both folders are gitignored.
- It **only appends** facilities not yet in the draft (matched on `source_1`). Existing rows are never rewritten. Rows you add by hand with another source are left alone. If a facility has dropped out of PeeringDB or OpenStreetMap, the merge adds "Not in source as of DATE" to its `notes`, and then:
  - If `source_2` holds a primary source (operator site, DEP permit, news), the row is unchanged and stays published.
  - Otherwise, when its only evidence besides PeeringDB is OpenStreetMap, it goes back to status "Needs check" with `published_ok` False. This happens only on the run that first notices the drop, so a row you re-verify later keeps your setting.
  - Every `--fetch` run ends with a list of all dropped rows and their current status.
- Overpass is often busy. The script retries with exponential backoff (15 s, 30 s, 60 s, 120 s), then tries alternate public Overpass servers. If they all fail, it uses the most recent cached response and prints a warning.
- After editing the draft (marking `published_ok`, recording sources), run the command without `--fetch` to update the public file.

The script works with two files:
- `data/processed/pa_dc_inventory_draft.csv` is the working draft. It is **gitignored and never published** because it contains PeeringDB records.
  - Every row starts as "Needs check" with `published_ok` = False.
  - Rows from the two sources that look like the same facility (same name or operator within 500 m) are flagged in `notes`, not merged. Unnamed OpenStreetMap buildings that belong to one site are flagged the same way.
  - Municipality and county come from the Census boundaries above.
  - Edits made by hand (`status`, `capacity_mw`, `mw_measure`, `source_2`, `date_checked`, `published_ok`, `notes`, or any other column) are never overwritten.
- `data/processed/pa_dc_inventory_public.csv` is the published file. It holds only rows with `published_ok` = True, with every PeeringDB link and note removed.
  - A row may be `published_ok` only if it comes from OpenStreetMap, or if it has been checked against a primary source recorded in `source_2` (operator website, PA DEP permit or news article).
  - A PeeringDB listing on its own never qualifies. A row marked True that breaks this rule is left out of the public file and named in the output. The draft itself is not changed.
  - Any map layer built from the inventory must read this file only (`datacenters.load_inventory_public()`). `make_maps.py` stops with an error if `docs/index.html`, the GeoPackages or the SVG maps contain PeeringDB content.

The two sources:
- **PeeringDB** ([API](https://www.peeringdb.com/apidocs/), facilities with state = PA) lists interconnection and colocation facilities as their operators report them. It misses enterprise and hyperscale sites that don't offer interconnection. Its [Acceptable Use Policy](https://www.peeringdb.com/aup) restricts redistributing the data without PeeringDB's permission, so PeeringDB is used only to find candidate facilities, and none of its records are published.
- **OpenStreetMap** (via the [Overpass API](https://overpass-api.de/), features tagged `telecom=data_center` or `building=data_center`) is © OpenStreetMap contributors, under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The public inventory is a derived database and is available under the ODbL.

*Ordinance landscape changes weekly; this is a snapshot.*
