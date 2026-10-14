"""fudan 适配器（K5：独立解析假设）。

M1 复核结论（fixtures/fudan/notes.md）：
- 入口 `https://hr.fudan.edu.cn/15364/list.htm`（教学科研栏目）；
- 条目 `a.column-news-item`（栏目导航 `column-item-link` 天然不同类，不混入）；
- 标题 `span.column-news-title`，日期 `span.column-news-date`（YYYY-MM-DD）；
- href 站内绝对路径，urljoin 拼接。
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

SOURCE_ID = SourceId.FUDAN
LIST_URL = "https://hr.fudan.edu.cn/15364/list.htm"
_BASE_URL = "https://hr.fudan.edu.cn/"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_entry(anchor: Node) -> RawItem | None:
    href = anchor.attrs.get("href", "").strip()
    if not href:
        return None
    title_node = anchor.find("span", class_contains="column-news-title")
    date_node = anchor.find("span", class_contains="column-news-date")
    if title_node is None or date_node is None:
        return None
    title = title_node.text().strip()
    date_text = date_node.text().strip()
    if not title or not _DATE_RE.match(date_text):
        return None
    return RawItem(
        source=SOURCE_ID,
        url=urljoin(_BASE_URL, href),
        title=title,
        published_on=date.fromisoformat(date_text),
    )


class FudanAdapter:
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
        for anchor in root.find_all("a", class_contains="column-news-item"):
            item = _parse_entry(anchor)
            if item is None:
                logger.warning("fudan: skip unparseable entry href=%r", anchor.attrs.get("href"))
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
