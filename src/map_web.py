"""Interactive Leaflet map (folium) -> docs/index.html for GitHub Pages.

Rendered in the dark theme; a small script (THEME_JS) restyles the layers for
light mode, driven by a sun/moon toggle, prefers-color-scheme and localStorage.
"""
import json
import folium
from branca.element import MacroElement
from jinja2 import Template
from . import config, legend

D = config.DARK_THEME
TILES = {
    "dark": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    "light": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
}
TILE_ATTR = "Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
POLY_OPACITY, DOT_RADIUS = 0.45, 5  # shared by the map layers and the legend swatches


def make_web_map(state, counties, polys, points, out_path=None):
    s = state.to_crs(4326); c = counties.to_crs(4326)
    p = polys.to_crs(4326); pt = points.to_crs(4326)
    minx, miny, maxx, maxy = s.total_bounds

    m = folium.Map(tiles=None, control_scale=True, prefer_canvas=True)
    dark_tiles = folium.TileLayer(tiles=TILES["dark"], attr=TILE_ATTR, name="Esri Dark Gray Canvas",
                                  max_zoom=16, control=False).add_to(m)
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    state_layer = folium.GeoJson(s, name="Pennsylvania", style_function=lambda f: {
        "color": D["state_line"], "weight": 1.5, "fill": False}, control=False).add_to(m)

    cfields = ["NAME", "county_status", "action_date", "source"]
    c_ = c.copy()
    for f in cfields[1:]:
        c_[f] = c_[f].fillna("—") if f in c_ else "—"

    def county_style(f):
        st = config.COUNTY_STATUS_STYLES.get(f["properties"]["county_status"])
        if st is None:
            return {"color": D["county_line"], "weight": 0.6, "fillOpacity": 0}
        return {"color": D["county_ord_fill"], "weight": st["width"] * 1.2, "opacity": st["opacity"],
                "dashArray": st["dash"] or None, "fillColor": D["county_ord_fill"],
                "fillOpacity": st["fill"]}

    county_layer = folium.GeoJson(
        c_[cfields + ["geometry"]], name="County governments (gray shading)",
        style_function=county_style,
        tooltip=folium.GeoJsonTooltip(["NAME", "county_status"], aliases=["County", "County-level"]),
    ).add_to(m)

    fields = ["municipality", "county", "status", "status_raw", "action_date", "source"]
    aliases = ["Municipality", "County", "Category", "Status detail", "Action date", "Source"]
    # Legend counts are len() of the very rows drawn in each layer (see legend.py).
    muni_entries = legend.municipal_entries(p, pt)
    county_entries = legend.county_entries(c)
    status_layers = []
    for e in muni_entries:
        status, col = e["key"], D["status_colors"][e["key"]]
        fg = folium.FeatureGroup(name=f"{e['label']} ({e['count']})").add_to(m)
        poly = folium.GeoJson(e["polys"][fields + ["geometry"]],
                              style_function=lambda f, col=col: {"color": col, "weight": 1, "fillColor": col,
                                                                 "fillOpacity": POLY_OPACITY},
                              popup=folium.GeoJsonPopup(fields, aliases=aliases)).add_to(fg)
        for _, r in e["points"].iterrows():
            folium.CircleMarker([r.geometry.y, r.geometry.x], radius=DOT_RADIUS, color=D["background"],
                                weight=1, fill=True, fill_color=col, fill_opacity=1,
                                tooltip=f"{r['municipality']} ({r['county']} Co.) — {status}").add_to(fg)
        status_layers.append((status, poly, fg))

    folium.LayerControl(collapsed=False).add_to(m)
    title = (f"<div class='pa-panel' style='position:fixed;top:12px;left:60px;z-index:9999;color:{D['text']};"
             f"font-family:Helvetica,Arial,sans-serif;background:{D['panel']};padding:10px 14px;"
             "border-radius:6px'><b style='font-size:18px'>Zoning for the Cloud</b><br>"
             f"<span class='pa-sub' style='font-size:12px;color:{D['subtext']}'>Pennsylvania municipal data center "
             f"ordinances — {len(p)} municipalities</span><br>"
             f"<span class='pa-sub' style='font-size:12px;color:{D['subtext']}'>Principal Investigator: "
             "Valerie Holt, Lehigh University</span></div>")
    m.get_root().html.add_child(folium.Element(title))

    m.get_root().html.add_child(folium.Element(LEGEND_CSS))
    legend_html = _legend_html(muni_entries, county_entries)
    m.get_root().html.add_child(folium.Element(legend_html))

    # Must be added last: map children render in order, so the layers above exist when it runs.
    themes = {k: {key: t[key] for key in ("background", "county_line", "state_line", "county_ord_fill",
                                          "text", "subtext", "panel", "status_colors")}
              for k, t in config.THEMES.items()}
    toggle = MacroElement()
    toggle._template = Template(THEME_JS)
    toggle.cfg = {
        "map": m.get_name(), "dark_tiles": dark_tiles.get_name(), "state": state_layer.get_name(),
        "counties": county_layer.get_name(),
        "status_layers": [(s_, poly.get_name(), fg.get_name()) for s_, poly, fg in status_layers],
        "themes": json.dumps(themes), "county_styles": json.dumps(config.COUNTY_STATUS_STYLES),
        "light_url": TILES["light"], "attr": TILE_ATTR,
    }
    m.add_child(toggle)

    out_path = out_path or (config.ROOT / "docs" / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(out_path)
    print(f"Saved {out_path.relative_to(config.ROOT)}")


def _row(swatch, e):
    desc = f"<div class='pa-sub pa-desc'>{e['desc']}</div>" if e["desc"] else ""
    return (f"<div class='pa-row'>{swatch}<div><div>{e['label']} ({e['count']})</div>{desc}</div></div>")


def _group(title, note, rows):
    return (f"<div class='pa-group'><div class='pa-title'><span class='pa-sub pa-gtitle'>{title}</span> "
            f"<span class='pa-sub pa-note'>{note}</span></div>{rows}</div>")


def _legend_html(muni_entries, county_entries):
    """Two groups (towns & townships / county governments) in a collapsible bottom-left box.
    Swatch colors are set for the dark theme here and restyled by THEME_JS."""
    muni_rows = "".join(_row(
        f"<svg width='30' height='18'><rect class='pa-st-swatch' data-status='{e['key']}' x='1' y='1' "
        f"width='28' height='16' rx='2' fill='{D['status_colors'][e['key']]}' fill-opacity='{POLY_OPACITY}' "
        f"stroke='{D['status_colors'][e['key']]}'/><circle class='pa-st-dot' data-status='{e['key']}' "
        f"cx='15' cy='9' r='{DOT_RADIUS}' fill='{D['status_colors'][e['key']]}' stroke='{D['background']}'/>"
        "</svg>", e) for e in muni_entries)
    county_rows = "".join(_row(
        f"<svg width='30' height='18'><rect class='pa-swatch' x='1' y='1' width='28' height='16' "
        f"fill='{D['county_ord_fill']}' fill-opacity='{e['style']['fill']}' stroke='{D['county_ord_fill']}' "
        f"stroke-width='{e['style']['width'] * 1.2}' stroke-opacity='{e['style']['opacity']}' "
        f"stroke-dasharray='{e['style']['dash'] or 'none'}'/></svg>", e) for e in county_entries)
    return (f"<details class='pa-panel pa-legend' open style='color:{D['text']};background:{D['panel']}'>"
            "<summary class='pa-sub'>Legend</summary><div class='pa-groups'>"
            + _group("Towns &amp; townships", "(colored shapes and dots)", muni_rows)
            + _group("County governments", "(gray shading)", county_rows)
            + "</div></details>")


LEGEND_CSS = """<style>
.pa-legend {position:fixed; bottom:52px; left:12px;  /* clears the scale bar */
  z-index:9999; max-width:calc(100vw - 24px);
  font-family:Helvetica,Arial,sans-serif; font-size:12.5px; padding:8px 12px; border-radius:6px;
  box-sizing:border-box}
.pa-legend summary {cursor:pointer; font-size:11px; letter-spacing:.06em; text-transform:uppercase}
.pa-legend .pa-groups {display:flex; flex-wrap:wrap; gap:6px 22px; margin-top:6px}
.pa-legend .pa-gtitle {font-variant:small-caps; text-transform:lowercase; font-size:14px;
  letter-spacing:.05em; font-weight:bold}
.pa-legend .pa-note {font-size:11px}
.pa-legend .pa-row {display:flex; align-items:center; gap:8px; margin-top:5px}
.pa-legend .pa-row svg {flex:none}
.pa-legend .pa-desc {font-size:11px; margin-top:1px}
</style>"""


THEME_JS = """
{% macro script(this, kwargs) %}
(function () {
  var c = {{ this.cfg | tojson }};
  var THEMES = JSON.parse(c.themes), CSTYLES = JSON.parse(c.county_styles);
  var map = window[c.map], KEY = "pa-dc-zoning-theme";
  var tiles = {dark: window[c.dark_tiles],
               light: L.tileLayer(c.light_url, {attribution: c.attr, maxZoom: 16})};
  var stateLayer = window[c.state], countyLayer = window[c.counties];
  var statusLayers = c.status_layers.map(function (x) {
    return {status: x[0], poly: window[x[1]], group: window[x[2]]};
  });
  var current, btn;

  function countyStyle(t) {
    return function (f) {
      var st = CSTYLES[f.properties.county_status];
      if (!st) return {color: t.county_line, weight: 0.6, opacity: 1, dashArray: null, fillOpacity: 0};
      return {color: t.county_ord_fill, weight: st.width * 1.2, opacity: st.opacity,
              dashArray: st.dash || null, fillColor: t.county_ord_fill, fillOpacity: st.fill};
    };
  }

  function apply(mode) {
    var t = THEMES[mode], other = mode === "dark" ? "light" : "dark";
    if (map.hasLayer(tiles[other])) map.removeLayer(tiles[other]);
    if (!map.hasLayer(tiles[mode])) tiles[mode].addTo(map);
    stateLayer.setStyle({color: t.state_line});
    countyLayer.setStyle(countyStyle(t));
    statusLayers.forEach(function (s) {
      var col = t.status_colors[s.status];
      s.poly.setStyle({color: col, fillColor: col});
      s.group.eachLayer(function (l) {
        if (l instanceof L.CircleMarker) l.setStyle({color: t.background, fillColor: col});
      });
    });
    document.querySelectorAll(".pa-panel").forEach(function (el) {
      el.style.background = t.panel; el.style.color = t.text;
    });
    document.querySelectorAll(".pa-sub").forEach(function (el) { el.style.color = t.subtext; });
    document.querySelectorAll(".pa-swatch").forEach(function (el) {
      el.setAttribute("stroke", t.county_ord_fill); el.setAttribute("fill", t.county_ord_fill);
    });
    document.querySelectorAll(".pa-st-swatch, .pa-st-dot").forEach(function (el) {
      var col = t.status_colors[el.dataset.status];
      el.setAttribute("fill", col);
      el.setAttribute("stroke", el.classList.contains("pa-st-dot") ? t.background : col);
    });
    current = mode;
    if (btn) {
      btn.textContent = mode === "dark" ? "\\u2600\\uFE0F" : "\\uD83C\\uDF19";
      btn.title = btn.ariaLabel = "Switch to " + other + " mode";
    }
  }

  var Toggle = L.Control.extend({
    options: {position: "topleft"},
    onAdd: function () {
      var div = L.DomUtil.create("div", "leaflet-bar");
      btn = L.DomUtil.create("a", "", div);
      btn.href = "#"; btn.setAttribute("role", "button");
      btn.style.fontSize = "16px"; btn.style.cursor = "pointer";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.on(btn, "click", function (e) {
        L.DomEvent.preventDefault(e);
        var next = current === "dark" ? "light" : "dark";
        apply(next);
        try { localStorage.setItem(KEY, next); } catch (err) {}
      });
      return div;
    }
  });
  map.addControl(new Toggle());

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (err) {}
  var prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  apply(saved === "dark" || saved === "light" ? saved : (prefersLight ? "light" : "dark"));
})();
{% endmacro %}
"""
