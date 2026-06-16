"""Phase 3 — MLA office admin tooling (BRD scope-extension).

Read-only ticket / meeting / event viewer for the MLA's office to triage
citizen submissions. Mounted under `/admin/*`, locked behind HTTP Basic Auth
sourced from ADMIN_USERNAME + ADMIN_PASSWORD env vars.

If those env vars aren't set on the host, the admin returns 503 to every
request — fail-closed, not fail-open.

Later phases will add: status updaters (3.2), schedule editor (3.3), location
updater (3.4), outbound notifications when status changes (3.5).
"""

from __future__ import annotations

import html
import os
import secrets
from datetime import datetime
from typing import Any, Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import db


router = APIRouter(prefix="/admin")
_security = HTTPBasic(auto_error=True)


# ─── Auth ───────────────────────────────────────────────────────────────────

def _admin_credentials() -> tuple[str, str]:
    return os.environ.get("ADMIN_USERNAME", ""), os.environ.get("ADMIN_PASSWORD", "")


def _verify_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
    expected_user, expected_pass = _admin_credentials()
    if not expected_user or not expected_pass:
        # Fail-closed when the admin hasn't been configured at all.
        raise HTTPException(status_code=503, detail="admin not configured")

    correct = (
        secrets.compare_digest(credentials.username, expected_user)
        and secrets.compare_digest(credentials.password, expected_pass)
    )
    if not correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ─── Data access ────────────────────────────────────────────────────────────

def fetch_tickets(
    status_filter: Optional[str] = None,
    ward_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read complaints with optional filters. status_filter='ALL' or None means no filter."""
    where: list[str] = []
    args: list[Any] = []
    if status_filter and status_filter.upper() != "ALL":
        where.append("status = %s")
        args.append(status_filter.upper())
    if ward_id is not None:
        where.append("ward_id = %s")
        args.append(ward_id)

    sql = "SELECT * FROM mymla_complaints"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT %s"
    args.append(limit)

    conn = db.get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]


def fetch_counts_by_status() -> dict[str, int]:
    """Cheap status summary for the filter bar."""
    conn = db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM mymla_complaints GROUP BY status")
        return {row[0]: row[1] for row in cur.fetchall()}


# ─── Rendering ──────────────────────────────────────────────────────────────

_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #1a1a1a; }
h1 { font-size: 22px; margin-bottom: 4px; }
.subtitle { color: #666; font-size: 13px; margin-bottom: 20px; }
.filters { margin: 16px 0; font-size: 13px; }
.filters a { margin-right: 12px; padding: 4px 10px; border: 1px solid #ddd;
    border-radius: 6px; text-decoration: none; color: #1a1a1a; }
.filters a.active { background: #1a4480; color: #fff; border-color: #1a4480; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border: 1px solid #e5e5e5; padding: 6px 10px; text-align: left;
    vertical-align: top; }
th { background: #f5f7fa; font-weight: 600; }
tr:hover td { background: #fafbfc; }
.ticket-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.status { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
    display: inline-block; }
.status-OPEN     { background: #fff3cd; color: #856404; }
.status-IN_PROGRESS { background: #cce5ff; color: #004085; }
.status-RESOLVED { background: #d4edda; color: #155724; }
.status-CLOSED   { background: #e2e3e5; color: #383d41; }
.desc { max-width: 380px; }
.muted { color: #777; }
.empty { padding: 40px; text-align: center; color: #888; }
"""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _fmt_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %H:%M")
    return _esc(value)


def _truncate(text: Optional[str], n: int = 120) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[: n - 1] + "…"


def _filter_bar(active: str, counts: dict[str, int]) -> str:
    options = [("ALL", "All"), ("OPEN", "Open"), ("IN_PROGRESS", "In progress"),
               ("RESOLVED", "Resolved"), ("CLOSED", "Closed")]
    parts: list[str] = []
    for key, label in options:
        count = sum(counts.values()) if key == "ALL" else counts.get(key, 0)
        cls = "active" if active.upper() == key else ""
        parts.append(
            f'<a class="{cls}" href="/admin/tickets?status={key}">'
            f'{_esc(label)} <span class="muted">({count})</span></a>'
        )
    return '<div class="filters">' + "".join(parts) + "</div>"


def _row(row: dict[str, Any]) -> str:
    description = _truncate(row.get("description_text"))
    voice = "🎙" if row.get("description_voice_url") else ""
    images = row.get("image_media_ids") or []
    images_label = f"📷 ×{len(images)}" if images else ""
    media_cell = " ".join(filter(None, [voice, images_label])) or '<span class="muted">—</span>'

    status_value = (row.get("status") or "OPEN").upper()
    ward_booth = f"W{row.get('ward_id')}"
    if row.get("booth_number") is not None:
        ward_booth += f" / B{row['booth_number']}"

    return "<tr>" + "".join([
        f'<td class="ticket-id">{_esc(row.get("ticket_id"))}</td>',
        f'<td>{_fmt_dt(row.get("created_at"))}</td>',
        f'<td>{_esc(ward_booth)}</td>',
        f'<td>{_esc(row.get("category"))}</td>',
        f'<td class="desc">{_esc(description)}</td>',
        f'<td>{media_cell}</td>',
        f'<td>{_esc(row.get("phone"))}</td>',
        f'<td><span class="status status-{_esc(status_value)}">{_esc(status_value)}</span></td>',
    ]) + "</tr>"


def render_tickets_page(rows: list[dict[str, Any]], status_filter: str,
                        counts: dict[str, int]) -> str:
    header = "<tr>" + "".join(f"<th>{c}</th>" for c in (
        "Ticket", "Created", "Ward / Booth", "Category", "Description",
        "Media", "Phone", "Status",
    )) + "</tr>"

    if rows:
        body = header + "".join(_row(r) for r in rows)
        table = f"<table>{body}</table>"
    else:
        table = '<div class="empty">No tickets match this filter.</div>'

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>MyMLA — Tickets</title>
<style>{_CSS}</style></head>
<body>
<h1>MyMLA — Citizen Complaints</h1>
<div class="subtitle">{len(rows)} ticket(s) shown · filter: <b>{_esc(status_filter)}</b></div>
{_filter_bar(status_filter, counts)}
{table}
</body></html>
"""


# ─── Routes ─────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def admin_home(_user: str = Depends(_verify_admin)) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>MyMLA — Admin</title>
<style>{_CSS}</style></head>
<body>
<h1>MyMLA — MLA Office Console</h1>
<div class="subtitle">Signed in as <b>{_esc(_user)}</b></div>
<ul>
  <li><a href="/admin/tickets">📝 Citizen complaints</a></li>
</ul>
</body></html>
"""


@router.get("/tickets", response_class=HTMLResponse)
def admin_tickets(
    status: str = Query("OPEN"),
    ward_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    _user: str = Depends(_verify_admin),
) -> str:
    rows = fetch_tickets(status_filter=status, ward_id=ward_id, limit=limit)
    counts = fetch_counts_by_status()
    return render_tickets_page(rows, status, counts)
