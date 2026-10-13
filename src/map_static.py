"""Static, print-quality statewide map (PNG + SVG), dark or light theme."""
from functools import lru_cache
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.lines import Line2D
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from PIL import Image
from shapely.geometry import box
from . import boundaries, config, fonts, terrain

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

    has_county_ords = county_ordinances and "county_status" in counties and counties["county_status"].notna().any()
    if has_county_ords:
        c = counties[counties["county_status"].notna()]
        c.plot(ax=ax, color=T["county_ord_fill"], alpha=0.07, edgecolor="none", zorder=2)
        for cs in config.COUNTY_STATUS_ORDER:
            sub = c[c["county_status"] == cs]
            if len(sub):
                st = config.COUNTY_STATUS_STYLES[cs]
                sub.boundary.plot(ax=ax, color=T["county_ord_fill"], linewidth=st["width"],
                                  linestyle=_mpl_dash(st["dash"]), alpha=st["opacity"], zorder=4)

    if show_counties:
        counties.boundary.plot(ax=ax, color=T["county_line"], linewidth=0.5, zorder=3)
    state.boundary.plot(ax=ax, color=T["state_line"], linewidth=1.1, zorder=5)

    for status in config.STATUS_ORDER:
        color = colors[status]
        if style in ("polygons", "both"):
            sub = polys[polys["status"] == status]
            if len(sub):
                sub.plot(ax=ax, color=color, alpha=0.85 if style == "polygons" else 0.55,
                         edgecolor=color, linewidth=0.4, zorder=6)
        if style in ("points", "both"):
            sub = points[points["status"] == status]
            if len(sub):
                sub.plot(ax=ax, color=color, markersize=240, alpha=0.15, edgecolor="none",
                         zorder=6.5)  # soft glow
                sub.plot(ax=ax, color=color, markersize=38, edgecolor=T["background"],
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

    # --- legend ---
    counts = polys["status"].value_counts()
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9,
                      markerfacecolor=colors[s], markeredgecolor=T["background"],
                      label=f"{s}  ({counts.get(s, 0)})") for s in config.STATUS_ORDER]
    leg = ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=12.5,
                    labelcolor=T["text"], title="MUNICIPAL ORDINANCE STATUS", ncol=len(handles),
                    title_fontsize=11.5, bbox_to_anchor=(0.0, -0.01), columnspacing=2.2)
    leg.get_title().set_color(T["subtext"])
    leg._legend_box.align = "left"

    if has_county_ords:
        ax.add_artist(leg)
        c_counts = counties["county_status"].value_counts()
        c_handles = []
        for cs in config.COUNTY_STATUS_ORDER:
            st = config.COUNTY_STATUS_STYLES[cs]
            c_handles.append(Line2D([0], [0], color=T["county_ord_fill"], alpha=st["opacity"],
                                    linewidth=st["width"] * 1.6, linestyle=_mpl_dash(st["dash"]),
                                    label=f"{cs}  ({c_counts.get(cs, 0)})"))
        cleg = ax.legend(handles=c_handles, loc="upper left", frameon=False, fontsize=12.5,
                         labelcolor=T["text"], title="COUNTY-LEVEL ACTION", ncol=len(c_handles),
                         title_fontsize=11.5, bbox_to_anchor=(0.0, -0.1), columnspacing=2.2,
                         handlelength=3)
        cleg.get_title().set_color(T["subtext"])
        cleg._legend_box.align = "left"

    # --- titles + credits ---
    n_cty = polys["county"].nunique()
    fig.text(0.05, 0.93, "ZONING FOR THE CLOUD", color=T["text"], fontsize=32,
             fontweight="bold", ha="left")
    fig.text(0.05, 0.895,
             f"{len(polys)} Pennsylvania municipalities across {n_cty} of 67 counties have adopted, "
             "paused, or proposed data center zoning", color=T["subtext"], fontsize=15, ha="left")
    fig.text(0.95, 0.0,
             "Principal Investigator: Valerie Holt, Lehigh University  |  Cartography: Geovisual Stories\n"
             "Data: municipal codes, public notices, county reviews & SAVRN  |  "
             f"Boundaries: U.S. Census Bureau ({config.CB_YEAR})  |  "
             "Relief: USGS 3DEP  |  NAD83 / Pennsylvania North",
             color=T["subtext"], fontsize=9, ha="right", va="top", linespacing=1.5)

    ax.set_xlim(view[0], view[2])
    ax.set_ylim(view[1], view[3])
    ax.set_aspect("equal")

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
