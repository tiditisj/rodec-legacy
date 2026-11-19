#!/usr/bin/env python3
"""
Build web assets for legacy.rodec.com from the Rodec legacy archive on Google Drive.

Reads the raw archive (photos, scans, manuals, the product history spreadsheet),
writes optimised images and PDFs into public/media + public/docs, and writes the
data files the Astro site is generated from into src/data/generated/.

Re-run whenever the archive changes:

    .venv/bin/python scripts/build_assets.py            # incremental
    .venv/bin/python scripts/build_assets.py --force    # rebuild every file

The archive location can be overridden with RODEC_ARCHIVE=/path/to/ZZ_Legacy.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import xlrd
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter

import box_scans

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = Path(os.environ.get(
    "RODEC_ARCHIVE",
    Path.home() / "Library/CloudStorage/GoogleDrive-tdr@tdr.be/My Drive/TDR/Rodec/DAM/Product/ZZ_Legacy",
))
TRANSTEL = ARCHIVE / "RODEC_from transtel"
INFO = TRANSTEL / "RODEC Info + history + boek"
MANUALS = ARCHIVE / "RODEC Manuals + schemas"
# Photos found online and approved by hand: one subfolder per model (folder name = model name),
# each with a SOURCES.md recording where every image came from.
WEB_APPROVED = ARCHIVE / "_Web fotos (goedgekeurd)"
# The 2010 "55 years" catalogue (history + full product range) lives in the Marketing folder.
CATALOGUE = Path(os.environ.get("RODEC_CATALOGUE", ARCHIVE.parent.parent / "Marketing/history/rodec_history.pdf"))
# Scans of the paper archive boxes (doos1, doos2, ...); contents are listed in box_scans.py.
BOXES = ARCHIVE / "Rodec archiefdozen"
CACHE = Path(__file__).resolve().parent.parent / ".cache"

PUBLIC = ROOT / "public"
MEDIA = PUBLIC / "media"
DOCS = PUBLIC / "docs"
DATA = ROOT / "src" / "data" / "generated"

FORCE = "--force" in sys.argv
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
MONTHS["januari"] = 1

warnings: list[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)
    print("  ! " + msg)


# ---------------------------------------------------------------- helpers

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


def canon(s: str) -> str:
    """Lowercase, unify MK suffixes, keep separators (used for prefix matching)."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"mk\s*iii", "mk3", s)
    s = re.sub(r"mk\s*ii", "mk2", s)
    s = re.sub(r"%20", " ", s)
    return s


def alias_regex(alias: str) -> re.Pattern:
    chars = [re.escape(c) for c in re.sub(r"[^a-z0-9]", "", canon(alias))]
    return re.compile(r"^" + r"[\s\-_.]*".join(chars) + r"(?![0-9])")


def stale(src: Path, dst: Path) -> bool:
    return FORCE or not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime


def readable(src: Path) -> Path:
    """Some archive photos (e.g. the Boy George shots) are old-style JPEG-in-TIFF files with a
    .jpg name and a wrong tile byte count, so every reader stops after a few lines. Patch the
    byte count in a cached copy and decode it with libtiff's tiff2rgba."""
    with Image.open(src) as im:
        if not (im.format == "TIFF" and im.info.get("compression") == "tiff_jpeg"):
            return src
    base = CACHE / "converted" / slugify(str(src.relative_to(ARCHIVE.parent)))
    out = base.with_suffix(".rgba.tif")
    if FORCE or not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        import struct
        out.parent.mkdir(parents=True, exist_ok=True)
        b = bytearray(src.read_bytes())
        fmt = "<" if b[:2] == b"II" else ">"
        ifd = struct.unpack_from(fmt + "I", b, 4)[0]
        tags = {}
        for i in range(struct.unpack_from(fmt + "H", b, ifd)[0]):
            e = ifd + 2 + 12 * i
            tag, _typ, count, val = struct.unpack_from(fmt + "HHII", b, e)
            tags[tag] = (e, count, val)
        data_tag, count_tag = (324, 325) if 324 in tags else (273, 279)
        if data_tag in tags and tags[data_tag][1] == 1:  # single tile/strip: data runs to end of file
            struct.pack_into(fmt + "I", b, tags[count_tag][0] + 8, len(b) - tags[data_tag][2])
        fixed = base.with_suffix(".fixed.tif")
        fixed.write_bytes(bytes(b))
        os.system(f'tiff2rgba "{fixed}" "{out}" >/dev/null 2>&1')
        fixed.unlink(missing_ok=True)
    if not out.exists():
        warn(f"could not decode {src.name}")
        return src
    return out


def autotrim(im: Image.Image, margin: float = 0.05) -> Image.Image:
    """Product shots on a plain light background: crop to the product, then add an even margin
    so every unit sits centred in its card. Photos without a plain light border are left alone."""
    from PIL import ImageChops, ImageStat
    rgb = im.convert("RGB")
    w, h = rgb.size
    k = max(2, min(w, h) // 50)
    border = [rgb.crop(b) for b in ((0, 0, w, k), (0, h - k, w, h), (0, 0, k, h), (w - k, 0, w, h))]
    stats = [ImageStat.Stat(b) for b in border]
    # Background = the brightest uniform border strip (products often touch one or two edges).
    plain = [(st.mean, st.stddev) for st in stats if min(st.mean) > 215 and max(st.stddev) < 12]
    if len(plain) < 2:
        return im
    bg = tuple(int(sum(m[i] for m, _ in plain) / len(plain)) for i in range(3))
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).convert("L")
    bbox = diff.point(lambda v: 255 if v > 22 else 0).getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    if (x1 - x0) * (y1 - y0) > 0.97 * w * h:  # nothing to trim
        return im
    pad = int(max(x1 - x0, y1 - y0) * margin)
    out = Image.new("RGB", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), bg)
    out.paste(rgb.crop(bbox), (pad, pad))
    return out


# Studio prints scanned with their dark film edge: shown cut out on plain white instead.
ON_WHITE = {"MX18 Front slanted BW", "MX18 Back BW", "MX180 Black Front slanted BW", "MX180 Back BW"}


def on_white(im: Image.Image, margin: float = 0.06) -> Image.Image:
    """Cut the dark film edge away, lift the grey studio backdrop to pure white and centre the
    product on a white canvas."""
    from PIL import ImageDraw, ImageFilter
    rgb = im.convert("RGB")
    g = rgb.convert("L")
    w, h = g.size
    px = g.load()

    def mean(coords):
        vals = [px[x, y] for x, y in coords]
        return sum(vals) / len(vals)

    def edge(line, limit):  # first line in from the edge that shows the light backdrop
        for i in range(int(limit)):
            if line(i) > 200:
                return i
        return 0

    xs = range(0, w, 4)
    top = edge(lambda i: mean([(x, i) for x in xs]), h * .35)
    bot = edge(lambda i: mean([(x, h - 1 - i) for x in xs]), h * .35)
    ys = range(top, h - bot, 4)
    left = edge(lambda i: mean([(i, y) for y in ys]), w * .35)
    right = edge(lambda i: mean([(w - 1 - i, y) for y in ys]), w * .35)
    inset = max(4, min(w, h) // 150)
    rgb = rgb.crop((left + (inset if left else 0), top + (inset if top else 0),
                    w - right - (inset if right else 0), h - bot - (inset if bot else 0)))
    g = rgb.convert("L")
    w, h = g.size

    # lift the backdrop to white with a highlight-only curve (product tones stay as they are)
    k = max(2, min(w, h) // 60)
    border = sorted(v for b in ((0, 0, w, k), (0, h - k, w, h)) for v in g.crop(b).getdata())
    bg = border[len(border) // 2]
    lo = bg - 30
    lut = [v if v <= lo else min(255, round(lo + (v - lo) * (255 - lo) / max(1, bg - 8 - lo))) for v in range(256)]
    rgb = rgb.point(lut * 3)

    # flood the backdrop from the edges so vignetting and soft shadows go white too
    mask = rgb.convert("L").point(lambda v: 255 if v >= 238 else 0)
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1)):
        if mask.getpixel(seed) == 255:
            ImageDraw.floodfill(mask, seed, 128)
    bgmask = mask.point(lambda v: 255 if v == 128 else 0).filter(ImageFilter.GaussianBlur(1.2))
    rgb = Image.composite(Image.new("RGB", rgb.size, (255, 255, 255)), rgb, bgmask)

    bbox = rgb.convert("L").point(lambda v: 255 if v < 245 else 0).filter(ImageFilter.MedianFilter(5)).getbbox()
    if not bbox:
        return rgb
    x0, y0, x1, y1 = bbox
    pad = int(max(x1 - x0, y1 - y0) * margin)
    out = Image.new("RGB", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (255, 255, 255))
    out.paste(rgb.crop(bbox), (pad, pad))
    return out


def to_webp(src: Path, dst: Path, max_side: int, quality: int = 80, trim: bool = False,
            white: bool = False) -> tuple[int, int]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not stale(src, dst):
        with Image.open(dst) as im:
            return im.size
    src = readable(src)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("1", "L", "P", "LA", "I;16", "I", "CMYK"):
            im = im.convert("RGBA" if "A" in im.mode or im.mode == "P" else "RGB")
        if white:
            im = on_white(im)
        elif trim:
            im = autotrim(im)
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        im.save(dst, "WEBP", quality=quality, method=5)
        return im.size


@dataclass
class Img:
    src: Path
    key: str  # output path below /media without extension
    alt: str
    caption: str = ""
    full: int = 1800
    thumb: int = 640
    trim: bool = False
    white: bool = False  # cut out on plain white (see ON_WHITE)

    def build(self) -> dict:
        if self.trim is None:
            self.trim = False
        trim = self.trim or self.key.startswith("models/")
        w, h = to_webp(self.src, MEDIA / f"{self.key}.webp", self.full, trim=trim, white=self.white)
        to_webp(self.src, MEDIA / f"{self.key}.thumb.webp", self.thumb, 74, trim=trim, white=self.white)
        out = {"src": f"/media/{self.key}.webp", "thumb": f"/media/{self.key}.thumb.webp",
               "w": w, "h": h, "alt": self.alt}
        if self.caption:
            out["caption"] = self.caption
        return out


def ahash(path: Path) -> int:
    with Image.open(path) as im:
        px = list(im.convert("L").resize((16, 16)).getdata())
    avg = sum(px) / len(px)
    return sum(1 << i for i, v in enumerate(px) if v > avg)


def dedupe(items: list[dict], prefer: list[str] = (), threshold: int = 12) -> list[dict]:
    """Drop near-identical photos (re-scans, colour/BW variants). Keeps the first in order,
    unless a later copy's caption matches one of `prefer`; position follows the first copy."""
    kept: list[tuple[int, dict]] = []
    for it in items:
        h = ahash(PUBLIC / it["thumb"].lstrip("/"))
        dup = next((k for k, (kh, _) in enumerate(kept) if bin(kh ^ h).count("1") <= threshold), None)
        if dup is None:
            kept.append((h, it))
        elif any(re.search(pat, it.get("caption", it["alt"]), re.I) for pat in prefer):
            kept[dup] = (kept[dup][0], it)
    return [it for _, it in kept]


def images_in(folder: Path, recursive: bool = False) -> list[Path]:
    if not folder.exists():
        warn(f"missing folder {folder.relative_to(ARCHIVE)}")
        return []
    it = folder.rglob("*") if recursive else folder.iterdir()
    files = [p for p in it if p.is_file() and p.suffix.lower() in IMAGE_EXT and not p.name.startswith(".")]
    # Drop BMP/TIF if a JPG with the same stem exists (scanner duplicates).
    stems = {p.stem.lower() for p in files if p.suffix.lower() in (".jpg", ".jpeg")}
    files = [p for p in files if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif") or p.stem.lower() not in stems]
    return sorted(files, key=lambda p: natural_key(p.name))


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def page_group(stem: str) -> tuple[str, int]:
    """'MX18 - 002' -> ('MX18', 2); 'SONO - FEB 2005 - 001' -> ('SONO - FEB 2005', 1)."""
    m = re.match(r"^(.*?)[\s\-_]*-\s*(\d{3})$|^(.*?)\s+(\d{3})$|^(.*?)\s*-(\d{3})$", stem)
    if m:
        g = [x for x in m.groups() if x is not None]
        return g[0].strip(" -"), int(g[1])
    return stem.strip(), 0


# ---------------------------------------------------------------- models

TYPE_FIX = {"Audiofan": "Amplifier", "PA800": "Amplifier", "PA1600": "Amplifier", "PA2400": "Amplifier"}
NAME_FIX = {"HD450SL": "HDA450SL", "1572.0": "1572", "1372.0": "1372", "2560.0": "2560",
            "1362.0": "1362", "1385.0": "1385"}
EXTRA_ALIASES = {
    "disco-mix": ["discomix", "disco mix"],
    "disco-max": ["discomax", "disco max"],
    "olympus-olympus2": ["olympus", "olympus 2"],
    "hda450sl": ["hda450 sl", "hda450sl"],
    "discotech-285a": ["discotech w285", "discotech 285"],
    "red-baron": ["red baron"],
    "mx180-limited-edition": ["mx180 50th", "mx180 50th anniversary", "mx180 limited 50"],
    "mx180-limited-1996": ["mx180 limited", "mx180 red limited", "mx180 limited edition red"],
    "multi-source-ii": ["multisource", "multi source"],
    "mixbox": ["mixbox mk1", "mixbox"],
    "power-project-100": ["power project 100"],
    "cu880": ["cu 880"], "cu881": ["cu 881"], "cu882": ["cu 882"], "cu888": ["cu 888"],
    "b840sta": ["b 840 sta", "b840sta"],
    "fader": ["fader", "the fader"],
    "auditorium": ["auditorium"],
    "mixus-103": ["mixus"],
    "donalbi-pam-100": ["donalbi pam"],
    "donalbi-alpha-centauri": ["donalbi alpha"],
}
# Models that appear in "Old RODEC's.xls" or the photo archive but not in the history sheet.
EXTRA_MODELS = [
    {"name": "Auditorium", "type": "Amplifier", "year": 1965, "approx": True,
     "after": "615SMA", "note": "Valve amplifier from the 1960s. It is not in the official product list, but survives in colour photos inside and out."},
    {"name": "MX180 Limited (1996)", "slug": "mx180-limited-1996", "type": "Mixer", "year": 1996, "month": 5,
     "after": "MX230", "note": "Red limited run of the MX180, built with the original rack handles."},
    {"name": "Donalbi PAM 100", "type": "Amplifier", "year": None, "approx": True, "after": "RED BARON",
     "note": "Donalbi-branded amplifier kept in the Rodec photo archive."},
    {"name": "Donalbi Alpha Centauri", "type": "Mixer", "year": None, "approx": True, "after": "Donalbi PAM 100",
     "note": "Donalbi-branded mixer kept in the Rodec photo archive."},
    {"name": "Mixus 103", "type": "Mixer", "year": None, "approx": True, "after": "Donalbi Alpha Centauri",
     "curiosity": True, "note": "Not a Rodec at all. This is a counterfeit built in Canada, and the best proof the brand was worth copying."},
]

CATEGORY = {
    "mixer": "Mixers", "microphone mixer": "Mixers", "mixer - pre amplifier": "Mixers",
    "amplifier": "Amplifiers", "pre amplifier": "Amplifiers", "phono pre amplifier": "Amplifiers",
    "tuner": "Tuners", "loudspeaker box": "Speakers",
    "quickstart": "Tools", "level controller": "Tools", "filterbank": "Tools", "patchbay": "Tools",
}

ERAS = [
    (1954, 1969, "radio", "The radio shop years"),
    (1970, 1976, "fader", "Birth of the DJ mixer"),
    (1977, 1985, "sound-machines", "Sound Machines"),
    (1986, 1998, "mx", "The MX legend"),
    (1999, 2007, "mk3", "MKIII & beyond"),
    (2008, 2014, "progressive", "Progressive & Original"),
]

SERIES = [
    (r"^MX(1400|1800|2200|3000)$", "Progressive series"),
    (r"Original$", "Original series"),
    (r"MKIII$", "MKIII series"),
    (r"^PA\d+", "PA amplifiers"),
    (r"^BX", "BX series"),
    (r"^CU8", "CU series"),
    (r"^13[67]\d", "13xx series"),
    (r"^(HDA|HD)\d", "HDA amplifiers"),
    (r"^SM\d", "SM series"),
    (r"^POWER PROJECT", "Power Project"),
]


def era_for(year: int | None) -> dict:
    for a, b, key, title in ERAS:
        if year is not None and a <= year <= b:
            return {"key": key, "title": title, "from": a, "to": b}
    return {"key": "radio", "title": ERAS[0][3], "from": ERAS[0][0], "to": ERAS[0][1]}


def load_models() -> list[dict]:
    path = ARCHIVE / "RODEC Toestellen history.xls"
    sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)
    rows = []
    for r in range(1, sheet.nrows):
        raw = str(sheet.cell_value(r, 1)).strip()
        if not raw or raw.lower() in ("missing information", "current range"):
            continue
        name = NAME_FIX.get(raw, raw.removesuffix(".0"))
        typ = str(sheet.cell_value(r, 2)).strip() or None
        month = str(sheet.cell_value(r, 3)).strip().lower()
        year = sheet.cell_value(r, 4)
        info = str(sheet.cell_value(r, 5)).strip() or None
        price = sheet.cell_value(r, 6)
        rows.append({
            "name": name,
            "type": TYPE_FIX.get(name, typ),
            "month": MONTHS.get(month),
            "year": int(year) if year else None,
            "approx": not bool(year),
            "launchDoc": info,
            "price": float(price) if price not in ("", None) else None,
        })
    # Insert extras after their anchor model.
    for extra in EXTRA_MODELS:
        idx = next((i for i, m in enumerate(rows) if m["name"] == extra["after"]), len(rows) - 1)
        rows.insert(idx + 1, {"name": extra["name"], "type": extra["type"], "month": extra.get("month"),
                              "year": extra["year"], "approx": extra.get("approx", False), "launchDoc": None,
                              "price": None, "extra": True, "curiosity": extra.get("curiosity", False),
                              "note": extra["note"], "slug": extra.get("slug")})
    # Unknown years inherit the previous known year in sheet order (the sheet is chronological).
    last = 1961
    for m in rows:
        if m["year"] is None:
            m["year"] = last
            m["approx"] = True
        else:
            last = m["year"]
    # The CU / FADER generation predates September 1970 (Old RODEC's.xls).
    for m in rows:
        if m["name"] in ("CU880", "CU881", "CU882", "CU888", "B840STA", "FADER"):
            m["year"], m["approx"] = 1970, True
    for i, m in enumerate(rows):
        m["slug"] = m.get("slug") or slugify(m["name"].replace(" / ", " "))
        m["order"] = i
        m["category"] = CATEGORY.get((m["type"] or "").lower(), "Other")
        m["era"] = era_for(m["year"])
        m["series"] = next((s for pat, s in SERIES if re.search(pat, m["name"])), None)
        m["aliases"] = [a.strip() for a in m["name"].split("/")] + EXTRA_ALIASES.get(m["slug"], [])
        m.update({"photos": [], "brochures": [], "docs": []})
    return rows


def matcher(models: list[dict]):
    table = []
    for m in models:
        for a in m["aliases"]:
            table.append((len(re.sub(r"[^a-z0-9]", "", canon(a))), alias_regex(a), m))
    table.sort(key=lambda t: -t[0])

    def match(name: str):
        s = canon(name)
        s = re.sub(r"^(the|rodec|schema|add|advertentie|leaflet)[\s\-_.]+", "", s)
        for _, rx, m in table:
            if rx.match(s):
                return m
        return None
    return match


# ---------------------------------------------------------------- documents

@dataclass
class Doc:
    id: str
    title: str
    kind: str  # user | service | schematic | leaflet | drawing | catalogue | book
    models: list[str]
    sources: list[str]  # paths relative to ARCHIVE; globs allowed
    note: str = ""
    pages: int = 0
    size: int = 0
    cover: dict | None = None
    missing: bool = False
    max_px: int = 2400  # longest side for image-based pages


M = "RODEC Manuals + schemas/"
T = "RODEC_from transtel/RODEC Manuals + schema's/"
L = "RODEC_from transtel/RODEC Info + history + boek/RODEC Ads + reviews + leaflets/"
PROG = ["mx1400", "mx1800", "mx2200", "mx3000"]
# Images embedded in the 2010 catalogue, as written by `pdfimages -f 4 -l 30 -png -p`
# (file stem "i-<page>-<num>"). Mapped to models that have few or no other photos.
CATALOGUE_IMAGES = {
    "mx3000": ["i-008-037", "i-009-041"],
    "mx2200": ["i-010-045", "i-011-050", "i-011-051"],
    "mx1800": ["i-012-053", "i-013-059"],
    "mx1400": ["i-014-061", "i-015-066", "i-015-067"],
    "mx180-original": ["i-018-072", "i-019-075", "i-019-077"],
    "bx14-original": ["i-020-081", "i-021-083"],
    "bx9-original": ["i-022-087", "i-023-091", "i-023-092"],
    "scratchbox": ["i-024-096"],
    "restyler": ["i-026-104", "i-027-106", "i-027-105", "i-027-107"],
    "patch-live": ["i-028-1025", "i-029-1028", "i-029-1026", "i-028-112"],
}
CATALOGUE_HISTORY = [
    ("i-004-005", "Early Rodec photos, from the 2010 catalogue"),
    ("i-005-016", "Valve era and the first Rodec Sound Machines sticker"),
    ("i-005-014", "Mixfan folder, the Mixetta at Double Dutch and an early business card"),
    ("i-006-023", "25th anniversary (1979): Disco-Mix, Disco-Max and the dealer shows"),
    ("i-006-025", "Disco-Mix and Disco-Max reviews, Denmark 1981"),
    ("i-007-032", "From MX18 to MX180 Original: the MX success story"),
    ("i-007-034", "MX18 promotion in Korea, 1987"),
]

DOC_LIST = [
    # --- vintage
    Doc("1385-manual", "1385 manual", "service", ["1385"], [M + "1385 manual/Rodec 1385 manual.*.pdf"]),
    Doc("mixfan-schematic", "Mixfan schematic", "schematic", ["mixfan"], [M + "Mixfan schema.jpg"]),
    Doc("discomix-schematic", "Disco-Mix schematic", "schematic", ["disco-mix"], [M + "Discomix schema.jpg"]),
    Doc("discomax-service", "Disco-Max service manual", "service", ["disco-max"], [M + "Discomax/Discomax service manual p*.pdf"]),
    Doc("hda340-service", "HDA340 / Disco-Max service manual", "service", ["hda340", "disco-max"], [M + "HDA340/*.jpg"]),
    Doc("sm200-service", "SM200 service manual", "service", ["sm200"], [M + "SM200 Service manual scanned.pdf"]),
    Doc("sm300-service", "SM300 service manual", "service", ["sm300"], [M + "SM300/SM300 Service manual p*.jpg"]),
    Doc("sm300-user", "SM300 user manual", "user", ["sm300"], [M + "SM300/SM300 User manual p*.jpg"]),
    Doc("hda450sl-service", "HDA450SL service manual", "service", ["hda450sl"], [M + "HDA450SL manual/HDA450sl service manual p*.jpg"]),
    Doc("hda450sl-user", "HDA450SL user manual", "user", ["hda450sl"], [M + "HDA450SL manual/HDA450sl user manual p*.jpg"]),
    # --- MX era
    Doc("mx10-mx100-service", "MX10 / MX100 service manual", "service", ["mx10", "mx100"], [M + "Rodec MX 10 - 100 service manual.pdf"]),
    Doc("mx18-mx180-mx34-service", "MX18 / MX180 / MX180 MKII / MX34 service manual", "service",
        ["mx18", "mx180", "mx180-mkii", "mx34"], [M + "Service manual MX18-MX180-MX180MKII-MX34.pdf"]),
    Doc("mx130-manual", "MX130 manual & schematics", "service", ["mx130"], [T + "Schema + manual  MX130/*.pdf", M + "MX 130-230/Schema + manual  MX130/*.pdf"]),
    Doc("mx230-user", "MX230 user manual", "user", ["mx230"], [M + "MX 130-230/MX230USE.pdf", T + "MX230USE.pdf"]),
    Doc("mx180-mkii-user", "MX180 MKII user manual", "user", ["mx180-mkii"], [M + "Mx180 MKII use.pdf"]),
    Doc("mx120-mx126-user", "MX120 / MX126 user manual", "user", ["mx120", "mx126"], [M + "MX120_126 use.pdf"]),
    # --- MKIII & 2000s
    Doc("mx180-mkiii-user", "MX180 MKIII user manual", "user", ["mx180-mkiii"], [M + "Mx180 MKIII use.pdf"]),
    Doc("mx240-mkiii-user", "MX240 MKIII user manual", "user", ["mx240-mkiii"], [M + "Mx240 MKIII use.pdf"]),
    Doc("mx300-mkiii-user", "MX300 MKIII user manual", "user", ["mx300-mkiii"], [M + "Mx300 MKIII use.pdf"]),
    Doc("mkiii-service", "MX180 / MX240 / MX300 MKIII service manual", "service",
        ["mx180-mkiii", "mx240-mkiii", "mx300-mkiii"], [M + "Service manual MX180 MKIII MX240 MKIII scanned 1.pdf"]),
    Doc("alc-01-user", "ALC-01 user manual", "user", ["alc-01"], [M + "ALC-01 use.pdf"]),
    Doc("multi-source-ii-user", "Multi Source II user manual", "user", ["multi-source-ii"], [M + "MultiSource II use.pdf"]),
    Doc("mixbox-user", "miXboX user manual", "user", ["mixbox"], [M + "miXboX use.pdf"]),
    Doc("mixbox-mkii-user", "miXboX MKII user manual", "user", ["mixbox-mkii"], [M + "miXboX MKII use.pdf"]),
    Doc("cx-1100-user", "CX-1100 user manual", "user", ["cx-1100"], [M + "CX-1100 use.pdf"]),
    Doc("cx-1100-schematic", "CX-1100 schematics (incl. balanced XLR output)", "schematic", ["cx-1100"], [M + "schema CX1100 + XLR Symm output V2.pdf"]),
    Doc("bx-user", "BX-9 / BX-14 user manual", "user", ["bx-9", "bx-14"], [M + "BX-9 BX-14 use.pdf"]),
    Doc("bx-service", "BX-9 / BX-14 service manual", "service", ["bx-9", "bx-14", "bx9-original", "bx14-original"], [M + "Service manual BX-9 & 14.pdf"]),
    Doc("pa-user", "PA800 / PA1600 / PA2400 user manual", "user", ["pa800", "pa1600", "pa2400"], [M + "PA800 PA1600 PA2400 use.pdf"]),
    Doc("mx180-limited-user", "MX180 50th Anniversary user manual", "user", ["mx180-limited-edition"], [M + "Mx180 50th anniversary use.pdf"]),
    Doc("mx180-limited-frontplate", "MX180 50th Anniversary front panel drawings", "drawing", ["mx180-limited-edition"],
        [M + "tekening front mx180 limited 50y/*.png", M + "tekening front mx180 limited 50y/*.PNG"]),
    Doc("scratchbox-schematic", "Scratchbox schematic (preliminary)", "schematic", ["scratchbox"], [M + "Schema Scratchbox (onder voorbehoud).pdf"]),
    Doc("scratchbox-xlr", "Scratchbox XLR output option", "schematic", ["scratchbox"], ["Scratchbox/XLR option.png"]),
    # --- Progressive & Original
    Doc("mx00-service", "Progressive series service manual (MX00: MX1400 / MX1800 / MX2200 / MX3000)", "service", PROG, [M + "Service manual MX00 series V1_0L Progressive.pdf"]),
    Doc("mx00-modification", "Progressive series modification notes (MX00: MX1400 / MX1800 / MX2200 / MX3000)", "service", PROG, [M + "Modificatie MX00 serie.pdf"]),
    Doc("mx180-original-service", "MX180 Original service manual", "service", ["mx180-original"], [M + "Service manual MX180 Limited Original.pdf"]),
    Doc("mx180-original-user", "MX180 Original user manual", "user", ["mx180-original"], [M + "User manual MX180 original V2.pdf"]),
    Doc("bx9-original-user", "BX9 Original user manual", "user", ["bx9-original"], [M + "User manual BX9 original V1.pdf"]),
    Doc("bx14-original-user", "BX14 Original user manual", "user", ["bx14-original"], [M + "User manual BX14 original V1.doc.pdf"]),
    # --- original leaflets (PDF)
    Doc("mx180-mkiii-leaflet", "MX180 MKIII leaflet", "leaflet", ["mx180-mkiii"], [L + "Leaflet MX180MKIII.pdf"]),
    Doc("mx240-mkiii-leaflet", "MX240 MKIII leaflet", "leaflet", ["mx240-mkiii"], [L + "mx240k3.pdf"]),
    Doc("mx300-mkiii-leaflet", "MX300 MKIII leaflet", "leaflet", ["mx300-mkiii"], [L + "mx300mk3.pdf"]),
    Doc("alc-01-leaflet", "ALC-01 leaflet", "leaflet", ["alc-01"], [L + "Leaflet%20ALC01.pdf"]),
    Doc("multi-source-ii-leaflet", "Multi Source II leaflet", "leaflet", ["multi-source-ii"], [L + "Multi Source II folder.pdf"]),
    Doc("mixbox-leaflet", "miXboX leaflet", "leaflet", ["mixbox"], [L + "mixbox.pdf"]),
    Doc("cx-1100-leaflet", "CX-1100 leaflet", "leaflet", ["cx-1100"], [L + "cx1100.pdf"]),
    Doc("bx-9-leaflet", "BX-9 leaflet", "leaflet", ["bx-9"], [L + "bx9.pdf"]),
    Doc("bx-14-leaflet", "BX-14 leaflet", "leaflet", ["bx-14"], [L + "bx14.pdf"]),
    # --- 2004 book
    Doc("book-50-years", "Perpetual Music Makers: Rodec 50 years book (2004)", "book", [],
        ["RODEC_from transtel/RODEC Info + history + boek/RODEC Boek/RODEC Boek/RO-*.jpg"], max_px=1754),
    # --- 2010 catalogue
    Doc("catalogue-2010", "Rodec catalogue 2010: 55 years of passion", "catalogue",
        PROG + ["mx180-original", "bx9-original", "bx14-original", "scratchbox", "restyler", "patch-live"],
        [str(CATALOGUE)]),
]
DOC_LIST += [Doc(i, t, k, ms, [f"box:{s}" for s in stems]) for i, t, k, ms, stems in box_scans.DOCS]


def box_src(stem: str, crop: tuple | None = None, rotate: int = 0) -> Path:
    """A scan from the archive boxes, levelled (the scans come out grey) and optionally cropped,
    cached as a JPEG so the rest of the pipeline can treat it like any other image."""
    hits = sorted(BOXES.glob(f"doos*/{stem}.jpg"))
    if not hits:
        raise FileNotFoundError(f"box scan {stem} not found")
    src = hits[0]
    tag = f"-{'-'.join(map(str, crop))}" if crop else ""
    out = CACHE / "boxes" / f"{slugify(stem) or 'scan'}{tag}.jpg"
    if FORCE or not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            if crop:
                im = im.crop(crop)
            if rotate:
                im = im.rotate(rotate, expand=True)
            im = ImageOps.autocontrast(im, cutoff=(0.3, 1.5), preserve_tone=True)
            im.thumbnail((3200, 3200), Image.LANCZOS)
            im.save(out, "JPEG", quality=90)
    return out


def resolve(patterns: list[str]) -> list[Path]:
    if patterns and all(p.startswith("box:") for p in patterns):
        return [box_src(p[4:]) for p in patterns]
    for pat in patterns:  # first pattern that yields files wins (fallback copies)
        if pat.startswith("/"):
            if Path(pat).is_file():
                return [Path(pat)]
            continue
        files = sorted((p for p in ARCHIVE.glob(pat) if p.is_file()), key=lambda p: natural_key(p.name))
        if files:
            return files
    return []


def build_doc(doc: Doc) -> None:
    files = resolve(doc.sources)
    if not files:
        warn(f"doc {doc.id}: no source found")
        doc.missing = True
        return
    out = DOCS / f"rodec-{doc.id}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    newest = max(f.stat().st_mtime for f in files)
    if FORCE or not out.exists() or out.stat().st_mtime < newest:
        if all(f.suffix.lower() == ".pdf" for f in files):
            if len(files) == 1:
                out.write_bytes(files[0].read_bytes())
            else:
                w = PdfWriter()
                for f in files:
                    w.append(str(f))
                with open(out, "wb") as fh:
                    w.write(fh)
        else:  # scanned page images -> one PDF, built page by page to keep memory low
            import io
            w = PdfWriter()
            for f in files:
                im = Image.open(f)
                im = ImageOps.exif_transpose(im)
                if im.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", im.size, "white")
                    im = im.convert("RGBA")
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                im = im.convert("RGB")
                im.thumbnail((doc.max_px * 17 // 24, doc.max_px), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "PDF", resolution=150 if doc.max_px < 2400 else 200, quality=70)
                im.close()
                w.append(PdfReader(io.BytesIO(buf.getvalue())))
            with open(out, "wb") as fh:
                w.write(fh)
    doc.pages = len(PdfReader(str(out)).pages)
    doc.size = out.stat().st_size
    # cover thumbnail
    cover = MEDIA / "docs" / f"{doc.id}.webp"
    if FORCE or not cover.exists() or cover.stat().st_mtime < out.stat().st_mtime:
        cover.parent.mkdir(parents=True, exist_ok=True)
        tmp = cover.with_suffix("")
        os.system(f'pdftoppm -f 1 -l 1 -r 60 -png -singlefile "{out}" "{tmp}" >/dev/null 2>&1')
        png = tmp.with_suffix(".png")
        if png.exists():
            to_webp(png, cover, 520, 72)
            png.unlink()
    if cover.exists():
        with Image.open(cover) as im:
            doc.cover = {"src": f"/media/docs/{doc.id}.webp", "w": im.width, "h": im.height}


# ---------------------------------------------------------------- main

def main() -> None:
    if not ARCHIVE.exists():
        sys.exit(f"Archive not found: {ARCHIVE}")
    print(f"Archive: {ARCHIVE}")
    models = load_models()
    by_slug = {m["slug"]: m for m in models}
    match = matcher(models)

    # ---- product photos
    print("Product photos …")
    old = TRANSTEL / "RODEC Mixers" / "Old Rodec mixers"
    unmatched_photos = []
    for p in images_in(old):
        if re.match(r"(?i)^(unknown|rodec radio shop|rodec 1972)", p.stem):
            unmatched_photos.append(p)
            continue
        m = match(p.stem)
        if not m:
            warn(f"photo without model: {p.name}")
            unmatched_photos.append(p)
            continue
        m["photos"].append((p, p.stem))
    folder_map = {
        "MX series/MX120": "mx120", "MX series/MX126": "mx126", "MX series/MX180 MKII": "mx180-mkii",
        "MX series/MX180 MKIII": "mx180-mkiii", "MX series/MX240": "mx240", "MX series/MX240 MKIII": "mx240-mkiii",
        "MX series/MX300 MKIII": "mx300-mkiii", "MX series/MX34": "mx34", "MixBox/MIXBOX": "mixbox",
        "MixBox/miXboX MKII": "mixbox-mkii", "Scratchbox": "scratchbox", "Restyler": "restyler",
    }
    for rel, slug in folder_map.items():
        for p in images_in(TRANSTEL / "RODEC Mixers" / rel):
            if re.search(r"(?i)crossfader|grayscale|modified", p.stem):
                continue
            by_slug[slug]["photos"].append((p, p.stem))

    def photo_rank(item):
        s = item[1].lower()
        return (0 if "cutout" in s or ("front" in s and "slanted" in s) or "eerste mixer" in s
                else 1 if "perspectief" in s else 2 if "front" in s and "detail" not in s else 3,
                natural_key(item[1]))

    for m in models:
        items = sorted(m["photos"], key=photo_rank)
        m["photos"] = [Img(p, f"models/{m['slug']}/{slugify(stem)}", f"Rodec {m['name']}",
                           re.sub(r"(?i)\b(BW|C)\b", "", stem).strip(), white=p.stem in ON_WHITE).build()
                       for p, stem in items]

    # ---- studio photo prints from the archive boxes
    for stem, slug, cap, first in box_scans.PHOTOS:
        m = by_slug[slug]
        img = Img(box_src(stem), f"models/{slug}/box-{slugify(stem)}", f"Rodec {m['name']}", cap).build()
        m["photos"].insert(0, img) if first else m["photos"].append(img)

    # ---- brochures (old folders) and press
    print("Brochures & press …")
    general_brochures, press = {}, {}
    for p in images_in(INFO / "RODEC Ads + reviews + leaflets" / "OLD FOLDERS"):
        group, page = page_group(p.stem)
        if re.match(r"(?i)^samen$", group):
            continue  # layout composite, not an original brochure
        group = {"The seauel story - 10 years MX180": "The sequel story - 10 years MX180",
                 "Disco mix-Max 25 years Rodec": "Disco-Mix & Disco-Max - 25 years Rodec"}.get(group, group)
        if re.match(r"(?i)^the fader 1061", group):
            m = by_slug.get("1061-1071")
        elif re.match(r"(?i)^(samen|mix with|sound machines|the new faces|the link|the seauel|disco mix-max 25)", group):
            m = None
        else:
            m = match(group)
        bucket = m["brochures"] if m else None
        key = f"brochures/{slugify(group)}-{page:03d}"
        img = Img(p, key, f"Rodec brochure: {group}, page {page or 1}", full=2000)
        if m:
            existing = next((b for b in m["brochures"] if b["title"] == group), None)
            if not existing:
                existing = {"title": group, "pages": []}
                m["brochures"].append(existing)
            existing["pages"].append(img.build())
        else:
            general_brochures.setdefault(group, []).append(img.build())

    def add_press(folder: Path, kind: str):
        for p in images_in(folder):
            group, page = page_group(p.stem)
            if re.match(r"(?i)^news sos", group):
                continue  # duplicates of the SOS scans
            if re.match(r"(?i)^sos\d*$", group):
                group, page = "Sound On Sound - MAR 2010", int(re.sub(r"\D", "", p.stem) or 1)
            group = group.replace("ADD ", "Ad ").replace("Advertentie", "Ad")
            key = f"press/{slugify(group)}-{page:03d}"
            entry = press.setdefault(group, {"title": group, "kind": kind, "pages": []})
            entry["pages"].append(Img(p, key, f"{group}, page {page or 1}", full=2000).build())

    ads = INFO / "RODEC Ads + reviews + leaflets"
    add_press(ads / "OLD REVIEWS & AD's", "ad")
    add_press(ads / "NEW REVIEW", "review")
    add_press(ads, "press")

    # ---- archive boxes: brochures (replacing older scans of the same brochure, see box_scans.REPLACES) and press
    print("Archive boxes …")
    for title, slug, stems in box_scans.BROCHURES:
        what = f"Rodec {title}" if slug else title
        pages = [Img(box_src(st), f"brochures/box-{slugify(title)}-{i + 1:03d}", f"{what}, page {i + 1}", full=2000).build()
                 for i, st in enumerate(stems)]
        old_title = box_scans.REPLACES.get(title)
        if slug:
            old = by_slug[slug]["brochures"]
            if old_title and not any(b["title"] == old_title for b in old):
                warn(f"{title}: nothing called {old_title!r} to replace")
            by_slug[slug]["brochures"] = [b for b in old if b["title"] != old_title] + [{"title": title, "pages": pages, "box": True}]
        else:
            general_brochures.pop(old_title, None)
            general_brochures[title] = pages
    for title, kind, stems in box_scans.PRESS:
        press[title] = {"title": title, "kind": kind, "pages": [
            Img(box_src(st), f"press/box-{slugify(title)}-{i + 1:03d}", f"{title}, page {i + 1}", full=2000).build()
            for i, st in enumerate(stems)]}

    # ---- 2010 catalogue: product shots, history collages and every page
    catalogue_pages, catalogue_history = [], []
    if CATALOGUE.exists():
        print("2010 catalogue …")
        imgdir = CACHE / "catalogue-images"
        pagedir = CACHE / "catalogue-pages"
        if FORCE or not imgdir.exists():
            imgdir.mkdir(parents=True, exist_ok=True)
            os.system(f'pdfimages -f 4 -l 30 -png -p "{CATALOGUE}" "{imgdir}/i"')
        if FORCE or not pagedir.exists():
            pagedir.mkdir(parents=True, exist_ok=True)
            os.system(f'pdftoppm -r 150 -jpeg -jpegopt quality=90 "{CATALOGUE}" "{pagedir}/p"')
        for slug, stems in CATALOGUE_IMAGES.items():
            m = by_slug[slug]
            for stem in stems:
                src = imgdir / f"{stem}.png"
                if not src.exists():
                    warn(f"catalogue image {stem} missing")
                    continue
                m["photos"].append(Img(src, f"models/{slug}/catalogue-{stem[2:]}", f"Rodec {m['name']}",
                                       f"{m['name']}, Rodec catalogue 2010").build())
        catalogue_history = [Img(imgdir / f"{stem}.png", f"history/catalogue-{stem[2:]}", cap, cap).build()
                             for stem, cap in CATALOGUE_HISTORY if (imgdir / f"{stem}.png").exists()]
        catalogue_pages = [Img(p, f"catalogue/{p.stem}", f"Rodec catalogue 2010, page {i + 1}", full=1800).build()
                           for i, p in enumerate(sorted(pagedir.glob("p-*.jpg")))]
    else:
        warn(f"catalogue not found: {CATALOGUE}")

    # ---- approved web photos (models with no photo in the archive)
    if WEB_APPROVED.exists():
        print("Approved web photos …")
        for folder in sorted(p for p in WEB_APPROVED.iterdir() if p.is_dir()):
            m = match(folder.name)
            if not m:
                warn(f"web photo folder without model: {folder.name}")
                continue
            for f in images_in(folder):
                m["photos"].append(Img(f, f"models/{m['slug']}/web-{slugify(f.stem)}", f"Rodec {m['name']}", m["name"]).build())

    # ---- book
    print("50 years book …")
    book = [Img(p, f"book/{slugify(p.stem)}", f"Rodec 50 years book, page {i + 1}",
                "Perpetual Music Makers · Rodec 50 years book", full=1600).build()
            for i, p in enumerate(images_in(INFO / "RODEC Boek" / "RODEC Boek"))]

    # ---- history & production photos
    print("History photos …")
    # File names in the archive spell the founder "De Clerck"; the correct spelling is De Clercq.
    history = [Img(p, f"history/{slugify(p.stem).replace('de-clerck', 'de-clercq')}", p.stem, p.stem).build()
               for p in images_in(INFO / "RODEC Old pictures" / "OLD PICTURES")]
    history += [Img(p, f"history/{slugify(p.stem)}", f"Rodec {p.stem}", p.stem).build()
                for p in unmatched_photos if re.match(r"(?i)^rodec", p.stem)]
    # Captions for the best scans; then drop duplicates (same photo in BW / colour / re-scan).
    HISTORY_CAPTIONS = {
        r"^rodec - radio$": "RODEC RADIO, Lange Beeldekensstraat 32, Antwerp. 1950s",
        r"^roger de clerck old 2$": "ROger DE Clercq, founder of Rodec",
        r"^rodec address card 70's - 003$": "Export business card, 1970s",
        r"^roger & theo$": "Roger & Theo",
        r"^dealerdays anno 1979$": "Dealer days, 1979",
        r"^eind test rodec mx180mkiii$": "Final test of an MX180 MKIII",
    }
    box_history = [Img(box_src(st, crop, rot), f"history/box-{slugify(cap)[:60]}", cap, cap).build()
                   for st, cap, crop, rot in box_scans.HISTORY]
    for h in history:
        for pat, cap in HISTORY_CAPTIONS.items():
            if re.match(pat, h.get("caption", ""), re.I):
                h["caption"] = h["alt"] = cap
    history = dedupe(box_history + history, prefer=[r"RODEC RADIO, Lange", r"founder of Rodec", r"Export business card"])
    # Variants too different for the hash check: other edits of the shop, Roger and card photos.
    history = [h for h in history if not re.match(
        r"(?i)^((rodec )?rodec radio shop|roger de clerck (b&w|color|old)$|rodec address card 70's( - 002)?$)", h.get("caption", ""))]
    shop_photo = next((h for h in history if h["caption"].startswith("RODEC RADIO,")), None)
    roger_photo = next((h for h in history if "founder of Rodec" in h["caption"]), None)
    production = [Img(p, f"production/{slugify(p.stem)}", f"Rodec production: {p.stem}", p.stem).build()
                  for p in images_in(INFO / "RODEC Old pictures" / "PRODUCTION PICS")]

    # ---- DJs (named photos only; anonymous Facebook downloads are skipped)
    DJ_CROPS = {  # file stem -> (crop box, caption)
        "Ricardo Villalobos": ((70, 99, 640, 738), "Ricardo Villalobos @ Amnesia Ibiza (photo: Ignacio Capella)"),
    }
    print("DJ photos …")
    djs = []
    junk = re.compile(r"^(\d+_.*_n|\d+|[a-zA-Z])\1*$|^\d+_|^0+\d+$|^([A-Za-z])\2{3,}$")
    for folder in (TRANSTEL / "RODEC Dj foto's", TRANSTEL / "RODEC Dj foto's" / "DJs with RODEC"):
        for p in images_in(folder):
            if junk.search(p.stem) or re.fullmatch(r"\d{3,4}", p.stem):
                continue
            cap = re.sub(r"\s*\d?jpg$|\s+\d$|%20", " ", p.stem).strip()
            cap = re.sub(r"(?<=[a-z])\d$", "", cap)
            cap = re.sub(r"\s+", " ", cap.replace(" at ", " @ ")).strip()
            src = p
            if p.stem in DJ_CROPS:  # cut the photo out of a social-media screenshot
                box, cap = DJ_CROPS[p.stem]
                src = CACHE / "crops" / f"{slugify(p.stem)}.png"
                if FORCE or not src.exists() or src.stat().st_mtime < p.stat().st_mtime:
                    src.parent.mkdir(parents=True, exist_ok=True)
                    with Image.open(p) as im:
                        im.convert("RGB").crop(box).save(src)
            djs.append(Img(src, f"djs/{slugify(p.stem)}", f"{cap} with a Rodec mixer", cap).build())

    # ---- documents
    print("Manuals & schematics …")
    docs_out = []
    for d in DOC_LIST:
        build_doc(d)
        if d.missing:
            continue
        for s in d.models:
            if s in by_slug:
                by_slug[s]["docs"].append(d.id)
            else:
                warn(f"doc {d.id}: unknown model slug {s}")
        docs_out.append({k: v for k, v in d.__dict__.items() if k not in ("sources", "missing")})

    # ---- write data
    DATA.mkdir(parents=True, exist_ok=True)
    for m in models:
        m.pop("aliases", None)
    (DATA / "models.json").write_text(json.dumps(models, indent=1, ensure_ascii=False))
    (DATA / "docs.json").write_text(json.dumps(docs_out, indent=1, ensure_ascii=False))
    (DATA / "archive.json").write_text(json.dumps({
        "book": book,
        "brochures": ([{"title": "Catalogue 2010 · 55 years", "pages": catalogue_pages}] if catalogue_pages else [])
                     + [{"title": k, "pages": v} for k, v in general_brochures.items()],
        "press": sorted(press.values(), key=lambda e: e["title"]),
        "history": history + catalogue_history,
        "historyHero": {"shop": shop_photo, "roger": roger_photo},
        "production": production,
        "djs": djs,
        "eras": [{"from": a, "to": b, "key": k, "title": t} for a, b, k, t in ERAS],
    }, indent=1, ensure_ascii=False))

    # Remove generated files that nothing references any more (dropped duplicates, renames).
    referenced = set(re.findall(r'"(/media/[^"]+)"', "".join(
        (DATA / f).read_text() for f in ("models.json", "docs.json", "archive.json"))))
    removed = 0
    for f in MEDIA.rglob("*.webp"):
        if "/" + str(f.relative_to(PUBLIC)) not in referenced:
            f.unlink()
            removed += 1
    if removed:
        print(f"Removed {removed} unreferenced media files")

    with_photo = sum(1 for m in models if m["photos"])
    print(f"\n{len(models)} models ({with_photo} with photos), {len(docs_out)} documents, "
          f"{len(book)} book pages, {len(press)} press items, {len(djs)} DJ photos")
    if warnings:
        print(f"{len(warnings)} warnings (see above)")


if __name__ == "__main__":
    main()
