"""Static, print-quality statewide map (PNG + SVG), dark or light theme."""
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from . import config


def _mpl_dash(dash):
    """'4 3' -> matplotlib (offset, (on, off)) tuple; '' -> solid."""
    return (0, tuple(float(x) for x in dash.split())) if dash else "-"


def make_static_map(state, counties, munis, polys, points, *,
                    show_counties=True, show_muni_lines=True, county_ordinances=True,
                    style="both", label_counties=False, theme="dark", out_name=None, dpi=300):
    """style: 'polygons' | 'points' | 'both';  theme: 'dark' | 'light'"""
    T = config.THEMES[theme]
    colors = T["status_colors"]
    fig, ax = plt.subplots(figsize=(16, 10), facecolor=T["background"])
    ax.set_facecolor(T["background"])
    ax.set_axis_off()

    state.plot(ax=ax, color=T["land"], edgecolor="none", zorder=1)
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
                sub.plot(ax=ax, color=color, markersize=38, edgecolor=T["background"],
                         linewidth=0.8, zorder=7)

    if label_counties:
        active = counties[counties.get("has_muni_activity", False) == True]  # noqa: E712
        for _, r in active.iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["NAME"].upper(), (p.x, p.y), ha="center", va="center", fontsize=6.5,
                        color=T["subtext"], alpha=0.8, zorder=8)

    # --- legend ---
    counts = polys["status"].value_counts()
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9,
                      markerfacecolor=colors[s], markeredgecolor=T["background"],
                      label=f"{s}  ({counts.get(s, 0)})") for s in config.STATUS_ORDER]
    leg = ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=11,
                    labelcolor=T["text"], title="MUNICIPAL ORDINANCE STATUS", ncol=len(handles),
                    title_fontsize=10.5, bbox_to_anchor=(0.0, -0.01), columnspacing=2.2)
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
        cleg = ax.legend(handles=c_handles, loc="upper left", frameon=False, fontsize=11,
                         labelcolor=T["text"], title="COUNTY-LEVEL ACTION", ncol=len(c_handles),
                         title_fontsize=10.5, bbox_to_anchor=(0.0, -0.085), columnspacing=2.2,
                         handlelength=3)
        cleg.get_title().set_color(T["subtext"])
        cleg._legend_box.align = "left"

    # --- titles + credits ---
    n_cty = polys["county"].nunique()
    fig.text(0.05, 0.93, "ZONING FOR THE CLOUD", color=T["text"], fontsize=26,
             fontweight="bold", ha="left")
    fig.text(0.05, 0.895,
             f"{len(polys)} Pennsylvania municipalities across {n_cty} of 67 counties have adopted, "
             "paused, or proposed data center zoning", color=T["subtext"], fontsize=13, ha="left")
    fig.text(0.95, 0.0,
             "Ordinance data: compiled by author from municipal codes, public notices, county reviews & SAVRN\n"
             f"Boundaries: U.S. Census Bureau Cartographic Boundary Files ({config.CB_YEAR})  |  "
             "Projection: NAD83 / Pennsylvania North",
             color=T["subtext"], fontsize=8, ha="right", va="top", linespacing=1.5)

    minx, miny, maxx, maxy = state.total_bounds
    pad = (maxx - minx) * 0.02
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)
    ax.set_aspect("equal")

    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    out_name = out_name or f"pa_datacenter_zoning_{style}{'' if show_counties else '_nocounties'}_{theme}"
    for ext in ("png", "svg"):
        fig.savefig(config.OUTPUTS / f"{out_name}.{ext}", dpi=dpi, facecolor=T["background"],
                    bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"Saved outputs/{out_name}.png + .svg")
