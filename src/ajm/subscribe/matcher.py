"""关键词订阅（题面任务 4）：规则文件化 + 事件匹配（确定性，同输入恒定输出）。

规则文件（默认 subscribe.yaml，git-ignored；示例 subscribe.example.yaml 入库）：

    subscriptions:
      - name: 北京博士后
        keywords: ["博士后", "北京"]
        sources: [gaoxiaojob, pku]        # 可选，缺省 = 全部源
        kinds: [new_posting, deadline_changed]  # 可选，缺省 = 全部事件类型

匹配纪律（HANDOFF-M4）：
- 同一事件同一规则重复运行命中恒定（关键词集合匹配是纯函数）；
- 仅 verified 字段出镜（K6）：new_posting 的 detail 只含 verified 值（differ 已保证）；
- 匹配域 = 标题 + detail 值文本 + URL；大小写不敏感。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ajm.config import EventKind, SourceId
from ajm.models import ChangeEvent


@dataclass(slots=True)
class SubscriptionRule:
    """一条关键词订阅规则。"""

    name: str
    keywords: list[str]
    sources: list[SourceId] | None = None  # None = 全部源
    kinds: list[EventKind] | None = None  # None = 全部事件类型

    @classmethod
    def from_dict(cls, raw: dict) -> SubscriptionRule:
        return cls(
            name=str(raw["name"]),
            keywords=[str(k) for k in raw.get("keywords", [])],
            sources=(
                [SourceId(s) for s in raw["sources"]] if raw.get("sources") else None
            ),
            kinds=[EventKind(k) for k in raw.get("kinds")] if raw.get("kinds") else None,
        )


@dataclass(slots=True)
class SubscriptionConfig:
    """订阅规则集合（文件根对象）。"""

    rules: list[SubscriptionRule] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> SubscriptionConfig:
        p = Path(path)
        if not p.exists():
            return cls()
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        rules = [SubscriptionRule.from_dict(r) for r in data.get("subscriptions", [])]
        return cls(rules=rules)


def _match_text(rule: SubscriptionRule, event: ChangeEvent, title: str) -> bool:
    """确定性匹配：源过滤 → 事件类型过滤 → 关键词全命中（AND 语义）。"""
    if rule.sources is not None and event.source not in rule.sources:
        return False
    if rule.kinds is not None and event.kind not in rule.kinds:
        return False
    haystack = " ".join(
        [title.lower(), event.url.lower(), *[str(v).lower() for v in event.detail.values()]]
    )
    return all(kw.lower() in haystack for kw in rule.keywords)


def match_events(
    config: SubscriptionConfig,
    events: list[ChangeEvent],
    titles: dict[str, str] | None = None,
) -> dict[str, list[ChangeEvent]]:
    """按规则分组命中事件；返回 {规则名: [事件…]}（规则登记序，事件输入序）。

    titles: url → 标题（匹配域之一；快照库可查，调用方注入）。
    """
    titles = titles or {}
    out: dict[str, list[ChangeEvent]] = {}
    for rule in config.rules:
        hits = [ev for ev in events if _match_text(rule, ev, titles.get(ev.url, ""))]
        if hits:
            out[rule.name] = hits
    return out


def load_default(config_path) -> SubscriptionConfig:
    return SubscriptionConfig.from_file(config_path)
