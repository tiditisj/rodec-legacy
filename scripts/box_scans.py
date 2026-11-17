"""What is in the scanned archive boxes ("Rodec archiefdozen/doos1..3").

Every scan is listed here by file stem (e.g. "rodec-038_002"), grouped into the item it belongs to.
Pages are given in reading order. Scans not listed are deliberately left out:
  - rodec-066, rodec-067: export price lists with dealer prices
  - rodec-071, rodec-072: Askom (Japan) letter and spec sheet, not Rodec
  - rodec-061*: AudioSource EQ-ONE leaflet, not Rodec
  - rodec-068_002, rodec-074_003: other brands' adverts on magazine back covers
  - rodec-074_002: unedited copy of rodec-074_002_BEWERKT
  - duplicates of scans already listed: rodec-013*, rodec-031*, rodec-035*, rodec-040*, rodec-044,
    rodec-047, rodec-052*, rodec-059*, rodec-062*, rodec-070*
"""

# Studio photo prints of a unit -> model photos. first=True puts them before the existing photos.
PHOTOS = [
    # (stem, model slug, caption, first)
    ("rodec-001", "mx240", "MX240, studio photo", False),
    ("rodec-005", "1061-1071", "Fader 1061, press photo", True),
    ("rodec-006", "cu882", "CU882 control unit, press photo", True),
    ("rodec-007", "cu881", "CU881, press photo", True),
    ("rodec-008", "2560", "2560 two-channel power amplifier, press photo", True),
    ("rodec-009", "olympus-olympus2", "Olympus 2, press photo", True),
    ("rodec-010", "mx180", "MX180 in red, studio photo", False),
]

# Brochures and leaflets. model=None -> general brochure in the Archive.
BROCHURES = [
    # (title, model slug or None, [stems])
    # 1970s: Beglec (Brussels) folders, Dutch / French
    ("1361/1371 stereo mixing panel", "1361-1371", ["rodec-053", "rodec-053_002"]),
    ("1363/1373 stereo mixing panel", "1363-1373", ["rodec-056", "rodec-056_002"]),
    ("1364/1374 stereo mixing panel", "1364-1374", ["rodec-048", "rodec-048_002"]),
    ("1385 stereo mixing panel", "1385", ["rodec-050", "rodec-050_002"]),
    ("1372 micro mixing panel", "1372", ["rodec-051", "rodec-051_002"]),
    ("Fader 1061/1071", "1061-1071", ["rodec-055", "rodec-055_002"]),
    ("Fader 1061: press photo with typed specifications", "1061-1071", ["rodec-005", "rodec-005_002"]),
    ("Power Amplifier 1572", "1572", ["rodec-054"]),
    ("CU888 mixing panel", "cu888", ["rodec-054_002"]),
    ("CU888 (Beglec folder)", "cu888", ["rodec-037", "rodec-037_002"]),
    ("CU882: press photo with description", "cu882", ["rodec-006", "rodec-006_002"]),
    ("CU881: press photo with specifications", "cu881", ["rodec-007", "rodec-007_002"]),
    ("2560 two-channel power amplifier", "2560", ["rodec-036", "rodec-036_002"]),
    ("2560: press photo with specifications", "2560", ["rodec-008", "rodec-008_002"]),
    ("Tuner T800", "t800", ["rodec-049", "rodec-049_002"]),
    # late 1970s - early 1980s: Transtel-Sabima (Antwerp)
    ("Mixetta: the best mixer money can buy", "mixetta", ["rodec-030_002"]),
    ("Power Project 100", "power-project-100", ["rodec-030"]),
    ("Disco-Mix: de doorbraak in mixer-technologie", "disco-mix", ["rodec-033"]),
    ("Disco-Mix leaflet with block diagram", "disco-mix", ["rodec-027", "rodec-027_002"]),
    ("Olympus: een mixer voor prijsbewuste kopers", "olympus-olympus2", ["rodec-033_002"]),
    ("Disco-Max", "disco-max", ["rodec-026", "rodec-026_002", "rodec-026_003"]),
    ("MF100M: a new approach to mixing pleasure", "mf100m", ["rodec-025", "rodec-025_002"]),
    ("MF100M: Rodec mixes music into magic", "mf100m", ["rodec-063", "rodec-063_002"]),
    ("QS4 start unit", "qs4", ["rodec-064", "rodec-064_002", "rodec-064_003"]),
    ("SM300: a triumph of flexibility", "sm300", ["rodec-012_002", "rodec-012"]),
    ("HDA340: success is no accident", "hda340", ["rodec-039", "rodec-039_002"]),
    # MX era
    ("MX7: the digital-ready mixer", "mx7", ["rodec-041", "rodec-041_002"]),
    ("MX10: a stunning performer every night of the week", "mx10", ["rodec-014", "rodec-014_002", "rodec-014_003"]),
    ("MX18: the digital-ready mixer", "mx18", ["rodec-022", "rodec-022_002", "rodec-022_003"]),
    ("Preview MX18", "mx18", ["rodec-073", "rodec-073_002"]),
    ("MX100", "mx100", ["rodec-024_002", "rodec-024"]),
    ("MX180", "mx180", ["rodec-023_002", "rodec-023"]),
    ("MX130", "mx130", ["rodec-019_002", "rodec-019"]),
    # general
    ("Rodec 25! 1954-1979", None, ["rodec-029", "rodec-029_002", "rodec-029_003"]),
    ("Rodec celebrates: the new faces", None, ["rodec-043", "rodec-043_002"]),
    ("Matériel audio-visuel de qualité depuis 1954", None, ["rodec-034", "rodec-034_002"]),
    ("Precision in audio mixers (Canada)", None, ["rodec-015_002", "rodec-015"]),
    ("The only way up (Germany)", None, ["rodec-016_002", "rodec-016"]),
    ("Die Erfolgsstory 1961-1997 (Germany)", None, ["rodec-046", "©_002"]),
    ("Retail price list, November 1996", None, ["rodec-018"]),
    ("The Rodec history: presentation sheets (2000s)", None,
     ["rodec-002", "rodec-002_002", "rodec-002_003", "rodec-002_004", "rodec-002_005"]),
    ("Aerobic Dancing: Audio Luidsprekers, Eindhoven", None,
     ["rodec-065_003", "rodec-065", "rodec-065_002", "rodec-069", "rodec-069_002", "rodec-069_003",
      "rodec-069_004", "rodec-069_005", "rodec-069_006"]),
]

# Magazine pages and adverts -> Archive, Ads & reviews.
PRESS = [
    # (title, kind, [stems])
    ("Stereo Technic, June 1979 (Japan): Disco-Mix", "review", ["rodec-074", "rodec-074_002_BEWERKT"]),
    ("Populær Elektronik 4/81 (Denmark): cover", "press", ["rodec-068"]),
    ("Ad: let Rodec provide the good vibrations", "ad", ["rodec-029_002"]),
    ("Ads Japan: SM200, MF100M and SM300 (Imai & Co)", "ad", ["rodec-042", "rodec-042_002"]),
    ("Ad: Mixmaster, Japan (Imai & Co)", "ad", ["rodec-060"]),
    ("Ad France: Bandes, tendances 80", "ad", ["rodec-028"]),
    ("Ad Italy: La produzione giapponese", "ad", ["rodec-032"]),
    ("Allo, Allo… June/July 1996", "review", ["rodec-017", "rodec-017_002"]),
]

# History photos. crop = (x0, y0, x1, y1) in the full-resolution scan; rotate in degrees.
HISTORY = [
    # (stem, caption, crop, rotate)
    ("rodec-020", "Rodec Radio, Lange Beeldekensstraat 32, Antwerp: the shop at night and the first business cards", None, 0),
    ("rodec-003", "Radio Stand shop front", None, 0),
    ("rodec-021", "In the Rodec workshop", None, 0),
    ("rodec-004", "Studio photo of the late-1970s range", None, 0),
    ("rodec-011", "Double Dutch", None, 0),
    ("rodec-058", "Rodec stand at a trade fair in Antwerp", None, 0),
    ("rodec-045", "At the test bench, 1980s (from a contact sheet)", (4105, 1262, 4855, 1745), 0),
    ("rodec-045", "In the Rodec lab, 1980s (from a contact sheet)", (2533, 3012, 3271, 3499), 0),
    ("rodec-045", "Component stock, 1980s (from a contact sheet)", (1749, 4780, 2479, 5263), 0),
    ("rodec-045", "Showing a front panel, 1980s (from a contact sheet)", (2533, 4780, 3271, 5263), 0),
    ("rodec-045", "Assembly, 1980s (from a contact sheet)", (920, 5623, 1650, 6118), 0),
]

# Manuals made from box scans (added to the document list).
DOCS = [
    # (id, title, kind, models, [stems])
    ("1385-service-box", "1385 service manual: schematic, parts list and PCB layout", "service", ["1385"],
     ["rodec-038", "rodec-038_002", "rodec-038_003", "rodec-038_004", "rodec-038_005", "rodec-038_006"]),
    ("1364-service-box", "1364 / 1374 service manual", "service", ["1364-1374"],
     ["rodec-057", "rodec-057_002", "rodec-057_003", "rodec-057_004"]),
    ("mixmaster-user-jp", "Mixmaster user manual (Japanese, Imai & Co)", "user", ["mixmaster"],
     ["rodec-060_002", "rodec-060_003", "rodec-060_004", "rodec-060_005"]),
]

# Box brochure title -> title of the older (lower quality) scan of the same brochure that it replaces.
REPLACES = {
    "1364/1374 stereo mixing panel": "1364-74",
    "1385 stereo mixing panel": "1385",
    "1372 micro mixing panel": "1372",
    "Power Amplifier 1572": "1572",
    "2560 two-channel power amplifier": "2560",
    "Tuner T800": "T800",
    "Mixetta: the best mixer money can buy": "Mixetta",
    "Power Project 100": "Power Project 100",
    "Disco-Max": "Disco max",
    "MF100M: Rodec mixes music into magic": "MF100M",
    "HDA340: success is no accident": "HDA340",
    "SM300: a triumph of flexibility": "SM300",
    "MX7: the digital-ready mixer": "MX7",
    "MX10: a stunning performer every night of the week": "MX10",
    "MX18: the digital-ready mixer": "MX18",
    "MX100": "MX100",
    "MX180": "MX180",
    "MX130": "MX130",
    "Rodec celebrates: the new faces": "The new faces",
    "Matériel audio-visuel de qualité depuis 1954": "Sound Machines",
}
