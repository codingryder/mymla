"""Phase 3 — MLA office admin console.

Read-only viewer + future status updaters for citizen submissions. Locked behind
form-based session auth (signed cookie) with HTTP Basic Auth as a backwards-
compat fallback for scripts/curl. Both validate against ADMIN_USERNAME +
ADMIN_PASSWORD env vars; fail-closed (503) when either is blank.

Visual design follows assets/PHILOSOPHY.md (Civic Vellum):
  - One teal (#0B4E56) — monsoon-darkened brass
  - One warm ivory (#F5F1E8) — old paper, softened
  - One barely-gold (#D2BB84) — the held breath, used only as a hairline
  - No gradients, no shadows beyond a single hairline border
  - "Engraved, not drawn" — the dashboard should feel like an *office*, not a SaaS

Routes:
  GET  /admin/         dashboard home — KPIs + charts + latest tickets
  GET  /admin/tickets  paginated complaint table with filters
  GET  /admin/login    styled sign-in form
  POST /admin/login    validate + set session cookie
  GET  /admin/logout   clear session cookie
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import html
import json
import os
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import db
import wards as W


router = APIRouter(prefix="/admin")
_basic = HTTPBasic(auto_error=False)  # don't auto-401; we want session-first auth


# ─── Brand palette (Civic Vellum) ───────────────────────────────────────────

TEAL       = "#0B4E56"
TEAL_DARK  = "#073A40"
TEAL_DEEP  = "#052B30"
IVORY      = "#F5F1E8"
IVORY_PAGE = "#FAF7EE"
GOLD       = "#D2BB84"
TEXT       = "#1F2A2C"
TEXT_MUTED = "#6B7676"
BORDER     = "#E6DFCF"


# ─── Auth ───────────────────────────────────────────────────────────────────

_COOKIE_NAME = "mymla_admin_session"
_SESSION_TTL_S = 12 * 3600


def _admin_credentials() -> tuple[str, str]:
    return os.environ.get("ADMIN_USERNAME", ""), os.environ.get("ADMIN_PASSWORD", "")


def _session_secret() -> str:
    """Secret used to sign the session cookie. Falls back to META_APP_SECRET so
    we don't require a new env var; both must be set in production anyway."""
    return os.environ.get("SESSION_SECRET") or os.environ.get("META_APP_SECRET", "")


def _sign_session(username: str) -> str:
    """Sign a session token: base64url(payload).short_hmac. Includes a timestamp
    so we can age-check on read."""
    secret = _session_secret()
    payload = json.dumps({"u": username, "t": int(time.time())}, separators=(",", ":"))
    body = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def _read_session(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None
    secret = _session_secret()
    if not secret:
        return None
    body, _, sig = token.partition(".")
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (binascii.Error, ValueError, json.JSONDecodeError):
        return None
    if int(time.time()) - int(payload.get("t", 0)) > _SESSION_TTL_S:
        return None
    return payload.get("u")


def _credentials_match(user: str, pw: str) -> bool:
    expected_user, expected_pass = _admin_credentials()
    if not expected_user or not expected_pass:
        return False
    return (secrets.compare_digest(user, expected_user)
            and secrets.compare_digest(pw, expected_pass))


def _require_admin(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(_basic),
) -> str:
    """Auth gate for every admin page.

    Order of attempts:
      1. Signed session cookie set by /admin/login
      2. HTTP Basic Auth header (for scripts/curl)
      3. Otherwise: 307 redirect to /admin/login (or 503 if admin env unset)
    """
    expected_user, expected_pass = _admin_credentials()
    if not expected_user or not expected_pass:
        raise HTTPException(status_code=503, detail="admin not configured")

    # 1. session cookie
    user = _read_session(request.cookies.get(_COOKIE_NAME))
    if user:
        return user

    # 2. HTTP Basic Auth
    if credentials and _credentials_match(credentials.username, credentials.password):
        return credentials.username

    # 3. send to the styled login form
    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": "/admin/login"},
    )


# ─── Small utilities ────────────────────────────────────────────────────────

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


def _query_all(sql: str, args: Iterable[Any] = ()) -> list[dict[str, Any]]:
    conn = db.get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, list(args))
        return [dict(r) for r in cur.fetchall()]


def _query_one(sql: str, args: Iterable[Any] = ()) -> dict[str, Any] | None:
    rows = _query_all(sql, args)
    return rows[0] if rows else None


# ─── Data access ────────────────────────────────────────────────────────────

def fetch_tickets(
    status_filter: Optional[str] = None,
    ward_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
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
    return _query_all(sql, args)


def fetch_counts_by_status() -> dict[str, int]:
    rows = _query_all("SELECT status, COUNT(*) AS n FROM mymla_complaints GROUP BY status")
    return {(r["status"] or "OPEN"): int(r["n"]) for r in rows}


def fetch_counts_by_category(days: int = 30) -> list[tuple[str, int]]:
    rows = _query_all(
        """
        SELECT COALESCE(category, '—') AS category, COUNT(*) AS n
        FROM mymla_complaints
        WHERE created_at >= NOW() - %s::interval
        GROUP BY 1
        ORDER BY 2 DESC
        """,
        (f"{int(days)} days",),
    )
    return [(r["category"], int(r["n"])) for r in rows]


def fetch_top_wards(limit: int = 5) -> list[tuple[int, int]]:
    rows = _query_all(
        """
        SELECT ward_id, COUNT(*) AS n
        FROM mymla_complaints
        WHERE ward_id IS NOT NULL
        GROUP BY ward_id
        ORDER BY n DESC, ward_id ASC
        LIMIT %s
        """,
        (limit,),
    )
    return [(int(r["ward_id"]), int(r["n"])) for r in rows]


def fetch_daily_counts(days: int = 14) -> list[tuple[date, int]]:
    rows = _query_all(
        """
        SELECT DATE(created_at AT TIME ZONE 'UTC') AS d, COUNT(*) AS n
        FROM mymla_complaints
        WHERE created_at >= (NOW() - %s::interval)
        GROUP BY 1 ORDER BY 1 ASC
        """,
        (f"{int(days)} days",),
    )
    found = {r["d"]: int(r["n"]) for r in rows}
    today = datetime.now(timezone.utc).date()
    series: list[tuple[date, int]] = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        series.append((d, found.get(d, 0)))
    return series


def fetch_citizen_count() -> int:
    row = _query_one("SELECT COUNT(*) AS n FROM mymla_users")
    return int(row["n"]) if row else 0


def fetch_resolved_last_n_days(days: int = 7) -> int:
    row = _query_one(
        """
        SELECT COUNT(*) AS n
        FROM mymla_complaints
        WHERE status = 'RESOLVED' AND created_at >= (NOW() - %s::interval)
        """,
        (f"{int(days)} days",),
    )
    return int(row["n"]) if row else 0


# ─── Layout shell ───────────────────────────────────────────────────────────

_CSS = f"""
:root {{
  --teal: {TEAL};
  --teal-dark: {TEAL_DARK};
  --teal-deep: {TEAL_DEEP};
  --ivory: {IVORY};
  --ivory-page: {IVORY_PAGE};
  --gold: {GOLD};
  --text: {TEXT};
  --text-muted: {TEXT_MUTED};
  --border: {BORDER};
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  background: var(--ivory-page);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}

/* ─── Layout ───────────────────────────────────────────────────────────── */
.layout {{ display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }}

.sidebar {{
  background: var(--teal);
  color: var(--ivory);
  padding: 28px 0;
  border-right: 1px solid var(--teal-deep);
  position: sticky; top: 0; height: 100vh; overflow-y: auto;
}}
.brand {{ text-align: center; padding: 0 20px 24px; border-bottom: 1px solid rgba(245,241,232,0.12); }}
.brand img {{ width: 96px; height: 96px; border-radius: 50%; display: block; margin: 0 auto 12px; }}
.brand .name {{
  font-size: 14px; letter-spacing: 2.2px; text-transform: uppercase;
  font-weight: 600; color: var(--ivory);
}}
.brand .tagline {{
  font-size: 11px; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--gold); margin-top: 4px;
}}
.nav {{ margin-top: 16px; }}
.nav a {{
  display: block; padding: 11px 24px;
  color: rgba(245,241,232,0.78);
  text-decoration: none; font-size: 13px;
  border-left: 3px solid transparent;
}}
.nav a:hover {{ background: var(--teal-dark); color: var(--ivory); }}
.nav a.active {{
  background: var(--teal-dark); color: var(--ivory);
  border-left-color: var(--gold);
}}
.nav a.disabled {{ color: rgba(245,241,232,0.32); cursor: default; pointer-events: none; }}
.nav .badge-soon {{
  float: right; font-size: 9px; letter-spacing: 1px;
  background: rgba(245,241,232,0.08); color: var(--gold);
  padding: 2px 6px; border-radius: 3px; margin-top: 2px;
}}

.main {{ padding: 32px 40px 60px; }}
.topbar {{
  display: flex; align-items: baseline; justify-content: space-between;
  margin-bottom: 28px; padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}}
.topbar h1 {{ font-size: 22px; margin: 0; color: var(--teal); font-weight: 600; letter-spacing: -0.2px; }}
.topbar .signed-in {{ color: var(--text-muted); font-size: 12px; }}
.topbar .signed-in b {{ color: var(--text); }}

/* ─── Cards & grids ──────────────────────────────────────────────────────── */
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
.kpi {{
  background: var(--ivory); border: 1px solid var(--border); padding: 18px 20px; border-radius: 4px;
  position: relative;
}}
.kpi::before {{
  content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 3px;
  background: var(--gold);
}}
.kpi .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px; color: var(--text-muted); }}
.kpi .value {{ font-size: 30px; font-weight: 600; color: var(--teal); margin-top: 6px; }}
.kpi .hint {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}

.row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
.row.full {{ grid-template-columns: 1fr; }}
.card {{
  background: var(--ivory); border: 1px solid var(--border); border-radius: 4px;
  padding: 20px 22px;
}}
.card h2 {{
  margin: 0 0 16px; font-size: 14px; text-transform: uppercase; letter-spacing: 1.3px;
  color: var(--teal); font-weight: 600;
}}
.card h2 .qualifier {{ color: var(--text-muted); text-transform: none; letter-spacing: 0;
  font-weight: 400; font-size: 12px; margin-left: 8px; }}
.empty {{ color: var(--text-muted); padding: 18px 0; font-style: italic; }}

/* ─── Tables ─────────────────────────────────────────────────────────────── */
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ padding: 10px 12px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--border); }}
th {{
  background: transparent; font-weight: 600; color: var(--teal);
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.1px;
}}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(11,78,86,0.025); }}

.ticket-id {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
  color: var(--teal-dark); }}
.muted {{ color: var(--text-muted); }}
.desc {{ max-width: 380px; color: var(--text); }}

.status {{
  padding: 3px 9px; border-radius: 3px; font-size: 10px; font-weight: 700;
  letter-spacing: 1.2px; text-transform: uppercase; display: inline-block;
}}
.status-OPEN        {{ background: #FFF1D6; color: #8B5A00; }}
.status-IN_PROGRESS {{ background: #D8E6F0; color: #0F4E78; }}
.status-RESOLVED    {{ background: #DCE9D6; color: #2F5B23; }}
.status-CLOSED      {{ background: #E3DECF; color: #5C4F2E; }}

/* ─── Filter bar ─────────────────────────────────────────────────────────── */
.filters {{ margin: 0 0 18px; font-size: 12px; display: flex; gap: 8px; flex-wrap: wrap; }}
.filters a {{
  padding: 6px 12px; border: 1px solid var(--border); border-radius: 3px;
  text-decoration: none; color: var(--text); background: var(--ivory);
  text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px;
}}
.filters a:hover {{ border-color: var(--gold); }}
.filters a.active {{ background: var(--teal); color: var(--ivory); border-color: var(--teal); }}
.filters a .n {{ opacity: 0.6; margin-left: 4px; font-weight: 400; }}

/* ─── Charts ─────────────────────────────────────────────────────────────── */
.bars {{ width: 100%; }}
.bars .row-bar {{ display: grid; grid-template-columns: 130px 1fr 50px;
  align-items: center; gap: 10px; padding: 5px 0; font-size: 12.5px; }}
.bars .label {{ color: var(--text); }}
.bars .track {{ background: rgba(11,78,86,0.07); height: 14px; border-radius: 2px;
  overflow: hidden; }}
.bars .fill {{ background: var(--teal); height: 100%; }}
.bars .n {{ color: var(--teal); font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }}

.sparkline-wrap {{ }}
.sparkline-axis {{
  display: grid; grid-template-columns: repeat(var(--cols, 14), 1fr); gap: 4px;
  margin-top: 10px; font-size: 10px; color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}}
.sparkline-axis span {{ text-align: center; }}

/* ─── Sidebar foot (sign out) ────────────────────────────────────────────── */
.sidebar-foot {{
  margin-top: 24px; padding: 16px 24px 0;
  border-top: 1px solid rgba(245,241,232,0.12);
}}
.sidebar-foot .signout {{
  color: rgba(245,241,232,0.6); font-size: 11px;
  text-transform: uppercase; letter-spacing: 1.4px;
  text-decoration: none;
}}
.sidebar-foot .signout:hover {{ color: var(--gold); }}

/* ─── Login page ─────────────────────────────────────────────────────────── */
.login-body {{
  margin: 0; min-height: 100vh; background: var(--teal);
  background-image:
    radial-gradient(ellipse at top, rgba(245,241,232,0.04) 0%, transparent 60%),
    radial-gradient(ellipse at bottom, rgba(5,43,48,0.6) 0%, transparent 60%);
  display: flex; align-items: center; justify-content: center;
  padding: 32px 16px;
  color: var(--text);
}}
.login-shell {{ width: 100%; max-width: 380px; }}
.login-card {{
  background: var(--ivory); border: 1px solid var(--border);
  border-radius: 4px; padding: 36px 32px 26px;
  position: relative;
}}
.login-card::before {{
  content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px;
  background: var(--gold);
}}
.login-brand {{ text-align: center; margin-bottom: 28px; }}
.login-brand img {{ width: 88px; height: 88px; border-radius: 50%; display: block; margin: 0 auto 14px; }}
.login-title {{
  font-size: 16px; font-weight: 600; color: var(--teal);
  letter-spacing: 2.4px; text-transform: uppercase;
}}
.login-subtitle {{
  font-size: 10.5px; color: var(--text-muted); letter-spacing: 1.6px;
  text-transform: uppercase; margin-top: 4px;
}}
.login-form {{ display: flex; flex-direction: column; gap: 14px; }}
.login-form label {{ display: flex; flex-direction: column; gap: 6px; }}
.login-form label span {{
  font-size: 10.5px; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 1.3px;
}}
.login-form input {{
  padding: 10px 12px; font-size: 14px; color: var(--text);
  background: #FFFDF8; border: 1px solid var(--border); border-radius: 3px;
  outline: none; font-family: inherit;
}}
.login-form input:focus {{ border-color: var(--teal); }}
.login-form button {{
  margin-top: 8px; padding: 11px 16px;
  background: var(--teal); color: var(--ivory);
  border: 1px solid var(--teal); border-radius: 3px;
  font-size: 12px; font-weight: 600; letter-spacing: 1.6px;
  text-transform: uppercase; cursor: pointer; font-family: inherit;
}}
.login-form button:hover {{ background: var(--teal-dark); }}
.login-error {{
  padding: 10px 12px; background: #FFE8E0; color: #8B2C18;
  border: 1px solid #E8B8A8; border-radius: 3px;
  font-size: 12.5px; margin-bottom: 4px;
}}
.login-footnote {{
  margin-top: 24px; text-align: center; font-size: 10.5px;
  color: var(--text-muted); letter-spacing: 1.1px; text-transform: uppercase;
}}

/* ─── Table responsive wrapper ───────────────────────────────────────────── */
.table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
.table-scroll table {{ min-width: 720px; }}

/* ─── Tablet ─────────────────────────────────────────────────────────────── */
@media (max-width: 960px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .row {{ grid-template-columns: 1fr; }}
}}

/* ─── Mobile ─────────────────────────────────────────────────────────────── */
@media (max-width: 720px) {{
  .layout {{ grid-template-columns: 1fr; grid-template-rows: auto 1fr; }}
  .sidebar {{
    position: static; height: auto; padding: 14px 16px;
    border-right: none; border-bottom: 1px solid var(--teal-deep);
  }}
  .sidebar .brand {{
    display: flex; align-items: center; gap: 12px;
    text-align: left; padding: 0 0 12px;
    border-bottom: 1px solid rgba(245,241,232,0.12);
  }}
  .sidebar .brand img {{ width: 40px; height: 40px; margin: 0; }}
  .sidebar .brand .name {{ font-size: 13px; letter-spacing: 1.8px; margin: 0; flex: 1; }}
  .sidebar .brand .tagline {{ display: none; }}
  .nav {{
    margin-top: 10px; display: flex; gap: 4px;
    overflow-x: auto; -webkit-overflow-scrolling: touch;
  }}
  .nav a {{
    padding: 8px 14px; border-left: none; border-bottom: 3px solid transparent;
    white-space: nowrap; font-size: 13px;
  }}
  .nav a.active {{ border-left-color: transparent; border-bottom-color: var(--gold); }}
  .nav a.disabled {{ display: none; }}    /* hide SOON items on mobile to reduce noise */
  .nav .badge-soon {{ display: none; }}

  .main {{ padding: 20px 16px 40px; }}
  .topbar {{ flex-direction: column; align-items: flex-start; gap: 6px; margin-bottom: 20px; }}
  .topbar h1 {{ font-size: 19px; }}

  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 20px; }}
  .kpi {{ padding: 14px 14px 14px 18px; }}
  .kpi .value {{ font-size: 24px; }}

  .card {{ padding: 16px 16px; }}
  .card h2 {{ font-size: 12.5px; }}
  .card h2 .qualifier {{ display: block; margin-left: 0; margin-top: 2px; }}

  .bars .row-bar {{ grid-template-columns: 110px 1fr 40px; gap: 8px; font-size: 12px; }}

  .filters {{ gap: 6px; }}
  .filters a {{ padding: 5px 9px; font-size: 10.5px; }}
}}

/* ─── Very narrow phones ─────────────────────────────────────────────────── */
@media (max-width: 380px) {{
  .kpi-grid {{ grid-template-columns: 1fr; }}
  .bars .row-bar {{ grid-template-columns: 90px 1fr 32px; }}
}}
"""


_NAV_ITEMS = [
    ("home", "/admin/", "Home", False),
    ("tickets", "/admin/tickets", "Tickets", False),
    ("meetings", "#", "Meetings", True),
    ("events", "#", "Events", True),
    ("schedule", "#", "Schedule", True),
    ("location", "#", "Location", True),
]


def _sidebar(active: str) -> str:
    items: list[str] = []
    for key, href, label, disabled in _NAV_ITEMS:
        classes = ["active"] if key == active else []
        if disabled:
            classes.append("disabled")
        cls = f' class="{" ".join(classes)}"' if classes else ""
        suffix = '<span class="badge-soon">SOON</span>' if disabled else ""
        items.append(f'<a href="{_esc(href)}"{cls}>{_esc(label)}{suffix}</a>')
    return f"""
<aside class="sidebar">
  <div class="brand">
    <img src="/assets/mymla_profile_512.png" alt="MyMLA seal" />
    <div class="name">MyMLA</div>
    <div class="tagline">Office Console</div>
  </div>
  <nav class="nav">
    {''.join(items)}
  </nav>
  <div class="sidebar-foot">
    <a href="/admin/logout" class="signout">Sign out</a>
  </div>
</aside>
"""


def _layout(title: str, page_title: str, body: str, active: str, signed_in_as: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MyMLA — {_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="layout">
  {_sidebar(active)}
  <main class="main">
    <div class="topbar">
      <h1>{_esc(page_title)}</h1>
      <div class="signed-in">Signed in as <b>{_esc(signed_in_as)}</b></div>
    </div>
    {body}
  </main>
</div>
</body></html>"""


# ─── Chart helpers (inline SVG / CSS) ───────────────────────────────────────

def _bars(rows: list[tuple[str, int]], empty_msg: str = "No data yet.") -> str:
    if not rows:
        return f'<div class="empty">{_esc(empty_msg)}</div>'
    max_n = max(n for _, n in rows) or 1
    parts: list[str] = ['<div class="bars">']
    for label, n in rows:
        pct = round(100 * n / max_n)
        parts.append(
            '<div class="row-bar">'
            f'<div class="label">{_esc(label)}</div>'
            f'<div class="track"><div class="fill" style="width: {pct}%"></div></div>'
            f'<div class="n">{_esc(n)}</div>'
            '</div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _sparkline(series: list[tuple[date, int]], width: int = 560, height: int = 80) -> str:
    if not series:
        return '<div class="empty">No tickets in the window.</div>'
    n = len(series)
    max_v = max((v for _, v in series), default=0) or 1
    bar_w = (width - (n - 1) * 4) / n
    bars: list[str] = []
    for i, (_d, v) in enumerate(series):
        x = i * (bar_w + 4)
        h = (v / max_v) * (height - 8) if max_v else 0
        y = height - h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'rx="1" fill="{TEAL}" opacity="{0.45 + 0.55 * (v / max_v):.2f}"/>'
        )
    axis_labels = "".join(
        f"<span>{d.strftime('%d')}</span>" for d, _ in series
    )
    return (
        '<div class="sparkline-wrap">'
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(bars)}'
        '</svg>'
        f'<div class="sparkline-axis" style="--cols:{n}">{axis_labels}</div>'
        '</div>'
    )


# ─── Pages ──────────────────────────────────────────────────────────────────

def _kpi(label: str, value: Any, hint: str = "") -> str:
    return (
        f'<div class="kpi">'
        f'<div class="label">{_esc(label)}</div>'
        f'<div class="value">{_esc(value)}</div>'
        f'<div class="hint">{_esc(hint)}</div>'
        '</div>'
    )


def render_home(signed_in_as: str) -> str:
    counts = fetch_counts_by_status()
    open_n = counts.get("OPEN", 0)
    in_progress_n = counts.get("IN_PROGRESS", 0)
    resolved_7d = fetch_resolved_last_n_days(7)
    citizens = fetch_citizen_count()

    by_cat = fetch_counts_by_category(30)
    by_ward_raw = fetch_top_wards(5)
    by_ward = [
        (f"Ward {wid} — {W.ward_name(wid, 'eng') or '?'}", n) for wid, n in by_ward_raw
    ]
    daily = fetch_daily_counts(14)
    latest = fetch_tickets(status_filter="ALL", limit=5)

    kpis = "".join([
        _kpi("Open tickets", open_n, "Awaiting first action"),
        _kpi("In progress", in_progress_n, "Office working on it"),
        _kpi("Resolved (7d)", resolved_7d, "Closed last 7 days"),
        _kpi("Citizens onboarded", citizens, "Unique phone numbers"),
    ])

    by_cat_chart = _bars(by_cat, "No tickets in the last 30 days.")
    by_ward_chart = _bars(by_ward, "No tickets with a ward yet.")
    sparkline_svg = _sparkline(daily)

    if latest:
        latest_rows: list[str] = []
        for r in latest:
            ward_label = f"Ward {r.get('ward_id')}" if r.get("ward_id") is not None else "—"
            status_value = (r.get("status") or "OPEN").upper()
            latest_rows.append(
                "<tr>"
                f'<td class="ticket-id">{_esc(r.get("ticket_id"))}</td>'
                f'<td>{_fmt_dt(r.get("created_at"))}</td>'
                f'<td>{_esc(ward_label)}</td>'
                f'<td>{_esc(r.get("category"))}</td>'
                f'<td><span class="status status-{_esc(status_value)}">{_esc(status_value)}</span></td>'
                "</tr>"
            )
        latest_table = (
            '<table><thead><tr>'
            '<th>Ticket</th><th>When</th><th>Ward</th>'
            '<th>Category</th><th>Status</th>'
            '</tr></thead><tbody>'
            + "".join(latest_rows)
            + '</tbody></table>'
        )
    else:
        latest_table = '<div class="empty">No tickets filed yet.</div>'

    body = f"""
<div class="kpi-grid">{kpis}</div>

<div class="row">
  <div class="card">
    <h2>Tickets by category <span class="qualifier">last 30 days</span></h2>
    {by_cat_chart}
  </div>
  <div class="card">
    <h2>Top wards by volume <span class="qualifier">all time</span></h2>
    {by_ward_chart}
  </div>
</div>

<div class="row full">
  <div class="card">
    <h2>Tickets per day <span class="qualifier">last 14 days</span></h2>
    {sparkline_svg}
  </div>
</div>

<div class="row full">
  <div class="card">
    <h2>Latest tickets <span class="qualifier">most recent 5</span></h2>
    {latest_table}
  </div>
</div>
"""
    return _layout("Dashboard", "Dashboard", body, active="home", signed_in_as=signed_in_as)


def _filter_bar(active: str, counts: dict[str, int]) -> str:
    options = [
        ("ALL", "All"), ("OPEN", "Open"), ("IN_PROGRESS", "In progress"),
        ("RESOLVED", "Resolved"), ("CLOSED", "Closed"),
    ]
    parts: list[str] = []
    for key, label in options:
        count = sum(counts.values()) if key == "ALL" else counts.get(key, 0)
        cls = "active" if active.upper() == key else ""
        parts.append(
            f'<a class="{cls}" href="/admin/tickets?status={key}">'
            f'{_esc(label)}<span class="n">{count}</span></a>'
        )
    return '<div class="filters">' + "".join(parts) + "</div>"


def _ticket_row(row: dict[str, Any]) -> str:
    description = _truncate(row.get("description_text"))
    voice = "🎙" if row.get("description_voice_url") else ""
    images = row.get("image_media_ids") or []
    images_label = f"📷×{len(images)}" if images else ""
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


def render_tickets(rows: list[dict[str, Any]], status_filter: str,
                   counts: dict[str, int], signed_in_as: str) -> str:
    header = "<tr>" + "".join(f"<th>{c}</th>" for c in (
        "Ticket", "Created", "Ward / Booth", "Category", "Description",
        "Media", "Phone", "Status",
    )) + "</tr>"

    if rows:
        body = (
            '<div class="table-scroll"><table>'
            + header + "".join(_ticket_row(r) for r in rows)
            + '</table></div>'
        )
    else:
        body = '<div class="empty">No tickets match this filter.</div>'

    inner = f"""
{_filter_bar(status_filter, counts)}
<div class="card">{body}</div>
"""
    return _layout("Tickets", "Citizen complaints", inner,
                   active="tickets", signed_in_as=signed_in_as)


# ─── Login page rendering ───────────────────────────────────────────────────

def render_login(error: Optional[str] = None, next_path: str = "/admin/") -> str:
    err_block = (
        f'<div class="login-error">{_esc(error)}</div>' if error else ""
    )
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MyMLA — Sign in</title>
<style>{_CSS}</style>
</head>
<body class="login-body">
<main class="login-shell">
  <div class="login-card">
    <div class="login-brand">
      <img src="/assets/mymla_profile_512.png" alt="MyMLA seal" />
      <div class="login-title">MyMLA</div>
      <div class="login-subtitle">Office Console</div>
    </div>
    <form method="post" action="/admin/login" class="login-form">
      <input type="hidden" name="next" value="{_esc(next_path)}" />
      {err_block}
      <label>
        <span>Username</span>
        <input name="username" autocomplete="username" autofocus required />
      </label>
      <label>
        <span>Password</span>
        <input name="password" type="password" autocomplete="current-password" required />
      </label>
      <button type="submit">Sign in</button>
    </form>
    <div class="login-footnote">Authorised access only · MyMLA Constituency Office</div>
  </div>
</main>
</body></html>"""


# ─── Routes ─────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def admin_login_form(request: Request, error: Optional[str] = None,
                     next: str = "/admin/") -> Any:
    expected_user, expected_pass = _admin_credentials()
    if not expected_user or not expected_pass:
        raise HTTPException(status_code=503, detail="admin not configured")
    # If already signed in, skip straight to the dashboard.
    if _read_session(request.cookies.get(_COOKIE_NAME)):
        return RedirectResponse(url=next or "/admin/", status_code=303)
    return HTMLResponse(render_login(error=error, next_path=next or "/admin/"))


@router.post("/login")
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin/"),
) -> Response:
    expected_user, expected_pass = _admin_credentials()
    if not expected_user or not expected_pass:
        raise HTTPException(status_code=503, detail="admin not configured")
    if not _credentials_match(username, password):
        # Re-render the form with an error; keep username out of the cookie.
        return HTMLResponse(
            render_login(error="Invalid username or password.",
                         next_path=next or "/admin/"),
            status_code=401,
        )
    # Constrain `next` to internal paths only.
    target = next if next and next.startswith("/admin") else "/admin/"
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=_sign_session(username),
        max_age=_SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


@router.get("/logout")
def admin_logout() -> Response:
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(_COOKIE_NAME, path="/")
    return response


@router.get("/", response_class=HTMLResponse)
def admin_home(_user: str = Depends(_require_admin)) -> str:
    return render_home(signed_in_as=_user)


@router.get("/tickets", response_class=HTMLResponse)
def admin_tickets(
    status: str = Query("OPEN"),
    ward_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    _user: str = Depends(_require_admin),
) -> str:
    rows = fetch_tickets(status_filter=status, ward_id=ward_id, limit=limit)
    counts = fetch_counts_by_status()
    return render_tickets(rows, status, counts, signed_in_as=_user)
