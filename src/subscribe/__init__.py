"""订阅与推送（题面任务 4）：关键词规则文件化 + RSS/HTML 摘要。

- matcher.py：规则加载与确定性事件匹配（同事件同规则重复运行命中恒定）；
- feeds.py：RSS 2.0 / HTML 渲染（标准库手写 XML，0 外链）。

K6 门控在 feeds 层收口：进入推送的 detail 只含 verified 字段值
（SnapshotPipeline._new_posting_detail / _field_detail_changes 已只写 verified 值）。
"""

from .feeds import FeedEntry, render_html, render_rss
from .matcher import SubscriptionConfig, SubscriptionRule, match_events

__all__ = [
    "FeedEntry",
    "SubscriptionConfig",
    "SubscriptionRule",
    "match_events",
    "render_html",
    "render_rss",
]
