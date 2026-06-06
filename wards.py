"""26-ward master data per BRD §4.

Source: BRD v1.0 Master Constituency Data Mapping (Thiruvananthapuram constituency,
wards 1–26, derived from IMG_1184.JPG → IMG_1209.JPG).
"""

from __future__ import annotations

from typing import Iterable


# Ordered list of wards. Index 0 is unused so ward_id matches BRD numbering 1..26.
WARDS: list[dict] = [
    {},  # placeholder so wards[1] == Vanchiyoor
    {"id":  1, "name_mal": "വഞ്ചിയൂര്‍",      "name_eng": "Vanchiyoor",    "booths": [70, 71, 72, 73, 74, 77, 78, 79]},
    {"id":  2, "name_mal": "പേട്ട",           "name_eng": "Pettah",        "booths": [63, 64, 65, 66, 67, 68, 69, 75, 76]},
    {"id":  3, "name_mal": "പാല്‍കുളങ്ങര",     "name_eng": "Palkulangara",  "booths": [23, 24, 25, 26, 50, 51, 52, 53]},
    {"id":  4, "name_mal": "വള്ളക്കടവ്",       "name_eng": "Vallakkadavu",  "booths": [41, 42, 43, 44, 45, 171, 172, 173, 174, 175]},
    {"id":  5, "name_mal": "പെരുന്താന്നി",    "name_eng": "Perunthanni",   "booths": [47, 48, 54, 55, 56, 57, 58, 59, 60, 61, 62]},
    {"id":  6, "name_mal": "ചാക്ക",            "name_eng": "Chakai",        "booths": [27, 28, 29, 30, 31, 32, 33, 49]},
    {"id":  7, "name_mal": "ശ്രീവരാഹം",       "name_eng": "Sreevaraham",   "booths": [176, 177, 185, 188, 189, 190, 193, 194, 195]},
    {"id":  8, "name_mal": "ശ്രീകണ്ഠേശ്വരം",  "name_eng": "Sreekanteswaram","booths": [89, 90, 92, 94, 96, 97]},
    {"id":  9, "name_mal": "ബീമാപള്ളി",       "name_eng": "Beemapally",    "booths": [196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 216]},
    {"id": 10, "name_mal": "പൂന്തുറ",          "name_eng": "Poonthura",     "booths": [219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230]},
    {"id": 11, "name_mal": "മാണിക്യവിളാകം",   "name_eng": "Manikavilakam", "booths": [208, 209, 210, 211, 212, 213, 214, 215, 217, 218]},
    {"id": 12, "name_mal": "വലിയതുറ",          "name_eng": "Valiyathura",   "booths": [161, 162, 163, 164, 165, 166, 167, 168, 169, 170]},
    {"id": 13, "name_mal": "ശംഖുമുഖം",        "name_eng": "Shanghumukham", "booths": [34, 35, 36, 37, 38, 39, 40, 46]},
    {"id": 14, "name_mal": "വെട്ടുകാട്",       "name_eng": "Vettukaud",     "booths": [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 17]},
    {"id": 15, "name_mal": "കണ്ണാന്തുറ",      "name_eng": "Kannanthura",   "booths": [9, 11, 13, 15, 18, 19, 20, 21, 22]},
    {"id": 16, "name_mal": "വഴുതക്കാട്",      "name_eng": "Vazhuthacaud",  "booths": [102, 103, 104, 105, 106, 107, 108]},
    {"id": 17, "name_mal": "ജഗതി",             "name_eng": "Jagathy",       "booths": [113, 114, 115, 116, 117, 118, 119, 120, 121]},
    {"id": 18, "name_mal": "തൈക്കാട്",          "name_eng": "Thycaud",       "booths": [123, 124, 125, 126, 127, 128]},
    {"id": 19, "name_mal": "വലിയശാല",          "name_eng": "Valiyasala",    "booths": [131, 132, 133, 138, 142]},
    {"id": 20, "name_mal": "തമ്പാനൂര്‍",       "name_eng": "Thampanoor",    "booths": [80, 81, 85, 86, 87, 88, 109, 110, 111, 112, 122, 129, 130]},
    {"id": 21, "name_mal": "പാളയം",            "name_eng": "Palayam",       "booths": [82, 83, 84, 100, 101]},
    {"id": 22, "name_mal": "ചാല",              "name_eng": "Chala",         "booths": [134, 135, 136, 137, 149, 150, 151, 154, 155, 156, 157]},
    {"id": 23, "name_mal": "മണക്കാട്",         "name_eng": "Manacaud",      "booths": [178, 179, 180, 181, 182, 183, 184, 186, 187, 191, 192]},
    {"id": 24, "name_mal": "ഫോര്‍ട്ട്",         "name_eng": "Fort",          "booths": [91, 93, 95, 98, 99]},
    {"id": 25, "name_mal": "കുര്യാത്തി",       "name_eng": "Kuryathi",      "booths": [158, 159, 160]},
    {"id": 26, "name_mal": "അട്ടക്കുളങ്ങര",   "name_eng": "Attakulangara", "booths": [139, 140, 141, 143, 144, 145, 146, 147, 148, 152, 153]},
]


def ward_by_id(ward_id: int) -> dict | None:
    if 1 <= ward_id <= 26:
        return WARDS[ward_id]
    return None


def ward_name(ward_id: int, lang: str) -> str:
    w = ward_by_id(ward_id)
    if not w:
        return ""
    return w["name_mal"] if lang == "mal" else w["name_eng"]


def booths_for_ward(ward_id: int) -> list[int]:
    w = ward_by_id(ward_id)
    return list(w["booths"]) if w else []


# WhatsApp List Message supports up to 10 rows per section. For wards with more
# than 9 booths we slice into pages of 9 so the 10th row can be "Next page".
BOOTHS_PER_PAGE = 9


def paginate_booths(ward_id: int, page: int = 0) -> tuple[list[int], bool]:
    """Return (booth_slice, has_next_page) for the given ward and zero-indexed page."""
    booths = booths_for_ward(ward_id)
    start = page * BOOTHS_PER_PAGE
    end = start + BOOTHS_PER_PAGE
    slice_ = booths[start:end]
    has_next = end < len(booths)
    return slice_, has_next


def all_wards() -> Iterable[dict]:
    return WARDS[1:]
