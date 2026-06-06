"""Phase 7.4 — View My Program Chart (BRD §7.4).

Renders the MLA's upcoming 7-day public events as a plain-text markdown grid.
"""

from __future__ import annotations

import cloud_api
import db
import strings as S


def send(phone: str, lang: str) -> None:
    rows = db.get_mla_schedule_next_7_days()
    lines: list[str] = [S.t(lang, "schedule_header")]
    if not rows:
        lines.append(S.t(lang, "schedule_empty"))
    else:
        for r in rows:
            date_str = r["event_date"].strftime("%a %d %b")
            lines.append(
                S.t(lang, "schedule_row",
                    date=date_str,
                    title=r.get("title") or "",
                    venue=r.get("venue") or "—")
            )
    cloud_api.send_text(phone, "\n".join(lines))
