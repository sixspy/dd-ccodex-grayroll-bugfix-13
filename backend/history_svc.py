"""变更历史。"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from audit_svc import write_audit
from auth import current_user, require_writer
from db import connect
from locks import acquire, release
from timeutil import UNIT, is_millis, seconds_of

router = APIRouter(prefix="/api/history", tags=["history"])
REFRESH_LOCK = "history-refresh"


class RefreshIn(BaseModel):
    session: str = ""


def _serialize(row: dict) -> dict:
    """历史行：created_at 一律按秒出，毫秒错位折回秒并标注。"""
    row = dict(row)
    raw = row.get("created_at")
    row["created_at"] = seconds_of(raw)
    row["created_at_unit"] = UNIT
    row["unit_misaligned"] = is_millis(raw)
    return row


@router.get("")
def list_history(authorization: str | None = Header(default=None), limit: int = 100):
    current_user(authorization)
    with connect() as conn:
        rows = [
            _serialize(r)
            for r in conn.execute(
                """
                SELECT h.*, f.key AS flag_key, e.code AS env_code
                FROM change_history h
                LEFT JOIN flags f ON f.id=h.flag_id
                LEFT JOIN environments e ON e.id=h.env_id
                ORDER BY h.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        body = {
            "items": rows,
            "unit": UNIT,
            # 时序复核：有任何毫秒错位即 aligned=False
            "timeline": {
                "unit": UNIT,
                "aligned": not any(r["unit_misaligned"] for r in rows),
                "mismatched": sum(1 for r in rows if r["unit_misaligned"]),
            },
        }
    return body


def _apply_refresh(conn, session: str) -> int:
    """胜方正式改：把错位历史行折回秒并记审计。返回修正行数。"""
    rows = conn.execute(
        "SELECT id, created_at FROM change_history WHERE created_at >= ?", (1e11,)
    ).fetchall()
    for r in rows:
        conn.execute(
            "UPDATE change_history SET created_at=created_at/1000.0 WHERE id=?", (r["id"],)
        )
    write_audit(
        conn,
        "system",
        "history_refresh",
        "change_history",
        None,
        f"session={session} fixed={len(rows)}",
    )
    return len(rows)


@router.post("/refresh")
def refresh_history(body: RefreshIn, authorization: str | None = Header(default=None)):
    """历史刷新互斥：双请求抢 `history-refresh`，败方 409 且零正式改。"""
    user = current_user(authorization)
    require_writer(user)
    session = (body.session or user["username"]).strip()
    holder = session
    with connect() as conn:
        acquire(conn, REFRESH_LOCK, holder)  # 争用败方在此 409 + 留痕
        try:
            fixed = _apply_refresh(conn, session)
            conn.commit()
            return {"mode": "official", "session": session, "fixed": fixed}
        finally:
            release(conn, REFRESH_LOCK, holder)
            conn.commit()
