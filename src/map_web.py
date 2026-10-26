"""Interactive Leaflet map (folium) -> docs/index.html for GitHub Pages.

Rendered in the dark theme; a small script (THEME_JS) restyles the layers for
light mode, driven by a sun/moon toggle, prefers-color-scheme and localStorage.
"""
import html
import json
import folium
from branca.element import MacroElement
from jinja2 import Template
from . import config, insets, legend

D = config.DARK_THEME
TILES = {
    "dark": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    "light": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
}
TILE_ATTR = "Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
POLY_OPACITY, DOT_RADIUS = 0.45, 5  # shared by the map layers and the legend swatches
DC_PX, DC_OPACITY = 8, 0.75  # existing data center diamonds (no capacity field to scale by)
DC_CREDIT = (f"PNNL {config.DATACENTER_ATLAS['name']} {config.DATACENTER_ATLAS['version']} "
             "(doi:" + config.DATACENTER_ATLAS["doi"] + "), &copy; OpenStreetMap contributors, ODbL")


def make_web_map(state, counties, polys, points, out_path=None, datacenters=None):
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

    # Data centers mapped in the PNNL Atlas: partial-inventory context layer, off by default. Color comes from a CSS variable
    # that THEME_JS sets, so the diamonds follow the theme toggle.
    dc_entries = legend.datacenter_entries(datacenters)
    for e in dc_entries:
        fg = folium.FeatureGroup(name=f"{e['label']} ({e['count']})", show=False).add_to(m)
        icon_html = (f"<div class='pa-dc' style='width:{DC_PX}px;height:{DC_PX}px;"
                     f"opacity:{DC_OPACITY};transform:rotate(45deg)'></div>")
        for _, r in e["rows"].to_crs(4326).iterrows():
            rows = [("Name", r["name"]), ("Operator", r["operator"]),
                    ("Footprint", f"{r['sqft']:,.0f} sq ft" if r["sqft"] == r["sqft"] and r["sqft"] else None)]
            body = "".join(f"<b>{k}:</b> {html.escape(str(v))}<br>" for k, v in rows
                           if v is not None and v == v and str(v).strip())
            popup = (f"{body or '<i>Unnamed data center</i><br>'}"
                     f"<span style='font-size:10px;color:#777'>Source: {DC_CREDIT}</span>")
            folium.Marker([r.geometry.y, r.geometry.x], popup=folium.Popup(popup, max_width=280),
                          icon=folium.DivIcon(html=icon_html, icon_size=(DC_PX, DC_PX),
                                              icon_anchor=(DC_PX // 2, DC_PX // 2))).add_to(fg)

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
    legend_html = _legend_html(muni_entries, county_entries, dc_entries)
    m.get_root().html.add_child(folium.Element(legend_html))

    # Must be added last: map children render in order, so the layers above exist when it runs.
    themes = {k: {key: t[key] for key in ("background", "county_line", "state_line", "county_ord_fill",
                                          "text", "subtext", "panel", "status_colors", "datacenter")}
              for k, t in config.THEMES.items()}
    toggle = MacroElement()
    toggle._template = Template(THEME_JS)
    toggle.cfg = {
        "map": m.get_name(), "dark_tiles": dark_tiles.get_name(), "state": state_layer.get_name(),
        "counties": county_layer.get_name(),
        "status_layers": [(s_, poly.get_name(), fg.get_name()) for s_, poly, fg in status_layers],
        "themes": json.dumps(themes), "county_styles": json.dumps(config.COUNTY_STATUS_STYLES),
        "light_url": TILES["light"], "attr": TILE_ATTR,
        # same extents as the static map's insets (config.INSETS)
        "zooms": [(spec["title"], insets.bounds_4326(spec["extent"])) for spec in config.INSETS.values()],
    }
    m.add_child(toggle)

    out_path = out_path or (config.ROOT / "docs" / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(out_path)
    print(f"Saved {out_path.name}")


def _row(swatch, e):
    desc = f"<div class='pa-sub pa-desc'>{e['desc']}</div>" if e["desc"] else ""
    return (f"<div class='pa-row'>{swatch}<div><div>{e['label']} ({e['count']})</div>{desc}</div></div>")


def _group(title, note, rows):
    return (f"<div class='pa-group'><div class='pa-title'><span class='pa-sub pa-gtitle'>{title}</span> "
            f"<span class='pa-sub pa-note'>{note}</span></div>{rows}</div>")


def _legend_html(muni_entries, county_entries, dc_entries=()):
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
    dc_rows = "".join(_row(
        f"<svg width='30' height='18'><rect class='pa-dc-swatch' x='11' y='5' width='{DC_PX}' "
        f"height='{DC_PX}' transform='rotate(45 15 9)' fill='{D['datacenter']}' "
        f"fill-opacity='{DC_OPACITY}'/></svg>", e) for e in dc_entries)
    dc_group = (_group("Data centers", "(context only)",
                       dc_rows + "<div class='pa-sub pa-desc' style='margin-top:4px'>Off by default: "
                       "turn on in the layer list</div>") if dc_entries else "")
    return (f"<details class='pa-panel pa-legend' open style='color:{D['text']};background:{D['panel']}'>"
            "<summary class='pa-sub'>Legend</summary><div class='pa-groups'>"
            + _group("Towns &amp; townships", "(colored shapes and dots)", muni_rows)
            + _group("County governments", "(gray shading)", county_rows)
            + dc_group + "</div></details>")


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
.pa-dc {background:var(--pa-dc, #fff)}
.pa-zoom a {width:auto !important; padding:0 8px; font:bold 12px Helvetica,Arial,sans-serif;
  white-space:nowrap}
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
    document.documentElement.style.setProperty("--pa-dc", t.datacenter);
    document.querySelectorAll(".pa-dc-swatch").forEach(function (el) { el.setAttribute("fill", t.datacenter); });
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

  // "Western PA" / "Eastern PA": zoom to the static map's inset extents.
  var Zooms = L.Control.extend({
    options: {position: "topleft"},
    onAdd: function () {
      var div = L.DomUtil.create("div", "leaflet-bar pa-zoom");
      L.DomEvent.disableClickPropagation(div);
      c.zooms.forEach(function (z) {
        var a = L.DomUtil.create("a", "", div);
        a.href = "#"; a.textContent = z[0]; a.title = "Zoom to " + z[0];
        a.setAttribute("role", "button");
        L.DomEvent.on(a, "click", function (e) {
          L.DomEvent.preventDefault(e);
          var leg = document.querySelector(".pa-legend");  // keep the extent clear of the open legend
          var pad = leg && leg.open ? leg.offsetHeight + 20 : 0;
          map.fitBounds(z[1], {paddingTopLeft: [0, 0], paddingBottomRight: [0, pad]});
        });
      });
      return div;
    }
  });
  map.addControl(new Zooms());

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (err) {}
  var prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  apply(saved === "dark" || saved === "light" ? saved : (prefersLight ? "light" : "dark"));
})();
{% endmacro %}
"""
