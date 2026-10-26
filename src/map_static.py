"""Static, print-quality statewide map (PNG + SVG), dark or light theme."""
from functools import lru_cache
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.colors import to_rgb
from PIL import Image
from shapely.geometry import box
from . import boundaries, config, fonts, legend, terrain

SVG_RASTER_DPI = 100


def _mpl_dash(dash):
    """'4 3' -> matplotlib (offset, (on, off)) tuple; '' -> solid."""
    return (0, tuple(float(x) for x in dash.split())) if dash else "-"


@lru_cache(maxsize=None)
def _font_family():
    return fonts.register()


@lru_cache(maxsize=None)
def _neighbors():
    return boundaries.load_neighbors()


@lru_cache(maxsize=None)
def _hillshade(state_wkb, strength):
    import shapely
    dem, extent = terrain.load_dem(shapely.from_wkb(state_wkb))
    return terrain.hillshade_rgba(dem, extent, strength)


def _geom_patch(geom, ax):
    """Shapely (Multi)Polygon -> invisible PathPatch in data coords, for clipping."""
    verts, codes = [], []
    for poly in getattr(geom, "geoms", [geom]):
        for ring in (poly.exterior, *poly.interiors):
            xy = np.asarray(ring.coords)[:, :2]
            verts.extend(xy)
            codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
    return PathPatch(Path(verts, codes), transform=ax.transData, facecolor="none", edgecolor="none")



DOT_SIZE, GLOW_SIZE = 38, 240  # scatter marker areas (pt²), shared by map and legend
# Existing data centers: small, slightly transparent diamonds. The Atlas has no capacity (MW)
# field, so they aren't size-scaled.
DC_SIZE, DC_ALPHA = 20, 0.7
LEGEND_GAP = 0.045  # figure-fraction space between legend groups
LEGEND_ROW = 0.52   # inches: height of one legend entry (label + description)

# Page layout, in inches. Statewide map on top, a row of insets below it, legend + credits under.
FIG_W = 16
MARGIN = 0.8                 # left/right page margin; titles, insets and legend align to it
MAIN_TOP, MAIN_H = 1.3, 6.4  # statewide map box (equal aspect shrinks it to fit)
INSET_GAP = 0.3              # between neighboring insets (one row, config.INSETS order)
N_INSETS = len(config.INSETS)
INSET_W = (FIG_W - 2 * MARGIN - (N_INSETS - 1) * INSET_GAP) / N_INSETS
INSET_H = INSET_W / config.INSET_ASPECT
INSET_TOP = MAIN_TOP + MAIN_H + 0.55  # leaves room for the inset titles
LEGEND_TOP = INSET_TOP + INSET_H + 0.35
FIG_H = LEGEND_TOP + 2.9     # legend (3 rows) + credits


def _symbols(style):
    """How municipalities are drawn for a style; the legend swatches reuse it."""
    return {"poly_alpha": {"polygons": 0.85, "both": 0.55}.get(style, 0),
            "dot": style in ("points", "both"),
            "note": {"polygons": "(colored shapes)", "points": "(colored dots)"}.get(
                style, "(colored shapes and dots)")}


def _status_swatch(T, color, sym):
    def draw(fig, x, y, w, h):
        kw = dict(transform=fig.transFigure)
        arts = []
        if sym["poly_alpha"]:
            arts.append(Rectangle((x, y - h / 2), w, h, facecolor=color, alpha=sym["poly_alpha"],
                                  edgecolor=color, linewidth=0.4, **kw))
        if sym["dot"]:
            dot = dict(marker="o", linestyle="", markerfacecolor=color, **kw)
            arts.append(Line2D([x + w / 2], [y], markersize=GLOW_SIZE ** 0.5, markeredgecolor="none",
                               alpha=0.15, **dot))
            arts.append(Line2D([x + w / 2], [y], markersize=DOT_SIZE ** 0.5,
                               markeredgecolor=T["background"], markeredgewidth=0.8, **dot))
        return arts
    return draw


def _county_swatch(T, st):
    def draw(fig, x, y, w, h):
        kw = dict(transform=fig.transFigure)
        arts = []
        if st["fill"]:
            arts.append(Rectangle((x, y - h / 2), w, h, facecolor=T["county_ord_fill"],
                                  alpha=st["fill"], edgecolor="none", **kw))
        arts.append(Rectangle((x, y - h / 2), w, h, facecolor="none", edgecolor=T["county_ord_fill"],
                              alpha=st["opacity"], linewidth=st["width"],
                              linestyle=_mpl_dash(st["dash"]), **kw))
        return arts
    return draw


def _datacenter_swatch(T):
    def draw(fig, x, y, w, h):
        return [Line2D([x + w / 2], [y], transform=fig.transFigure, marker="D", linestyle="",
                       markersize=DC_SIZE ** 0.5, markerfacecolor=T["datacenter"],
                       markeredgecolor="none", alpha=DC_ALPHA)]
    return draw


def _legend_group(fig, T, x, top, title, note, entries):
    """Title (+ small gray note), then per entry: swatch | "label (N)" over a lighter description.
    Titles are uppercase at a small size: matplotlib can't render true small caps.
    Vertical spacing is in inches (converted here), so it doesn't depend on the figure height.
    -> {"artists": [...], "bottom": figure-fraction y of the lower edge, "right": ... x}"""
    fw, fh = fig.get_size_inches()
    title_t = fig.text(x, top, title, color=T["subtext"], fontsize=11, fontweight="semibold",
                       ha="left", va="top")
    note_t = fig.text(0, 0, note, color=T["subtext"], fontsize=9.5, alpha=0.75, ha="left",
                      va="baseline")
    fig.canvas.draw()  # the title's extent places the note after it
    r = fig.canvas.get_renderer()
    bb = title_t.get_window_extent(r).transformed(fig.transFigure.inverted())
    note_t.set_position((bb.x1 + 0.005, bb.y0 + 0.02 / fh))
    arts = [title_t, note_t]
    sw_w = 0.022
    sw_h = sw_w * fw / fh * 0.75
    row = LEGEND_ROW / fh
    y = bb.y0 - 0.08 / fh - row / 2
    for e, swatch in entries:
        for art in swatch(fig, x, y, sw_w, sw_h):
            fig.add_artist(art)
            arts.append(art)
        tx = x + sw_w + 0.009
        arts.append(fig.text(tx, y + 0.01 / fh if e["desc"] else y, f"{e['label']}  ({e['count']})",
                             color=T["text"], fontsize=12.5, ha="left",
                             va="bottom" if e["desc"] else "center"))
        if e["desc"]:
            arts.append(fig.text(tx, y - 0.02 / fh, e["desc"], color=T["subtext"], fontsize=10,
                                 ha="left", va="top"))
        y -= row
    fig.canvas.draw()
    right = max(a.get_window_extent(r).transformed(fig.transFigure.inverted()).x1 for a in arts)
    return {"artists": arts, "bottom": y + row / 2 - 0.1 / fh, "right": right}


def _check_layout(fig, obstacles, groups, credits):
    """Fail loudly if a legend group overlaps a map panel (or its title), another group,
    or the credits. obstacles: {name: artist}"""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [Bbox.union([a.get_window_extent(r) for a in g["artists"]]) for g in groups]
    others = {name: a.get_window_extent(r) for name, a in {**obstacles, "credits": credits}.items()}
    for i, b in enumerate(boxes):
        for name, o in others.items():
            if b.overlaps(o):
                raise RuntimeError(f"legend group {i + 1} overlaps the {name}")
        for j in range(i + 1, len(boxes)):
            if b.overlaps(boxes[j]):
                raise RuntimeError(f"legend groups {i + 1} and {j + 1} overlap")


def _crop_raster(rgba, extent, view, margin=0.05):
    """Cut the statewide hillshade down to a view (+margin), so insets don't each embed the
    whole raster in the SVG. extent/return extent: (minx, maxx, miny, maxy)."""
    minx, maxx, miny, maxy = extent
    h, w = rgba.shape[:2]
    px, py = (maxx - minx) / w, (maxy - miny) / h
    vx0, vy0, vx1, vy1 = view
    mx, my = (vx1 - vx0) * margin, (vy1 - vy0) * margin
    c0, c1 = max(0, int((vx0 - mx - minx) / px)), min(w, int(np.ceil((vx1 + mx - minx) / px)))
    r0, r1 = max(0, int((maxy - vy1 - my) / py)), min(h, int(np.ceil((maxy - vy0 + my) / py)))
    return rgba[r0:r1, c0:c1], (minx + c0 * px, minx + c1 * px, maxy - r1 * py, maxy - r0 * py)


def _draw_layers(ax, T, view, L, inset=False):
    """Everything that is drawn on both the statewide map and the insets. L: shared layers/flags."""
    ax.set_facecolor(T["background"])
    vx0, vy0, vx1, vy1 = view
    view_area = (vx1 - vx0) * (vy1 - vy0)
    k = 1.6 if inset else 1.0  # insets are zoomed in: slightly heavier lines

    # --- context: neighboring states (faint outlines + labels) ---
    nb = _neighbors()
    nb.boundary.plot(ax=ax, color=T["neighbor_line"], linewidth=0.6 * k, zorder=0.5)
    for _, r in nb.iterrows():
        vis = r.geometry.intersection(box(*view))
        if vis.is_empty:
            continue
        part = max(getattr(vis, "geoms", [vis]), key=lambda g: g.area)
        bx0, by0, bx1, by1 = part.bounds
        if part.area < 0.0012 * view_area:  # too little visible: no room for a label
            continue
        p = part.representative_point()
        ax.text(p.x, p.y, r["label"], ha="center", va="center", fontsize=8.5, color=T["subtext"],
                alpha=0.6, rotation=90 if (by1 - by0) > (bx1 - bx0) else 0, zorder=0.6, clip_on=True)

    # --- land + relief ---
    state = L["state"]
    state.plot(ax=ax, color=T["land"], edgecolor="none", zorder=1)
    if T["hillshade"]:
        rgba, extent = _hillshade(state.union_all().wkb, T["hillshade"])
        if inset:
            rgba, extent = _crop_raster(rgba, extent, view)
        im = ax.imshow(rgba, extent=extent, origin="upper", interpolation="bilinear", zorder=1.5)
        clip = _geom_patch(state.union_all(), ax)
        ax.add_patch(clip)
        im.set_clip_path(clip)

    if L["show_muni_lines"]:
        L["munis"].boundary.plot(ax=ax, color=T["muni_line"], linewidth=0.15 * (2 if inset else 1),
                                 zorder=2)
    for e in L["county_entries"]:
        sub, st = e["rows"], e["style"]
        if not len(sub):
            continue
        if st["fill"]:
            sub.plot(ax=ax, color=T["county_ord_fill"], alpha=st["fill"], edgecolor="none", zorder=2)
        sub.boundary.plot(ax=ax, color=T["county_ord_fill"], linewidth=st["width"],
                          linestyle=_mpl_dash(st["dash"]), alpha=st["opacity"], zorder=4)
    if L["show_counties"]:
        L["counties"].boundary.plot(ax=ax, color=T["county_line"], linewidth=0.5 * k, zorder=3)
    state.boundary.plot(ax=ax, color=T["state_line"], linewidth=1.1, zorder=5)

    sym, colors = L["sym"], T["status_colors"]
    for e in L["muni_entries"]:
        color = colors[e["key"]]
        if sym["poly_alpha"] and len(e["polys"]):
            e["polys"].plot(ax=ax, color=color, alpha=sym["poly_alpha"], edgecolor=color,
                            linewidth=0.4 * k, zorder=6)
        if sym["dot"] and len(e["points"]):
            e["points"].plot(ax=ax, color=color, markersize=GLOW_SIZE, alpha=0.15, edgecolor="none",
                             zorder=6.5)  # soft glow
            e["points"].plot(ax=ax, color=color, markersize=DOT_SIZE, edgecolor=T["background"],
                             linewidth=0.8, zorder=7)

    # Context, not the story: above the ordinance shapes but under the status dots.
    for e in L["dc_entries"]:
        e["rows"].plot(ax=ax, marker="D", markersize=DC_SIZE, color=T["datacenter"], alpha=DC_ALPHA,
                       edgecolor="none", zorder=6.8)

    ax.set_xlim(vx0, vx1)
    ax.set_ylim(vy0, vy1)
    # Insets keep their panel size; if a hand-edited extent has another shape, the view grows.
    ax.set_aspect("equal", adjustable="datalim" if inset else "box")
    ax.apply_aspect()


def _halo(T, width=2.5):
    return [patheffects.withStroke(linewidth=width, foreground=T["background"], alpha=0.85)]


def _inset_labels(ax, T, L):
    """County names (light gray) and ordinance municipality names, nudged apart by adjustText."""
    from adjustText import adjust_text
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    vbox = box(x0, y0, x1, y1)
    county_texts = []
    if L["show_counties"]:
        for _, r in L["counties"].iterrows():
            part = r.geometry.intersection(vbox)
            if part.is_empty or part.area < 0.03 * vbox.area:
                continue
            p = part.representative_point()
            county_texts.append(ax.text(p.x, p.y, r["NAME"].upper(), ha="center", va="center",
                                        fontsize=6.5, color=T["subtext"], alpha=0.75, zorder=8,
                                        clip_on=True))
    pts = L["points"][L["points"].within(vbox)]
    texts = [ax.text(r.geometry.x, r.geometry.y, r["municipality"], fontsize=6.5, color=T["text"],
                     ha="center", va="center", zorder=9, clip_on=True, path_effects=_halo(T))
             for _, r in pts.iterrows()]
    if texts:
        # avoid every symbol, not just the labeled ones: dots and data center diamonds
        avoid = [L["points"].geometry] + [e["rows"].geometry for e in L["dc_entries"]]
        xs = np.concatenate([g.x.to_numpy() for g in avoid])
        ys = np.concatenate([g.y.to_numpy() for g in avoid])
        adjust_text(texts, x=xs, y=ys, objects=county_texts or None, ax=ax,
                    expand=(1.15, 1.4), force_text=(0.3, 0.5), time_lim=5,
                    arrowprops=dict(arrowstyle="-", color=T["subtext"], lw=0.4, alpha=0.8))


def _scale_bar(ax, T):
    """Small km scale bar (with miles) in the lower-left corner of an inset."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    target = (x1 - x0) * 0.2 / 1000
    km = max([n for n in (1, 2, 5, 10, 20, 25, 50, 100) if n <= target] or [1])
    bx, by = x0 + (x1 - x0) * 0.04, y0 + (y1 - y0) * 0.05
    tick = (y1 - y0) * 0.012
    ax.plot([bx, bx + km * 1000], [by, by], color=T["text"], lw=1.6, solid_capstyle="butt",
            zorder=10, path_effects=_halo(T, 3.5))
    for x in (bx, bx + km * 1000):
        ax.plot([x, x], [by - tick, by + tick], color=T["text"], lw=1, zorder=10)
    ax.text(bx + km * 500, by + tick * 1.8, f"{km} km  ({km * 0.621371:.1f} mi)", ha="center",
            va="bottom", fontsize=8, color=T["text"], zorder=10, path_effects=_halo(T))


def make_static_map(state, counties, munis, polys, points, **kw):
    family = _font_family()
    with plt.rc_context({"font.family": family} if family else {}):
        _draw(state, counties, munis, polys, points, **kw)


def _draw(state, counties, munis, polys, points, *,
          show_counties=True, show_muni_lines=True, county_ordinances=True,
          style="both", label_counties=False, theme="dark", out_name=None, dpi=300,
          datacenters=None):
    """style: 'polygons' | 'points' | 'both';  theme: 'dark' | 'light';
    datacenters: existing data centers (datacenters.load()), or None to leave them off"""
    T = config.THEMES[theme]
    colors = T["status_colors"]
    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor=T["background"])

    def rect(left, top, w, h):  # inches from the top-left -> figure fraction [l, b, w, h]
        return [left / FIG_W, 1 - (top + h) / FIG_H, w / FIG_W, h / FIG_H]

    county_entries = legend.county_entries(counties) if county_ordinances else []
    L = {"state": state, "counties": counties, "munis": munis, "points": points,
         "show_counties": show_counties, "show_muni_lines": show_muni_lines,
         "sym": _symbols(style), "muni_entries": legend.municipal_entries(polys, points),
         "county_entries": county_entries, "dc_entries": legend.datacenter_entries(datacenters)}
    has_county_ords = any(e["count"] for e in county_entries)
    sym, muni_entries, dc_entries = L["sym"], L["muni_entries"], L["dc_entries"]

    # --- statewide map ---
    ax = fig.add_axes(rect(MARGIN, MAIN_TOP, FIG_W - 2 * MARGIN, MAIN_H))
    ax.set_axis_off()
    minx, miny, maxx, maxy = state.total_bounds
    pad = (maxx - minx) * 0.02
    _draw_layers(ax, T, (minx - pad, miny - pad, maxx + pad, maxy + pad), L)

    if label_counties:
        active = counties[counties.get("has_muni_activity", False) == True]  # noqa: E712
        for _, r in active.iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["NAME"].upper(), (p.x, p.y), ha="center", va="center", fontsize=6.5,
                        color=T["subtext"], alpha=0.8, zorder=8)

    # --- regional callouts (counts from the data) ---
    for name, spec in (config.REGION_CALLOUTS if config.SHOW_REGION_CALLOUTS else {}).items():
        sub = points[points["county"].isin(spec["counties"])]
        if not len(sub):
            continue
        ax_, ay_ = sub.geometry.x.mean(), sub.geometry.y.mean()
        dx, dy = (v * 1000 for v in spec["offset"])
        n = len(sub)
        ax.annotate(f"{name.upper()}\n{n} municipalit{'y' if n == 1 else 'ies'}",
                    xy=(ax_, ay_), xytext=(ax_ + dx, ay_ + dy),
                    ha="right" if dx < 0 else "left", va="center", fontsize=10, linespacing=1.15,
                    color=T["text"], fontweight="medium", zorder=9,
                    path_effects=[patheffects.withStroke(linewidth=3, foreground=T["background"],
                                                         alpha=0.7)],
                    arrowprops=dict(arrowstyle="-", color=T["subtext"], lw=0.8, alpha=0.9,
                                    shrinkA=3, shrinkB=6))

    # --- insets: extents outlined + lettered on the statewide map, panels below it ---
    obstacles = {"statewide map": ax}
    for i, (key, spec) in enumerate(config.INSETS.items()):
        x0, y0, x1, y1 = spec["extent"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="none", edgecolor=T["text"],
                               linewidth=0.9, zorder=9.5))
        ax.text(x0, y1, f" {key}", ha="left", va="bottom", fontsize=11, fontweight="bold",
                color=T["text"], zorder=9.5, path_effects=_halo(T))

        iax = fig.add_axes(rect(MARGIN + i * (INSET_W + INSET_GAP), INSET_TOP, INSET_W, INSET_H))
        iax.set_xticks([]); iax.set_yticks([])
        for s in iax.spines.values():
            s.set_edgecolor(T["text"]); s.set_linewidth(0.9); s.set_zorder(11)
        _draw_layers(iax, T, spec["extent"], L, inset=True)
        _inset_labels(iax, T, L)
        _scale_bar(iax, T)
        iax.set_xlabel(""); iax.set_ylabel("")  # geopandas adds "Easting [metre]" labels
        title = iax.set_title(f"{key} — {spec['title']}", loc="left", fontsize=12.5,
                              fontweight="semibold", color=T["text"], pad=6)
        obstacles[f"inset {key}"] = iax
        obstacles[f"inset {key} title"] = title

    # --- titles ---
    n_cty = polys["county"].nunique()
    fig.text(MARGIN / FIG_W, 1 - 0.7 / FIG_H, "ZONING FOR THE CLOUD", color=T["text"], fontsize=32,
             fontweight="bold", ha="left")
    fig.text(MARGIN / FIG_W, 1 - 1.05 / FIG_H,
             f"{len(polys)} Pennsylvania municipalities across {n_cty} of 67 counties have adopted, "
             "paused, or proposed data center zoning", color=T["subtext"], fontsize=15, ha="left")

    # --- legend: groups side by side under the insets (each placed after the previous one's
    # measured right edge), credits below them ---
    top = 1 - LEGEND_TOP / FIG_H
    specs = [("TOWNS & TOWNSHIPS", sym["note"],
              [(e, _status_swatch(T, colors[e["key"]], sym)) for e in muni_entries])]
    if has_county_ords:
        specs.append(("COUNTY GOVERNMENTS", "(gray shading)",
                      [(e, _county_swatch(T, e["style"])) for e in county_entries]))
    if dc_entries:
        specs.append(("EXISTING DATA CENTERS", "(source: PNNL Data Center Atlas)",
                      [(e, _datacenter_swatch(T)) for e in dc_entries]))
    groups, x = [], MARGIN / FIG_W
    for title, note, entries in specs:
        groups.append(_legend_group(fig, T, x, top, title, note, entries))
        x = groups[-1]["right"] + LEGEND_GAP
    legend_bottom = min(g["bottom"] for g in groups)
    dc_credit = (f"  |  Existing data centers: PNNL {config.DATACENTER_ATLAS['name']} "
                 f"{config.DATACENTER_ATLAS['version']}, © OpenStreetMap contributors (ODbL)"
                 if dc_entries else "")
    credits = fig.text(1 - MARGIN / FIG_W, legend_bottom - 0.15 / FIG_H,
                       "Principal Investigator: Valerie Holt, Lehigh University  |  Cartography: Geovisual Stories\n"
                       "Data: municipal codes, public notices, county reviews & SAVRN" + dc_credit + "\n"
                       f"Boundaries: U.S. Census Bureau ({config.CB_YEAR})  |  "
                       "Relief: USGS 3DEP  |  NAD83 / Pennsylvania North",
                       color=T["subtext"], fontsize=9, ha="right", va="top", linespacing=1.5)
    _check_layout(fig, obstacles, groups, credits)

    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_name = out_name or f"pa_datacenter_zoning_{style}{'' if show_counties else '_nocounties'}_{theme}"
    png = config.OUTPUTS / f"{out_name}.png"
    fig.savefig(png, dpi=dpi, facecolor=T["background"], bbox_inches="tight", pad_inches=0.3)
    # SVG: vectors stay vectors; dpi only sets the resolution of the embedded relief raster.
    fig.savefig(config.OUTPUTS / f"{out_name}.svg", dpi=SVG_RASTER_DPI, facecolor=T["background"],
                bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    _quantize(png, [*colors.values(), T["background"], T["text"], T["subtext"], T["datacenter"]])
    print(f"Saved {png.with_suffix('').name}.png + .svg")


def _quantize(png, keep_colors, n=256):
    """Relief texture makes full-color PNGs ~5x larger; a 256-color palette is visually
    identical, as long as small symbols keep their exact colors (median cut alone can merge
    the few dot pixels into the background), so those colors are reserved in the palette."""
    im = Image.open(png).convert("RGB")
    keep = sorted({tuple(round(v * 255) for v in to_rgb(c)) for c in keep_colors})
    base = im.quantize(n - len(keep), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = base.getpalette()[:3 * (n - len(keep))] + [v for c in keep for v in c]
    pal_im = Image.new("P", (1, 1))
    pal_im.putpalette(pal)
    im.quantize(palette=pal_im, dither=Image.Dither.NONE).save(png, optimize=True)
