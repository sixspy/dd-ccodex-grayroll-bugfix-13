"""行锁与争用痕（嵌进发布/熔断主写路径）。"""
from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException

from auth import current_user
from db import connect

router = APIRouter(prefix="/api/locks", tags=["locks"])
TTL = 20.0


def acquire(conn, key: str, holder: str) -> None:
    """原子抢锁：条件 upsert 一步完成，避免 SELECT-then-INSERT 的 TOCTOU 双成。

    仅当「无人持有 / 已过期 / 本持有者重入」时 upsert 才会改行，rowcount 即
    是否抢到。行锁与竞态检查在同一写语句内由 SQLite 串行化，多个会话并发
    请求至多一个 rowcount=1。
    """
    now = time.time()
    cur = conn.execute(
        "INSERT INTO row_locks(lock_key, holder, expires_at) VALUES(?,?,?) "
        "ON CONFLICT(lock_key) DO UPDATE SET holder=excluded.holder, expires_at=excluded.expires_at "
        "WHERE row_locks.holder=? OR row_locks.expires_at<=?",
        (key, holder, now + TTL, holder, now),
    )
    acquired = cur.rowcount > 0
    # 必须提交：SQLite 下未提交的锁对其他会话不可见 → 双成
    conn.commit()
    if acquired:
        return
    # 抢锁失败：读当前持有者，留争用痕，败方零正式改
    row = conn.execute(
        "SELECT holder FROM row_locks WHERE lock_key=?", (key,)
    ).fetchone()
    winner = row["holder"] if row else "unknown"
    conn.execute(
        "INSERT INTO contention_marks(lock_key, loser, winner, created_at) VALUES(?,?,?,?)",
        (key, holder, winner, now),
    )
    conn.commit()
    raise HTTPException(409, detail="发布锁争用，请稍后重试")


def release(conn, key: str, holder: str) -> None:
    conn.execute("DELETE FROM row_locks WHERE lock_key=? AND holder=?", (key, holder))


@router.get("/contention")
def list_contention(authorization: str | None = Header(default=None), limit: int = 40):
    current_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM contention_marks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"items": [dict(r) for r in rows]}
