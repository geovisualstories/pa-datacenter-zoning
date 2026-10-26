"""Legend groups shared by the static and web maps.

Each entry carries the exact rows that get drawn for it, so a legend count is always
len() of what is on the map: the two can't disagree.
"""
from . import config


def municipal_entries(polys, points):
    out = []
    for status in config.STATUS_ORDER:
        label, desc = config.STATUS_LEGEND[status]
        sub_polys, sub_points = polys[polys["status"] == status], points[points["status"] == status]
        assert len(sub_polys) == len(sub_points), f"{status}: polygon/point counts differ"
        out.append({"key": status, "label": label, "desc": desc, "count": len(sub_polys),
                    "polys": sub_polys, "points": sub_points})
    return out


def county_entries(counties):
    status = counties["county_status"] if "county_status" in counties else None
    out = []
    for cs in config.COUNTY_STATUS_ORDER:
        st = config.COUNTY_STATUS_STYLES[cs]
        rows = counties.iloc[0:0] if status is None else counties[status == cs]
        out.append({"key": cs, "label": st["label"], "desc": st["note"], "count": len(rows),
                    "style": st, "rows": rows})
    if status is not None:
        unknown = set(status.dropna()) - set(config.COUNTY_STATUS_ORDER)
        assert not unknown, f"county statuses with no map style: {unknown}"
    return out


def datacenter_entries(dcs):
    """Existing data centers (context layer); empty when the Atlas isn't downloaded."""
    if dcs is None:
        return []
    label, desc = config.DATACENTER_LEGEND
    return [{"key": "datacenter", "label": label, "desc": desc, "count": len(dcs), "rows": dcs}]
