"""nju 适配器（K5：独立解析假设）。

M1 复核结论（fixtures/nju/notes.md）：
- 入口 `https://hr.nju.edu.cn/`，条目 `li.news`（类名带序号修饰如 "news 1"）；
- 标题：`span.news_title > a` 的 title 属性（a 文本是省略号截断版，以 title 为准）；
- 日期：`span.news_meta`（YYYY-MM-DD）；
- 无日期条目（导航类）整条跳过（M2 口径：解析不出必需字段即跳过，K5）。
"""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin

from ..config import AppConfig, FailureCode, SourceId
from ..fetch import Fetcher
from ..models import RawItem
from ._htmlutil import Node, parse_html
from .base import FetchOutcome, SourceFailure

logger = logging.getLogger(__name__)

SOURCE_ID = SourceId.NJU
LIST_URL = "https://hr.nju.edu.cn/"
_BASE_URL = "https://hr.nju.edu.cn/"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_entry(item_node: Node) -> RawItem | None:
    anchor = item_node.find("span", class_contains="news_title")
    if anchor is None:
        return None
    anchor = anchor.find("a")
    if anchor is None:
        return None
    href = anchor.attrs.get("href", "").strip()
    title = anchor.attrs.get("title", "").strip()
    if not href or not title:
        return None
    date_node = item_node.find("span", class_contains="news_meta")
    if date_node is None:
        return None  # 无日期条目（导航类）整条跳过
    date_text = date_node.text().strip()
    if not _DATE_RE.match(date_text):
        return None
    return RawItem(
        source=SOURCE_ID,
        url=urljoin(_BASE_URL, href),
        title=title,
        published_on=date.fromisoformat(date_text),
    )


class NjuAdapter:
    source_id = SOURCE_ID

    def fetch_list(self, fetcher: Fetcher, config: AppConfig) -> FetchOutcome:
        result = fetcher.get(LIST_URL, rate_limit_key=str(SOURCE_ID))
        if not result.ok:
            assert result.failure_code is not None
            return FetchOutcome(
                source=SOURCE_ID,
                failure=SourceFailure(
                    source=SOURCE_ID, code=result.failure_code, detail=result.failure_detail
                ),
            )
        assert result.body is not None
        root = parse_html(result.body)
        items: list[RawItem] = []
        for item_node in root.find_all("li", class_contains="news"):
            item = _parse_entry(item_node)
            if item is None:
                logger.warning("nju: skip entry without parseable title/date")
                continue
            items.append(item)
        if not items:
            return FetchOutcome(
                source=SOURCE_ID,
                failure=SourceFailure(
                    source=SOURCE_ID, code=FailureCode.PARSE_EMPTY, detail="0 entries parsed"
                ),
            )
        return FetchOutcome(source=SOURCE_ID, items=items)
