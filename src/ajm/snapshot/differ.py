"""快照与变更检测：持久快照 + 字段级 diff 四类事件（题面任务 3，招牌模式）。

diff 纪律（plan/03 §三.4）：
- 字段级比较分类事件，content_hash 仅作"有无变更"初筛信号，不做一票否决；
- 哈希变了但所有可比较字段未变 → 仍记 CONTENT_CHANGED（detail 指明无字段级差异，
  事件不丢失）；
- 删除判定去抖 N=3（K4）：连续 N 轮缺失才产出 ANNOUNCEMENT_REMOVED；
  期间复现 → missed_then_reappeared 事件（M4 基准的"删除后复现"边界）。
"""

from __future__ import annotations

import logging

from ajm.config import AppConfig, EventKind, SourceId
from ajm.extract.engine import extract_posting, is_recruitment
from ajm.models import (
    ChangeEvent,
    ExtractedField,
    JobPosting,
    RawItem,
    strip_update_suffix,
)
from ajm.storage import Storage

logger = logging.getLogger(__name__)

# 字段级 diff 覆盖的字段（值相等比较；ambiguous 字段比 candidates 全集）。
_DIFF_FIELDS = ("position", "organization", "discipline", "compensation", "deadline")


def _field_repr(posting: JobPosting, name: str) -> str:
    """字段的 diff 表示：value 优先，ambiguous 用候选集。"""
    f = posting.fields()[name]
    if f.candidates:
        return "|".join(f.candidates)
    return f.value or ""


def _field_detail_changes(old: JobPosting, new: JobPosting) -> dict[str, str]:
    changes: dict[str, str] = {}
    for name in _DIFF_FIELDS:
        before, after = _field_repr(old, name), _field_repr(new, name)
        if before != after:
            changes[name] = f"{before} -> {after}"
    return changes


def _unextracted_posting(row) -> JobPosting:  # type: ignore[type-arg]
    """无抽取数据的历史行（防御路径，正常流程不触达）。"""
    return JobPosting(
        url=row["url"],
        source=SourceId(row["source"]),
        title=row["title"],
        published_on=None,
        position=ExtractedField.unextracted("position"),
        organization=ExtractedField.unextracted("organization"),
        discipline=ExtractedField.unextracted("discipline"),
        compensation=ExtractedField.unextracted("compensation"),
        deadline=ExtractedField.unextracted("deadline"),
    )


def _posting_from_row(row) -> JobPosting:  # type: ignore[type-arg]
    raw = row["extracted_json"]
    if raw:
        return JobPosting.from_json(raw)
    return _unextracted_posting(row)


class SnapshotPipeline:
    """一轮抓取条目 → 抽取 → 快照入库 → diff 事件产出。CLI 与 Web 共用（单一事实源）。"""

    def __init__(self, storage: Storage, config: AppConfig) -> None:
        self._st = storage
        self._config = config

    def ingest(
        self,
        source: SourceId,
        items: list[RawItem],
        bodies: dict[str, str] | None = None,
    ) -> list[ChangeEvent]:
        """单源单轮入库。bodies: url → 详情页正文（可选，无则只用标题）。

        抽取与分类纪律：
        - is_recruitment()=False（显式非招聘）→ 不入快照（nju/pku 首页通知）；
        - None（不可判定）→ 照常入库，字段走 pending 门控（不臆测，也不丢数据）。

        产出的事件经 append_event 持久化（时间线可查询的前提）。
        注意：缺失登记（去抖输入）不在此做——ingest 逐源调用，单源视角会把
        其他源的条目误判缺失（真实两轮实测踩过）；统一由 close_round 兜底登记。
        """
        self._st.current_round()  # 轮次由调用方 begin_round；此处仅校验已开启
        events: list[ChangeEvent] = []
        bodies = bodies or {}
        for item in items:
            if is_recruitment(item) is False:
                logger.info("skip non-recruitment notice: %s", item.url)
                continue
            posting = extract_posting(item, bodies.get(item.url, ""))
            events.extend(self._ingest_one(posting, self._st.current_round()))
        for ev in events:
            self._st.append_event(ev)
        return events

    def _ingest_one(self, posting: JobPosting, round_no: int) -> list[ChangeEvent]:
        events: list[ChangeEvent] = []
        row = self._st.get_snapshot(posting.url)
        if row is None:
            self._st.upsert_snapshot(
                url=posting.url,
                source=posting.source,
                title=posting.title,
                content_hash=posting.content_hash,
                round_no=round_no,
                extracted_json=posting.to_json(),
            )
            events.append(
                ChangeEvent(
                    kind=EventKind.NEW_POSTING,
                    url=posting.url,
                    source=posting.source,
                    round=round_no,
                    detail=self._new_posting_detail(posting),
                )
            )
            return events

        old = _posting_from_row(row)
        # 缺失后复现（去抖期间回来）→ 清 removed_since 并登记边界事件。
        reappeared_since = self._st.mark_reappeared(posting.url, round_no)
        if reappeared_since is not None:
            events.append(
                ChangeEvent(
                    kind=EventKind.CONTENT_CHANGED,
                    url=posting.url,
                    source=posting.source,
                    round=round_no,
                    detail={
                        "note": "missed_then_reappeared",
                        "missing_since_round": str(reappeared_since),
                    },
                )
            )

        changes = _field_detail_changes(old, posting)
        if changes:
            if "deadline" in changes:
                events.append(
                    ChangeEvent(
                        kind=EventKind.DEADLINE_CHANGED,
                        url=posting.url,
                        source=posting.source,
                        round=round_no,
                        detail={"deadline": changes["deadline"]},
                    )
                )
            others = {k: v for k, v in changes.items() if k != "deadline"}
            if others:
                events.append(
                    ChangeEvent(
                        kind=EventKind.CONTENT_CHANGED,
                        url=posting.url,
                        source=posting.source,
                        round=round_no,
                        detail=others,
                    )
                )
        elif posting.content_hash != row["content_hash"]:
            # 哈希变但字段级 diff 无差异：正文实质变更仍需登记
            #（字段抽取粒度之外的正文变化，事件不丢失）。
            events.append(
                ChangeEvent(
                    kind=EventKind.CONTENT_CHANGED,
                    url=posting.url,
                    source=posting.source,
                    round=round_no,
                    detail={"note": "hash_changed_no_field_diff"},
                )
            )

        self._st.upsert_snapshot(
            url=posting.url,
            source=posting.source,
            title=posting.title,
            content_hash=posting.content_hash,
            round_no=round_no,
            extracted_json=posting.to_json(),
        )
        return events

    def close_round(
        self, seen_urls: set[str] | None = None
    ) -> list[ChangeEvent]:
        """轮次收尾：登记本轮未见条目的缺失起始轮，并对连续缺失达 N 轮（K4）
        的条目产出 ANNOUNCEMENT_REMOVED。

        seen_urls：本轮全部源 ingest 过的 URL 并集（None = 不登记新缺失，
        仅对已缺失条目做去抖判定——受控测试场景）。
        删除事件只发一次（发后清 removed_since，时间线已持久）。
        """
        round_no = self._st.current_round()
        if seen_urls is not None:
            for url in self._st.all_urls():
                if url not in seen_urls:
                    self._st.mark_missing(url, round_no)
        events: list[ChangeEvent] = []
        debounce = self._config.removal_debounce_rounds
        for url, since in sorted(self._st.removed_since_map().items()):
            if round_no - since + 1 >= debounce:
                row = self._st.get_snapshot(url)
                assert row is not None
                events.append(
                    ChangeEvent(
                        kind=EventKind.ANNOUNCEMENT_REMOVED,
                        url=url,
                        source=SourceId(row["source"]),
                        round=round_no,
                        detail={
                            "missing_since_round": str(since),
                            "consecutive_missing_rounds": str(round_no - since + 1),
                        },
                    )
                )
                self._st.clear_removal(url)
        for ev in events:
            self._st.append_event(ev)
        return events

    @staticmethod
    def _new_posting_detail(posting: JobPosting) -> dict[str, str]:
        det: dict[str, str] = {"title": strip_update_suffix(posting.title)}
        for name in _DIFF_FIELDS:
            f = posting.fields()[name]
            if f.status.value == "verified" and f.value:
                det[name] = f.value
        return det
