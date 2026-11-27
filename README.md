# 灰度发布台（grayroll）

**所属领域：应用开发 · 子方向：全栈开发**

全栈产品：功能开关登记 → 环境绑定 → 人群圈选 → 灰度规则 → 发布生效 → 紧急熔断 → 单点覆盖 → 变更历史 → 在线求值。

## 骨架一句话

功能开关按环境配置灰度比例与人群，发布须版本落库才能生效，紧急熔断与变更历史同源。

## H3 切口候选（写路径互斥 · 须择一）

1. **发布生效**：同事务写入正式生效配置并升版本锁旧版，或只写影子发布草案、升正时原子落正式区（正式区升正前零改）。
2. **紧急熔断**：同事务立即写正式关闭并记变更，或影子紧急草案确认后原子熔断。
3. **人群绑定**：同事务写正式人群规则，或影子绑定草案升正。

正确性口径只能走甲乙中的一种且两边不得混用。

## 时间口径（BUGFIX-13）

库内一切时间戳（`created_at` / `published_at` / `updated_at`）皆为**秒**级 REAL。
所有列表面统一以 `created_at_unit="s"` 输出；前端一律经 `frontend/js/time.js`
的 `fmtTime()` 按秒换算，禁止把秒级戳直接塞进 `new Date()`（否则错到 1970）。

- 历史 / 审计 / 总览 / 发布 / 求值 / 开关各页同一口径。
- 发布复核 `GET /api/releases/review` 在同一读事务内跨表联查 `releases` 与
  `change_history`，逐对比较发布时间须同源同戳（`review_ok`、`matched`、`mismatched`）。
- 总览 `timeline_review.reviewed` 仅在线时间线对齐时为真；错位时间线不得当成已复核。

## 历史刷新互斥

`POST /api/history/refresh` 抢 `history-refresh` 行锁：并发时恰一方胜出并做正式
改，败方 409、只留争用痕（`/api/locks/contention`）、零正式改。`locks.acquire`
用条件 upsert 原子抢锁并提交，杜绝 SELECT-then-INSERT 的 TOCTOU 双成。

## 一键起环境

```bash
docker compose up -d --build
```

浏览器：http://localhost:11720

- `admin` / `admin123`（管理员）
- `writer` / `writer123`（发布员）
- `viewer` / `viewer123`（只读）

## 本地开发

```powershell
cd projects/17-grayroll
$env:PYTHONPATH="backend"
python -m uvicorn app:app --app-dir backend --reload --port 8020
python -m pytest
python scripts/count_loc.py
```

## 空桩

- 远程配置推送（`remote_push`）
- 实验平台桥接（`experiment_bridge`）

接口固定返回 501，题面可点名。
