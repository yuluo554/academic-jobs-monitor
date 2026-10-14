"""共享视图层（M5 双形态对账的单一事实源）。

CLI（jobsctl timeline/feed/bench 的打印）与 Web 面板（webapp.app 路由）都从这里
取数：同一编排函数（storage 查询 + subscribe.match_events + bench 报告对象），
双入口不允许各自实现一份查询/判定逻辑。

- list_snapshots / timeline_events / feed_preview：快照库驱动（本地 cache/ajm.sqlite3）；
- bench_report：直接复用 bench.run_truth / run_change_cases 报告对象
  （webapp 不重复实现判定口径，见 HANDOFF-M4 备忘）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ajm.config import AppConfig
from ajm.models import ChangeEvent
from ajm.storage import Storage
from subscribe import match_events

_FIELD_LABELS = {
    "position": "岗位",
    "organization": "单位",
    "discipline": "学科方向",
    "compensation": "待遇",
    "deadline": "截止日期",
}


@dataclass(slots=True)
class SnapshotRow:
    """条目列表一行：快照元数据 + 抽取字段（status 门控展示，K6）。"""

    url: str
    source: str
    title: str
    first_round: int
    last_seen_round: int
    removed_since: int | None
    updated_at: str
    fields: dict[str, dict]  # 字段名 → {status, value, candidates, evidence}

    def field_display(self, name: str) -> str:
        """字段出镜文本：verified 值、ambiguous 候选集、pending 不臆测（K5/K6）。"""
        f = self.fields.get(name) or {}
        if f.get("candidates"):
            return " / ".join(f["candidates"]) + "（待判定）"
        return f.get("value") or "—"


@dataclass(slots=True)
class EventRow:
    """时间线一行：事件 + 匹配到的标题（快照库可查到时）。"""

    kind: str
    url: str
    source: str
    round: int
    detail: dict[str, str]
    detected_at: str
    title: str = ""


def list_snapshots(cfg: AppConfig) -> list[SnapshotRow]:
    """条目列表（快照库全量，updated_at 倒序）；库为空返回空列表。"""
    storage = Storage(cfg.db_path)
    try:
        rows = storage._conn.execute(
            "SELECT * FROM snapshots ORDER BY updated_at DESC, url ASC"
        ).fetchall()
        out = []
        for row in rows:
            extracted = (
                json.loads(row["extracted_json"]) if row["extracted_json"] else None
            )
            fields = (extracted or {}).get("fields", {})
            out.append(
                SnapshotRow(
                    url=row["url"],
                    source=row["source"],
                    title=row["title"],
                    first_round=int(row["first_round"]),
                    last_seen_round=int(row["last_seen_round"]),
                    removed_since=(
                        int(row["removed_since"]) if row["removed_since"] else None
                    ),
                    updated_at=row["updated_at"],
                    fields=fields,
                )
            )
        return out
    finally:
        storage.close()


def timeline_events(cfg: AppConfig, url: str = "") -> list[EventRow]:
    """变更时间线：缺省最近一轮，--url/参数指定条目时出全历史（与 CLI 同语义）。"""
    storage = Storage(cfg.db_path)
    try:
        if url:
            events = storage.events_for_url(url)
        else:
            round_no = storage.current_round()
            events = storage.events_for_round(round_no) if round_no else []
        titles = storage.all_titles()
    finally:
        storage.close()
    return [
        EventRow(
            kind=str(ev.kind),
            url=ev.url,
            source=str(ev.source),
            round=ev.round,
            detail=ev.detail,
            detected_at=ev.detected_at.isoformat(),
            title=titles.get(ev.url, ""),
        )
        for ev in events
    ]


def feed_preview(
    cfg: AppConfig, url: str = ""
) -> tuple[dict[str, list[ChangeEvent]], dict[str, str]]:
    """订阅预览：复用 subscribe.match_events（与 jobsctl feed 同一纯函数）。

    返回 ({规则名: [命中事件…]}, titles)；订阅文件未配置时第一项为空 dict。
    """
    from subscribe import SubscriptionConfig

    sub = SubscriptionConfig.from_file(cfg.subscribe_file)
    storage = Storage(cfg.db_path)
    try:
        if url:
            events = storage.events_for_url(url)
        else:
            round_no = storage.current_round()
            events = storage.events_for_round(round_no) if round_no else []
        titles = storage.all_titles()
    finally:
        storage.close()
    return match_events(sub, events, titles), titles


def bench_report() -> dict:
    """基准报告（结构化 dict，webapp 基准页直接渲染；判定不在这里重复实现）。

    CLI 形态 = jobsctl bench 的打印；面板形态 = 本函数渲染。三方对账以
    report 数字为准（CLI exit 1 是当前诚实扣分项，对账测试不断言 exit==0）。
    """
    from bench.change_cases import run_change_cases
    from bench.truth import run_truth

    truth = run_truth()
    changes = [
        {"name": name, "report": change_report.summary(), "ok": change_report.ok}
        for name, change_report in run_change_cases()
    ]
    total = sum(s.total for s in truth.fields.values())
    correct = sum(s.correct for s in truth.fields.values())
    return {
        "fields": truth.field_scores(),
        "field_labels": _FIELD_LABELS,
        "overall": {"correct": correct, "total": total},
        "classification": {
            "correct": truth.classified_correct,
            "total": truth.classified_total,
        },
        "failures": list(truth.failures),
        "change_cases": changes,
        "passed": not truth.failures and all(c["ok"] for c in changes),
    }
