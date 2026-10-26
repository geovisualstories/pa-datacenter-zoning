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

*Ordinance landscape changes weekly; this is a snapshot.*
