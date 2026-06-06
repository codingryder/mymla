"""Phase 7.2 — Where is my MLA (BRD §7.2).

Single-shot: read the singleton mla_location row and render a bilingual status card.
"""

from __future__ import annotations

import cloud_api
import db
import strings as S
import wards as W


_STATUS_KEY_TO_STRING = {
    "assembly":   "location_status_assembly",
    "inspection": "location_status_inspection",
    "office":     "location_status_office",
}


def send(phone: str, lang: str) -> None:
    row = db.get_mla_location()
    key = (row.get("status_key") or "office").lower()
    string_key = _STATUS_KEY_TO_STRING.get(key, "location_status_office")

    fmt: dict = {}
    if key == "inspection":
        fmt["ward_name"] = W.ward_name(row.get("status_ward_id") or 0, lang) or "—"

    status = S.t(lang, string_key, **fmt)
    updated_at = row.get("updated_at")
    updated_str = updated_at.strftime("%d %b %Y, %H:%M") if updated_at else "—"
    card = S.t(lang, "location_card", status=status, updated_at=updated_str)
    cloud_api.send_text(phone, card)
