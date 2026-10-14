"""变更检测基准（题面任务 3 对账）：受控多轮样本走 SnapshotPipeline 生产路径。

用例文件 bench/fixtures/change_cases/cases.json：
- rounds：逐轮条目（离线构造，example.invalid 域名 + 假名白名单，K8）；
- expect：该轮期望事件（kind + url 必填，detail_contains 可选）；
- 期望之外的事件即误报（no_false_positive_rule）。

与生产编排同口径：begin_round → ingest（逐源）→ close_round(seen_urls 并集)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ajm.config import AppConfig, EventKind, SourceId
from ajm.models import RawItem
from ajm.storage import Storage
from snapshot import SnapshotPipeline

CASES_PATH = (
    Path(__file__).resolve().parents[2] / "bench" / "fixtures" / "change_cases" / "cases.json"
)


@dataclass(slots=True)
class ChangeReport:
    """变更检测报告：期望事件检出数、误报数、漏报明细。"""

    expected_total: int = 0
    detected: int = 0
    missed: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missed and not self.false_positives

    def summary(self) -> str:
        return (
            f"expected={self.expected_total} detected={self.detected} "
            f"missed={len(self.missed)} false_positives={len(self.false_positives)}"
        )


def _run_case(case: dict) -> ChangeReport:
    report = ChangeReport()
    storage = Storage(":memory:")
    try:
        pipeline = SnapshotPipeline(storage, AppConfig())
        for round_no, rnd in enumerate(case["rounds"], start=1):
            storage.begin_round()
            by_source: dict[SourceId, list[RawItem]] = {}
            for it in rnd["items"]:
                item = RawItem(
                    source=SourceId(it["source"]),
                    url=it["url"],
                    title=it["title"],
                    published_on=(
                        date.fromisoformat(it["published_on"]) if it.get("published_on") else None
                    ),
                    extra=it.get("extra") or {},
                )
                by_source.setdefault(item.source, []).append(item)
            events = []
            seen: set[str] = set()
            for source, items in by_source.items():
                seen.update(i.url for i in items)
                events.extend(pipeline.ingest(source, items, bodies=_bodies(rnd["items"])))
            events.extend(pipeline.close_round(seen))

            expected = [
                (
                    EventKind(e["kind"]).value,
                    e["url"],
                    e.get("detail_contains", ""),
                )
                for e in rnd["expect"]
            ]
            actual = [
                (ev.kind.value, ev.url, _detail_text(ev.detail)) for ev in events
            ]
            report.expected_total += len(expected)
            # 逐个消费期望项：同一实际事件只能命中一个期望（否则重复匹配
            # 会把已检出的期望事件再算一次误报）。
            remaining = list(expected)
            for exp in expected:
                if exp not in remaining or not _match(remaining, exp):
                    report.missed.append(f"{case['name']} round{round_no}: {exp}")
                    continue
                remaining.remove(exp)
                report.detected += 1
            # 未被任何期望消费的实际事件 = 误报
            for act in actual:
                if _match(remaining, act):
                    report.false_positives.append(f"{case['name']} round{round_no}: {act}")
    finally:
        storage.close()
    return report


def _bodies(items: list[dict]) -> dict[str, str]:
    return {i["url"]: i["body_text"] for i in items if i.get("body_text")}


def _detail_text(detail: dict) -> str:
    return json.dumps(detail, ensure_ascii=False)


def _match(pool: list[tuple], target: tuple) -> bool:
    """kind+url 必须相等；detail_contains 为期望时对 detail 文本做子串断言。"""
    kind, url, contains = target
    for a_kind, a_url, a_detail in pool:
        if a_kind != kind or a_url != url:
            continue
        if not contains or contains in a_detail:
            return True
    return False


def run_change_cases() -> list[tuple[str, ChangeReport]]:
    """跑全部变更检测用例，返回 (用例名, 报告) 列表。"""
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return [(case["name"], _run_case(case)) for case in data["cases"]]
