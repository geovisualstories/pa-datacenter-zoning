"""Load the ordinance spreadsheet and standardize it for joining + mapping."""
import re
import pandas as pd
from . import config

TYPE_WORDS = ("township", "borough", "city", "town")


def classify_status(raw: str) -> str:
    """Collapse free-text status into 3 map categories.

    Precedence: anything adopted -> Adopted; else any moratorium -> Moratorium;
    else proposed / draft / curative process / review -> Proposed / Under Review.
    """
    s = str(raw).lower()
    if "adopted" in s:
        return "Adopted"
    if "moratorium" in s:
        return "Moratorium"
    return "Proposed / Under Review"


def parse_year(raw) -> str:
    """Pull a display year (or range) out of the messy date column."""
    if pd.isna(raw):
        return "n/d"
    if hasattr(raw, "year"):
        return str(raw.year)
    years = sorted(set(re.findall(r"20\d\d", str(raw))))
    if not years:
        return "n/d"
    return f"{years[0]}–{years[-1]}" if len(years) > 1 else years[0]


def split_name(name: str):
    """'Adams Township' -> ('adams', 'township'); 'Allentown' -> ('allentown', None)."""
    n = re.sub(r"\s+", " ", str(name).strip().lower())
    for t in TYPE_WORDS:
        if n.endswith(" " + t):
            return n[: -len(t) - 1].strip(), t
    return n, None


def load_municipal() -> pd.DataFrame:
    df = pd.read_excel(config.ORDINANCE_XLSX, sheet_name=config.MUNI_SHEET)
    df.columns = ["municipality", "county", "status_raw", "action_date", "source"]
    df["municipality"] = df["municipality"].str.strip()
    df["county"] = df["county"].str.strip()
    df["status"] = df["status_raw"].map(classify_status)
    df["year"] = df["action_date"].map(parse_year)
    df["action_date"] = (df["action_date"].astype(str)
                         .str.replace(" 00:00:00", "", regex=False).replace("nan", "n/d"))
    parts = df["municipality"].map(split_name)
    df["base_name"] = parts.str[0]
    df["muni_type"] = parts.str[1]
    df["county_key"] = df["county"].str.lower()
    return df


def load_county() -> pd.DataFrame:
    df = pd.read_excel(config.ORDINANCE_XLSX, sheet_name=config.COUNTY_SHEET)
    df.columns = ["county", "status_raw", "action_date", "source"]
    df["county_key"] = df["county"].str.replace(" County", "", regex=False).str.strip().str.lower()
    df["county_status"] = df["status_raw"].str.strip().str.title()
    df["action_date"] = df["action_date"].astype(str).str.replace(" 00:00:00", "", regex=False)
    return df


if __name__ == "__main__":
    m = load_municipal()
    print(m[["municipality", "county", "status", "year"]].to_string())
    print("\n", m["status"].value_counts())
    print("\nCounties w/ municipal activity:", m["county"].nunique())
    print("\n", load_county()[["county", "county_status"]])
