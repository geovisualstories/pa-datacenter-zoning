"""Interactive Leaflet map (folium) -> docs/index.html for GitHub Pages.

Rendered in the dark theme; a small script (THEME_JS) restyles the layers for
light mode, driven by a sun/moon toggle, prefers-color-scheme and localStorage.
"""
import json
import folium
from branca.element import MacroElement
from jinja2 import Template
from . import config

D = config.DARK_THEME
TILES = {
    "dark": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    "light": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
}
TILE_ATTR = "Esri, HERE, Garmin, &copy; OpenStreetMap contributors"


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
                "dashArray": st["dash"] or None, "fillColor": D["county_ord_fill"], "fillOpacity": 0.06}

    county_layer = folium.GeoJson(
        c_[cfields + ["geometry"]], name="County boundaries / county-level ordinances",
        style_function=county_style,
        tooltip=folium.GeoJsonTooltip(["NAME", "county_status"], aliases=["County", "County-level"]),
    ).add_to(m)

    fields = ["municipality", "county", "status", "status_raw", "action_date", "source"]
    aliases = ["Municipality", "County", "Category", "Status detail", "Action date", "Source"]
    status_layers = []
    for status in config.STATUS_ORDER:
        col = D["status_colors"][status]
        fg = folium.FeatureGroup(name=f"{status} ({(p['status'] == status).sum()})").add_to(m)
        poly = folium.GeoJson(p[p["status"] == status][fields + ["geometry"]],
                              style_function=lambda f, col=col: {"color": col, "weight": 1,
                                                                 "fillColor": col, "fillOpacity": 0.45},
                              popup=folium.GeoJsonPopup(fields, aliases=aliases)).add_to(fg)
        for _, r in pt[pt["status"] == status].iterrows():
            folium.CircleMarker([r.geometry.y, r.geometry.x], radius=5, color=D["background"],
                                weight=1, fill=True, fill_color=col, fill_opacity=1,
                                tooltip=f"{r['municipality']} ({r['county']} Co.) — {status}").add_to(fg)
        status_layers.append((status, poly, fg))

    folium.LayerControl(collapsed=False).add_to(m)
    title = (f"<div class='pa-panel' style='position:fixed;top:12px;left:60px;z-index:9999;color:{D['text']};"
             f"font-family:Helvetica,Arial,sans-serif;background:{D['panel']};padding:10px 14px;"
             "border-radius:6px'><b style='font-size:18px'>Zoning for the Cloud</b><br>"
             f"<span class='pa-sub' style='font-size:12px;color:{D['subtext']}'>Pennsylvania municipal data center "
             f"ordinances — {len(p)} municipalities</span></div>")
    m.get_root().html.add_child(folium.Element(title))

    c_counts = c["county_status"].value_counts() if "county_status" in c else {}
    rows = "".join(
        f"<div style='display:flex;align-items:center;gap:8px;margin-top:4px'>"
        f"<svg width='34' height='10'><line class='pa-swatch' x1='1' y1='5' x2='33' y2='5' "
        f"stroke='{D['county_ord_fill']}' stroke-width='{st['width'] * 1.6}' stroke-opacity='{st['opacity']}' "
        f"stroke-dasharray='{st['dash'] or 'none'}'/></svg>{cs} ({c_counts.get(cs, 0)})</div>"
        for cs, st in ((cs, config.COUNTY_STATUS_STYLES[cs]) for cs in config.COUNTY_STATUS_ORDER))
    legend = (f"<div class='pa-panel' style='position:fixed;bottom:28px;left:12px;z-index:9999;color:{D['text']};"
              f"font-family:Helvetica,Arial,sans-serif;font-size:12px;background:{D['panel']};"
              "padding:8px 12px;border-radius:6px'>"
              f"<div class='pa-sub' style='font-size:10.5px;letter-spacing:.06em;color:{D['subtext']}'>"
              f"COUNTY-LEVEL ACTION</div>{rows}</div>")
    m.get_root().html.add_child(folium.Element(legend))

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
              dashArray: st.dash || null, fillColor: t.county_ord_fill, fillOpacity: 0.06};
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
      el.setAttribute("stroke", t.county_ord_fill);
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
