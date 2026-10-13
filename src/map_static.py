"""Static, print-quality statewide map (PNG + SVG), dark or light theme."""
from functools import lru_cache
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle
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
LEGEND_ROW = 0.052  # figure-fraction height of one legend entry (label + description)


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


def _legend_group(fig, T, x, top, title, note, entries):
    """Title (+ small gray note), then per entry: swatch | "label (N)" over a lighter description.
    Titles are uppercase at a small size: matplotlib can't render true small caps.
    -> {"artists": [...], "bottom": figure-fraction y of the group's lower edge}"""
    fw, fh = fig.get_size_inches()
    title_t = fig.text(x, top, title, color=T["subtext"], fontsize=11, fontweight="semibold",
                       ha="left", va="top")
    note_t = fig.text(0, 0, note, color=T["subtext"], fontsize=9.5, alpha=0.75, ha="left",
                      va="baseline")
    fig.canvas.draw()  # the title's extent places the note after it
    r = fig.canvas.get_renderer()
    bb = title_t.get_window_extent(r).transformed(fig.transFigure.inverted())
    note_t.set_position((bb.x1 + 0.005, bb.y0 + 0.002))
    arts = [title_t, note_t]
    sw_w = 0.022
    sw_h = sw_w * fw / fh * 0.75
    y = bb.y0 - 0.008 - LEGEND_ROW / 2
    for e, swatch in entries:
        for art in swatch(fig, x, y, sw_w, sw_h):
            fig.add_artist(art)
            arts.append(art)
        tx = x + sw_w + 0.009
        arts.append(fig.text(tx, y + 0.001 if e["desc"] else y, f"{e['label']}  ({e['count']})",
                             color=T["text"], fontsize=12.5, ha="left",
                             va="bottom" if e["desc"] else "center"))
        if e["desc"]:
            arts.append(fig.text(tx, y - 0.002, e["desc"], color=T["subtext"], fontsize=10,
                                 ha="left", va="top"))
        y -= LEGEND_ROW
    return {"artists": arts, "bottom": y + LEGEND_ROW / 2 - 0.01}


def _check_layout(fig, ax, groups, credits):
    """Fail loudly if a legend group overlaps the map, the other group, or the credits."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [Bbox.union([a.get_window_extent(r) for a in g["artists"]]) for g in groups]
    others = {"map": ax.get_window_extent(r), "credits": credits.get_window_extent(r)}
    for i, b in enumerate(boxes):
        for name, o in others.items():
            if b.overlaps(o):
                raise RuntimeError(f"legend group {i + 1} overlaps the {name}")
        for j in range(i + 1, len(boxes)):
            if b.overlaps(boxes[j]):
                raise RuntimeError(f"legend groups {i + 1} and {j + 1} overlap")


def make_static_map(state, counties, munis, polys, points, **kw):
    family = _font_family()
    with plt.rc_context({"font.family": family} if family else {}):
        _draw(state, counties, munis, polys, points, **kw)


def _draw(state, counties, munis, polys, points, *,
          show_counties=True, show_muni_lines=True, county_ordinances=True,
          style="both", label_counties=False, theme="dark", out_name=None, dpi=300):
    """style: 'polygons' | 'points' | 'both';  theme: 'dark' | 'light'"""
    T = config.THEMES[theme]
    colors = T["status_colors"]
    fig, ax = plt.subplots(figsize=(16, 10), facecolor=T["background"])
    ax.set_facecolor(T["background"])
    ax.set_axis_off()

    minx, miny, maxx, maxy = state.total_bounds
    pad = (maxx - minx) * 0.02
    view = (minx - pad, miny - pad, maxx + pad, maxy + pad)

    # --- context: neighboring states (faint outlines + labels) ---
    nb = _neighbors()
    nb.boundary.plot(ax=ax, color=T["neighbor_line"], linewidth=0.6, zorder=0.5)
    for _, r in nb.iterrows():
        vis = r.geometry.intersection(box(*view))
        if vis.is_empty:
            continue
        part = max(getattr(vis, "geoms", [vis]), key=lambda g: g.area)
        bx0, by0, bx1, by1 = part.bounds
        if part.area < 150e6:  # < 150 km² visible: no room for a label
            continue
        p = part.representative_point()
        ax.text(p.x, p.y, r["label"], ha="center", va="center", fontsize=8.5, color=T["subtext"],
                alpha=0.6, rotation=90 if (by1 - by0) > (bx1 - bx0) else 0, zorder=0.6)

    # --- land + relief ---
    state.plot(ax=ax, color=T["land"], edgecolor="none", zorder=1)
    if T["hillshade"]:
        rgba, extent = _hillshade(state.union_all().wkb, T["hillshade"])
        im = ax.imshow(rgba, extent=extent, origin="upper", interpolation="bilinear", zorder=1.5)
        clip = _geom_patch(state.union_all(), ax)
        ax.add_patch(clip)
        im.set_clip_path(clip)

    if show_muni_lines:
        munis.boundary.plot(ax=ax, color=T["muni_line"], linewidth=0.15, zorder=2)

    muni_entries = legend.municipal_entries(polys, points)
    county_entries = legend.county_entries(counties) if county_ordinances else []
    has_county_ords = any(e["count"] for e in county_entries)
    for e in county_entries:
        sub, st = e["rows"], e["style"]
        if not len(sub):
            continue
        if st["fill"]:
            sub.plot(ax=ax, color=T["county_ord_fill"], alpha=st["fill"], edgecolor="none", zorder=2)
        sub.boundary.plot(ax=ax, color=T["county_ord_fill"], linewidth=st["width"],
                          linestyle=_mpl_dash(st["dash"]), alpha=st["opacity"], zorder=4)

    if show_counties:
        counties.boundary.plot(ax=ax, color=T["county_line"], linewidth=0.5, zorder=3)
    state.boundary.plot(ax=ax, color=T["state_line"], linewidth=1.1, zorder=5)

    sym = _symbols(style)
    for e in muni_entries:
        color = colors[e["key"]]
        if sym["poly_alpha"] and len(e["polys"]):
            e["polys"].plot(ax=ax, color=color, alpha=sym["poly_alpha"], edgecolor=color,
                            linewidth=0.4, zorder=6)
        if sym["dot"] and len(e["points"]):
            e["points"].plot(ax=ax, color=color, markersize=GLOW_SIZE, alpha=0.15, edgecolor="none",
                             zorder=6.5)  # soft glow
            e["points"].plot(ax=ax, color=color, markersize=DOT_SIZE, edgecolor=T["background"],
                             linewidth=0.8, zorder=7)

    if label_counties:
        active = counties[counties.get("has_muni_activity", False) == True]  # noqa: E712
        for _, r in active.iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["NAME"].upper(), (p.x, p.y), ha="center", va="center", fontsize=6.5,
                        color=T["subtext"], alpha=0.8, zorder=8)

    # --- regional callouts (counts from the data) ---
    for name, spec in config.REGION_CALLOUTS.items():
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

    # --- titles + credits ---
    n_cty = polys["county"].nunique()
    fig.text(0.05, 0.93, "ZONING FOR THE CLOUD", color=T["text"], fontsize=32,
             fontweight="bold", ha="left")
    fig.text(0.05, 0.895,
             f"{len(polys)} Pennsylvania municipalities across {n_cty} of 67 counties have adopted, "
             "paused, or proposed data center zoning", color=T["subtext"], fontsize=15, ha="left")

    ax.set_xlim(view[0], view[2])
    ax.set_ylim(view[1], view[3])
    ax.set_aspect("equal")
    ax.apply_aspect()  # so ax.get_position() is the map's real footprint

    # --- legend: two groups side by side under the map, credits below them ---
    pos = ax.get_position()
    top = pos.y0 - 0.005
    groups = [_legend_group(fig, T, pos.x0 + 0.01, top, "TOWNS & TOWNSHIPS", sym["note"],
                            [(e, _status_swatch(T, colors[e["key"]], sym)) for e in muni_entries])]
    if has_county_ords:
        groups.append(_legend_group(fig, T, pos.x0 + 0.38, top, "COUNTY GOVERNMENTS", "(gray shading)",
                                    [(e, _county_swatch(T, e["style"])) for e in county_entries]))
    legend_bottom = min(g["bottom"] for g in groups)
    credits = fig.text(0.95, legend_bottom - 0.015,
                       "Principal Investigator: Valerie Holt, Lehigh University  |  Cartography: Geovisual Stories\n"
                       "Data: municipal codes, public notices, county reviews & SAVRN  |  "
                       f"Boundaries: U.S. Census Bureau ({config.CB_YEAR})  |  "
                       "Relief: USGS 3DEP  |  NAD83 / Pennsylvania North",
                       color=T["subtext"], fontsize=9, ha="right", va="top", linespacing=1.5)
    _check_layout(fig, ax, groups, credits)

    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_name = out_name or f"pa_datacenter_zoning_{style}{'' if show_counties else '_nocounties'}_{theme}"
    png = config.OUTPUTS / f"{out_name}.png"
    fig.savefig(png, dpi=dpi, facecolor=T["background"], bbox_inches="tight", pad_inches=0.3)
    # SVG: vectors stay vectors; dpi only sets the resolution of the embedded relief raster.
    fig.savefig(config.OUTPUTS / f"{out_name}.svg", dpi=SVG_RASTER_DPI, facecolor=T["background"],
                bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    # Relief texture makes full-color PNGs ~5x larger; a 256-color palette is visually identical here.
    Image.open(png).convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT,
                                            dither=Image.Dither.NONE).save(png, optimize=True)
    print(f"Saved outputs/{out_name}.png + .svg")
