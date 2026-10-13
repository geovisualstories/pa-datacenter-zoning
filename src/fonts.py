"""Barlow Condensed (SIL OFL) for the static maps: fetched once into fonts/, registered with matplotlib."""
import urllib.request
from matplotlib import font_manager
from . import config

FAMILY = "Barlow Condensed"
BASE = "https://github.com/google/fonts/raw/main/ofl/barlowcondensed/"
FILES = ["BarlowCondensed-Regular.ttf", "BarlowCondensed-Medium.ttf",
         "BarlowCondensed-SemiBold.ttf", "BarlowCondensed-Bold.ttf", "OFL.txt"]
FONTS = config.ROOT / "fonts"


def register():
    """-> FAMILY if available, else None (matplotlib's default sans is used)."""
    FONTS.mkdir(exist_ok=True)
    try:
        for f in FILES:
            if not (FONTS / f).exists():
                print(f"Downloading {f} ...")
                urllib.request.urlretrieve(BASE + f, FONTS / f)
    except OSError as e:
        print(f"Font download failed ({e}); using default font")
    ttfs = sorted(FONTS.glob("*.ttf"))
    for p in ttfs:
        font_manager.fontManager.addfont(str(p))
    return FAMILY if ttfs else None
