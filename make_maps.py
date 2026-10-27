"""One command to rebuild everything:  python make_maps.py"""
import argparse
from src import config, datacenters, join
from src.map_static import make_static_map
from src.map_web import make_web_map

ap = argparse.ArgumentParser()
ap.add_argument("--style", choices=["polygons", "points", "both"], default="both")
ap.add_argument("--no-counties", action="store_true", help="hide county boundaries")
ap.add_argument("--no-county-ordinances", action="store_true", help="hide county-level ordinance wash")
ap.add_argument("--label-counties", action="store_true", help="label counties with municipal activity")
ap.add_argument("--all-variants", action="store_true", help="export every style x county combo")
ap.add_argument("--skip-web", action="store_true")
ap.add_argument("--no-datacenters", action="store_true", help="leave off existing data centers")
a = ap.parse_args()

state, counties, munis, polys, points = join.build()
dcs = None if a.no_datacenters else datacenters.load(state)
static_dcs = dcs if config.STATIC_DATACENTERS else None  # web-only context layer for now
if dcs is not None:
    datacenters.print_summary(datacenters.summary(dcs, munis, polys))

for theme in ("dark", "light"):
    if a.all_variants:
        for style in ("polygons", "points", "both"):
            for show in (True, False):
                make_static_map(state, counties, munis, polys, points, style=style, show_counties=show,
                                county_ordinances=show and not a.no_county_ordinances,
                                label_counties=a.label_counties, theme=theme, datacenters=static_dcs)
    else:
        make_static_map(state, counties, munis, polys, points, style=a.style,
                        show_counties=not a.no_counties,
                        county_ordinances=not a.no_county_ordinances,
                        label_counties=a.label_counties, theme=theme, datacenters=static_dcs)

if not a.skip_web:
    make_web_map(state, counties, polys, points, datacenters=dcs)

# PeeringDB is discovery-only (its terms restrict redistribution): nothing published may contain it.
datacenters.assert_no_peeringdb([config.ROOT / "docs" / "index.html", config.DC_INVENTORY_PUBLIC,
                                 *config.PROCESSED.glob("*.gpkg"), *config.OUTPUTS.glob("*.svg")])
