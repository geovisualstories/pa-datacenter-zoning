"""Interactive Leaflet map (folium) -> docs/index.html for GitHub Pages."""
import folium
from . import config

T = config.THEME


def make_web_map(state, counties, polys, points, out_path=None):
    s = state.to_crs(4326); c = counties.to_crs(4326)
    p = polys.to_crs(4326); pt = points.to_crs(4326)
    minx, miny, maxx, maxy = s.total_bounds

    m = folium.Map(tiles=None, control_scale=True, prefer_canvas=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, HERE, Garmin, &copy; OpenStreetMap contributors", name="Esri Dark Gray Canvas",
        max_zoom=16, control=False).add_to(m)
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    folium.GeoJson(s, name="Pennsylvania", style_function=lambda f: {
        "color": T["state_line"], "weight": 1.5, "fill": False}, control=False).add_to(m)

    cfields = ["NAME", "county_status", "action_date", "source"]
    c_ = c.copy()
    for f in cfields[1:]:
        c_[f] = c_[f].fillna("—") if f in c_ else "—"
    folium.GeoJson(
        c_[cfields + ["geometry"]], name="County boundaries / county-level ordinances",
        style_function=lambda f: {
            "color": "#ffffff" if f["properties"]["county_status"] != "—" else T["county_line"],
            "weight": 1.2 if f["properties"]["county_status"] != "—" else 0.6,
            "dashArray": "4 4" if f["properties"]["county_status"] != "—" else None,
            "fillColor": "#ffffff",
            "fillOpacity": 0.06 if f["properties"]["county_status"] != "—" else 0},
        tooltip=folium.GeoJsonTooltip(["NAME", "county_status"], aliases=["County", "County-level"]),
    ).add_to(m)

    fields = ["municipality", "county", "status", "status_raw", "action_date", "source"]
    aliases = ["Municipality", "County", "Category", "Status detail", "Action date", "Source"]
    for status in config.STATUS_ORDER:
        col = config.STATUS_COLORS[status]
        fg = folium.FeatureGroup(name=f"{status} ({(p['status'] == status).sum()})").add_to(m)
        folium.GeoJson(p[p["status"] == status][fields + ["geometry"]],
                       style_function=lambda f, col=col: {"color": col, "weight": 1,
                                                          "fillColor": col, "fillOpacity": 0.45},
                       popup=folium.GeoJsonPopup(fields, aliases=aliases)).add_to(fg)
        for _, r in pt[pt["status"] == status].iterrows():
            folium.CircleMarker([r.geometry.y, r.geometry.x], radius=5, color=T["background"],
                                weight=1, fill=True, fill_color=col, fill_opacity=1,
                                tooltip=f"{r['municipality']} ({r['county']} Co.) — {status}").add_to(fg)

    folium.LayerControl(collapsed=False).add_to(m)
    title = (f"<div style='position:fixed;top:12px;left:60px;z-index:9999;color:{T['text']};"
             "font-family:Helvetica,Arial,sans-serif;background:rgba(20,22,26,.85);padding:10px 14px;"
             "border-radius:6px'><b style='font-size:18px'>Zoning for the Cloud</b><br>"
             f"<span style='font-size:12px;color:{T['subtext']}'>Pennsylvania municipal data center "
             f"ordinances — {len(p)} municipalities</span></div>")
    m.get_root().html.add_child(folium.Element(title))

    out_path = out_path or (config.ROOT / "docs" / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(out_path)
    print(f"Saved {out_path.relative_to(config.ROOT)}")
