"""核心数据模型。

字段设计对齐题面任务 1–4：
- RawItem：抓取层统一原始条目（标题/URL/发布日期/来源 + raw 留证路径）；
- ExtractedField：抽取字段 = 值 + status 门控 + 证据链（命中规则名 + 原文片段）；
- JobPosting：结构化字段集合（岗位/单位/学科方向/待遇/截止日期）；
- Snapshot / ChangeEvent：持久快照与四类事件。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from .config import EventKind, FieldStatus, SourceId

_TEXT_COLLAPSE = re.compile(r"\s+")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(text: str) -> str:
    """文本归一化：空白折叠。diff 与哈希统一走此函数，保证同一输入恒定输出。"""
    return _TEXT_COLLAPSE.sub(" ", text).strip()


def content_hash(text: str) -> str:
    """正文哈希：仅作变更存在性初筛信号，不作事件分类依据（字段级 diff 才分类）。"""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class RawItem:
    """抓取层统一原始条目模型（题面任务 1 输出契约）。"""

    source: SourceId
    url: str
    title: str
    published_on: date | None
    # raw HTML 落盘留证路径（相对项目根；cache/ 已 git-ignore，不外发）。
    raw_html_path: str | None = None
    fetched_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class Evidence:
    """抽取证据链：字段值必须能回溯到命中规则与原文片段（题面"来源证据"纪律）。"""

    rule_name: str
    snippet: str  # 原文片段定位（截断存储，避免整段冗余）


@dataclass(slots=True)
class ExtractedField:
    """单字段抽取结果。

    确定性纪律：
    - 同一正文输入产出恒定（规则集不变时值与 evidence 不变）；
    - 规则未命中 → status=pending，绝不臆测；
    - 多候选并存 → 全部保留在 candidates 并置 ambiguous，不静默取第一个。
    """

    name: str
    status: FieldStatus
    value: str | None = None
    candidates: list[str] = field(default_factory=list)
    ambiguous: bool = False
    evidence: Evidence | None = None

    @classmethod
    def unextracted(cls, name: str) -> ExtractedField:
        return cls(name=name, status=FieldStatus.PENDING)


@dataclass(slots=True)
class JobPosting:
    """结构化字段集合（题面任务 2 输出契约）。"""

    url: str
    source: SourceId
    title: str
    published_on: date | None
    position: ExtractedField  # 岗位名称
    organization: ExtractedField  # 单位
    discipline: ExtractedField  # 学科方向
    compensation: ExtractedField  # 待遇
    deadline: ExtractedField  # 截止日期
    body_text: str = ""
    content_hash: str = ""
    extracted_at: datetime = field(default_factory=_utcnow)

    def fields(self) -> dict[str, ExtractedField]:
        return {
            "position": self.position,
            "organization": self.organization,
            "discipline": self.discipline,
            "compensation": self.compensation,
            "deadline": self.deadline,
        }


@dataclass(slots=True)
class Snapshot:
    """一轮抓取的持久快照条目。"""

    url: str
    source: SourceId
    title: str
    content_hash: str
    seen_round: int  # 首次见到该 URL 的轮次
    last_seen_round: int  # 最近一轮仍存在
    extracted: JobPosting | None
    snapshotted_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class ChangeEvent:
    """变更事件（题面任务 3 输出契约；四类见 EventKind）。

    before/after 均为字段级（字段名 → 值），非全文哈希一票否决。
    """

    kind: EventKind
    url: str
    source: SourceId
    round: int
    detail: dict[str, str] = field(default_factory=dict)  # {"deadline": "旧值 -> 新值"}
    detected_at: datetime = field(default_factory=_utcnow)
