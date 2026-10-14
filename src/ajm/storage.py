"""SQLite 快照库接口。

持久快照与变更历史逐轮累积（题面任务 3）：同一 URL 可查询任意变更时间线。
仅存公告元数据与抽取字段，不存整页镜像（合规红线，data/README.md 缓存边界）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import EventKind, SourceId
from .models import ChangeEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot_rounds (
    round       INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    url             TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    title           TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    first_round     INTEGER NOT NULL,
    last_seen_round INTEGER NOT NULL,
    -- 删除去抖（K4，N=3）：首轮缺失轮次；NULL=未缺失。
    -- 连续缺失达 N 轮产出 ANNOUNCEMENT_REMOVED；期间复现则清空（记 missed_then_reappeared 事件）。
    removed_since   INTEGER,
    extracted_json  TEXT,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    url         TEXT NOT NULL,
    source      TEXT NOT NULL,
    round       INTEGER NOT NULL,
    detail_json TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_url ON events(url);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
"""


class Storage:
    """快照存储门面：建表、轮次登记、事件追加、时间线查询。"""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        if str(db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- 轮次 ----------------------------------------------------------------

    def current_round(self) -> int:
        row = self._conn.execute(
            "SELECT MAX(round) AS r FROM snapshot_rounds"
        ).fetchone()
        return int(row["r"] or 0)

    def begin_round(self) -> int:
        """开启新一轮抓取快照，返回轮次号。"""
        nxt = self.current_round() + 1
        self._conn.execute(
            "INSERT INTO snapshot_rounds(round, started_at) "
            "VALUES (?, datetime('now'))",
            (nxt,),
        )
        self._conn.commit()
        return nxt

    # -- 快照 ----------------------------------------------------------------

    def upsert_snapshot(
        self,
        *,
        url: str,
        source: SourceId,
        title: str,
        content_hash: str,
        round_no: int,
        extracted_json: str | None,
        removed_since: int | None = None,
    ) -> bool:
        """UPSERT 快照条目；返回是否为新条目（round_no == first_round 即新增）。"""
        existing = self._conn.execute(
            "SELECT first_round, content_hash FROM snapshots WHERE url = ?",
            (url,),
        ).fetchone()
        if existing is None:
            self._conn.execute(
                "INSERT INTO snapshots(url, source, title, content_hash, "
                "first_round, last_seen_round, removed_since, extracted_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (url, str(source), title, content_hash, round_no, round_no, None, extracted_json),
            )
            self._conn.commit()
            return True
        self._conn.execute(
            "UPDATE snapshots SET last_seen_round = ?, title = ?, content_hash = ?, "
            "removed_since = ?, extracted_json = ?, updated_at = datetime('now') WHERE url = ?",
            (round_no, title, content_hash, removed_since, extracted_json, url),
        )
        self._conn.commit()
        return False

    def mark_missing(self, url: str, round_no: int) -> int | None:
        """登记一轮缺失；返回当前连续缺失起始轮（首次缺失=本轮，已缺失=原值）。"""
        row = self._conn.execute(
            "SELECT removed_since FROM snapshots WHERE url = ?", (url,)
        ).fetchone()
        if row is None:
            return None
        current = row["removed_since"]
        if current is None:
            self._conn.execute(
                "UPDATE snapshots SET removed_since = ?, updated_at = datetime('now') "
                "WHERE url = ?",
                (round_no, url),
            )
            self._conn.commit()
            return round_no
        return int(current)

    def mark_reappeared(self, url: str, round_no: int) -> int | None:
        """缺失后复现：清空 removed_since，返回被清掉的起始轮（供 missed_then_reappeared 事件）。"""
        row = self._conn.execute(
            "SELECT removed_since FROM snapshots WHERE url = ?", (url,)
        ).fetchone()
        if row is None or row["removed_since"] is None:
            return None
        since = int(row["removed_since"])
        self._conn.execute(
            "UPDATE snapshots SET removed_since = NULL, last_seen_round = ?, "
            "updated_at = datetime('now') WHERE url = ?",
            (round_no, url),
        )
        self._conn.commit()
        return since

    def clear_removal(self, url: str) -> None:
        """删除事件产出后清标记（事件只发一次；时间线已持久）。"""
        self._conn.execute(
            "UPDATE snapshots SET removed_since = NULL, updated_at = datetime('now') "
            "WHERE url = ?",
            (url,),
        )
        self._conn.commit()

    def all_urls(self) -> list[str]:
        rows = self._conn.execute("SELECT url FROM snapshots").fetchall()
        return [r["url"] for r in rows]

    def removed_since_map(self) -> dict[str, int]:
        """当前处于缺失状态（removed_since 非空）的全部条目。"""
        rows = self._conn.execute(
            "SELECT url, removed_since FROM snapshots WHERE removed_since IS NOT NULL"
        ).fetchall()
        return {r["url"]: int(r["removed_since"]) for r in rows}

    def all_titles(self) -> dict[str, str]:
        """url → 最新标题（订阅匹配域之一；CLI feed 与 webapp 订阅预览共用）。"""
        rows = self._conn.execute("SELECT url, title FROM snapshots").fetchall()
        return {r["url"]: r["title"] for r in rows}

    def get_snapshot(self, url: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM snapshots WHERE url = ?", (url,)
        ).fetchone()

    # -- 事件 ----------------------------------------------------------------

    def append_event(self, event: ChangeEvent) -> None:
        import json

        self._conn.execute(
            "INSERT INTO events(kind, url, source, round, detail_json, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(event.kind),
                event.url,
                str(event.source),
                event.round,
                json.dumps(event.detail, ensure_ascii=False),
                event.detected_at.isoformat(),
            ),
        )
        self._conn.commit()

    def events_for_url(self, url: str) -> list[ChangeEvent]:
        """查询任意 URL 的变更时间线（题面任务 3 的可查询性要求）。"""
        import json

        rows = self._conn.execute(
            "SELECT * FROM events WHERE url = ? ORDER BY round ASC, id ASC",
            (url,),
        ).fetchall()
        return [
            ChangeEvent(
                kind=EventKind(r["kind"]),
                url=r["url"],
                source=SourceId(r["source"]),
                round=r["round"],
                detail=json.loads(r["detail_json"]),
            )
            for r in rows
        ]

    def events_for_round(self, round_no: int) -> list[ChangeEvent]:
        import json

        rows = self._conn.execute(
            "SELECT * FROM events WHERE round = ? ORDER BY source ASC, id ASC",
            (round_no,),
        ).fetchall()
        return [
            ChangeEvent(
                kind=EventKind(r["kind"]),
                url=r["url"],
                source=SourceId(r["source"]),
                round=r["round"],
                detail=json.loads(r["detail_json"]),
            )
            for r in rows
        ]
