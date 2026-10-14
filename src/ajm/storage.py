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

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
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
    ) -> bool:
        """UPSERT 快照条目；返回是否为新条目（round_no == first_round 即新增）。"""
        existing = self._conn.execute(
            "SELECT first_round, content_hash FROM snapshots WHERE url = ?",
            (url,),
        ).fetchone()
        if existing is None:
            self._conn.execute(
                "INSERT INTO snapshots(url, source, title, content_hash, "
                "first_round, last_seen_round, extracted_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (url, str(source), title, content_hash, round_no, round_no, extracted_json),
            )
            self._conn.commit()
            return True
        self._conn.execute(
            "UPDATE snapshots SET last_seen_round = ?, title = ?, content_hash = ?, "
            "extracted_json = ?, updated_at = datetime('now') WHERE url = ?",
            (round_no, title, content_hash, extracted_json, url),
        )
        self._conn.commit()
        return False

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
