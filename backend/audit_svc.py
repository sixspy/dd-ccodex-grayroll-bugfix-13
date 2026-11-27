"""审计与变更历史写入。"""
from __future__ import annotations

import time

from fastapi import APIRouter, Header

from auth import current_user
from db import connect
from timeutil import UNIT, is_millis, seconds_of

router = APIRouter(prefix="/api/audit", tags=["audit"])


def write_audit(
    conn, actor: str, action: str, entity: str, entity_id: int | None, detail: str,
    at: float | None = None,
) -> None:
    conn.execute(
        "INSERT INTO audit_log(actor, action, entity, entity_id, detail, created_at) VALUES(?,?,?,?,?,?)",
        (actor, action, entity, entity_id, detail, time.time() if at is None else at),
    )


def write_history(
    conn, actor: str, action: str, detail: str, flag_id: int | None = None, env_id: int | None = None,
    at: float | None = None,
) -> None:
    conn.execute(
        "INSERT INTO change_history(flag_id, env_id, action, detail, actor, created_at) VALUES(?,?,?,?,?,?)",
        (flag_id, env_id, action, detail, actor, time.time() if at is None else at),
    )


@router.get("")
def list_audit(authorization: str | None = Header(default=None), limit: int = 80):
    current_user(authorization)
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    items = []
    for r in rows:
        r = dict(r)
        raw = r.get("created_at")
        r["created_at"] = seconds_of(raw)
        r["created_at_unit"] = UNIT
        r["unit_misaligned"] = is_millis(raw)
        items.append(r)
    return {"items": items, "unit": UNIT}
