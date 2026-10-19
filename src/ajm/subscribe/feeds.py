"""RSS 2.0 与 HTML 摘要生成（题面任务 4）：标准库手写 XML/HTML，零额外依赖。

纪律（HANDOFF-M4 / K6）：
- 推送条目 = 订阅命中事件，带来源 URL + 事件类型 + detail（verified 值已由
  differ 层门控进 detail，pending 不出镜）；
- 确定性：同一事件集合 + 生成时间戳 → 同一输出（XML 属性序固定、转义一致）；
- XML 特殊字符经 xml.sax.saxutils.escape 转义。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from ajm.config import EventKind
from ajm.models import ChangeEvent

_KIND_LABELS = {
    EventKind.NEW_POSTING: "新增岗位",
    EventKind.DEADLINE_CHANGED: "截止日变更",
    EventKind.CONTENT_CHANGED: "内容变更",
    EventKind.ANNOUNCEMENT_REMOVED: "公告删除",
}


@dataclass(slots=True)
class FeedEntry:
    """一条推送条目：事件 + 标题上下文。"""

    event: ChangeEvent
    title: str  # 快照库里的公告标题（非 detail 重建）

    def summary(self) -> str:
        """事件摘要文本（detail 逐键拼接，dict 序即插入序，确定性）。"""
        label = _KIND_LABELS.get(self.event.kind, str(self.event.kind))
        parts = [f"{k}: {v}" for k, v in self.event.detail.items()]
        return f"[{label}] " + "；".join(parts) if parts else f"[{label}]"

    def guid(self) -> str:
        """确定性 GUID：kind+url+round+detail 哈希（同事件重复运行不变）。"""
        import hashlib

        raw = (
            f"{self.event.kind}|{self.event.url}|{self.event.round}|"
            f"{self.event.detected_at.isoformat()}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def render_rss(
    entries: list[FeedEntry],
    *,
    channel_title: str,
    channel_link: str,
    generated_at: datetime | None = None,
) -> str:
    """RSS 2.0 文档（标准库手写 XML，条目按输入序）。"""
    now = generated_at or datetime.now(UTC)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{escape(channel_title)}</title>",
        f"<link>{escape(channel_link)}</link>",
        f"<description>{escape('高校学术招聘监控推送（仅 verified 字段出镜）')}</description>",
        f"<lastBuildDate>{_rfc822(now)}</lastBuildDate>",
    ]
    for entry in entries:
        desc = (
            f"{entry.title} — {entry.summary()}"
            f"（来源: {entry.event.source}，round {entry.event.round}）"
        )
        lines += [
            "<item>",
            f"<title>{escape(entry.summary())}</title>",
            f"<link>{escape(entry.event.url)}</link>",
            f"<guid>{escape(entry.guid())}</guid>",
            f"<pubDate>{_rfc822(entry.event.detected_at)}</pubDate>",
            f"<description>{escape(desc)}</description>",
            "</item>",
        ]
    lines += ["</channel>", "</rss>"]
    return "\n".join(lines)


_HTML_DOC = """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}}
h1{{font-size:1.3rem}} .meta{{color:#666;font-size:.85rem}}
li{{margin:.6rem 0}} .kind{{font-weight:600}}</style></head>
<body><h1>{title}</h1>
<p class="meta">生成时间 {generated} · 共 {count} 条 · 仅 verified 字段出镜</p>
<ul>{items}</ul></body></html>
"""


def render_html(
    entries: list[FeedEntry],
    *,
    channel_title: str,
    generated_at: datetime | None = None,
) -> str:
    """HTML 摘要页（内联样式，0 外链，断网可看）。"""
    now = generated_at or datetime.now(UTC)
    items = []
    for entry in entries:
        label = _KIND_LABELS.get(entry.event.kind, str(entry.event.kind))
        items.append(
            f"<li><span class='kind'>{escape(label)}</span> — "
            f"<a href='{escape(entry.event.url)}'>{escape(entry.title)}</a><br>"
            f"<span class='meta'>{escape(entry.summary())} · "
            f"来源 {escape(str(entry.event.source))} · round {entry.event.round}</span></li>"
        )
    return _HTML_DOC.format(
        title=escape(channel_title),
        generated=now.isoformat(timespec="seconds"),
        count=len(entries),
        items="".join(items),
    )
