"""gaoxiaojob 适配器（K5：独立解析假设，不共享他源规则）。

M1 复核结论（fixtures/gaoxiaojob/notes.md）：
- 入口 `https://www.gaoxiaojob.com/column/11.html`（原 /zhaopin/ 入口 404/403）；
- 条目 `.job-board` 内 `ul > li > a[href^="/job/detail/"]`；
- 列表页无每条发布日期 → published_on=None（K6 不臆测，日期属 M3+ 扩展）。
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from ..config import AppConfig, FailureCode, SourceId
from ..fetch import Fetcher
from ..models import RawItem
from ._htmlutil import Node, parse_html
from .base import FetchOutcome, SourceFailure

logger = logging.getLogger(__name__)

SOURCE_ID = SourceId.GAOXIAOJOB
LIST_URL = "https://www.gaoxiaojob.com/column/11.html"
_BASE_URL = "https://www.gaoxiaojob.com/"


def _parse_entry(anchor: Node) -> RawItem | None:
    """单条目解析：任何必需字段缺失返回 None（整条跳过，不兜底）。

    页面结构中"原样存在"的值（requirement/region span）进 RawItem.extra，
    供抽取层映射为 verified 证据（K5：适配器不推断，只搬运页面原值）。
    """
    href = anchor.attrs.get("href", "")
    if not href.startswith("/job/detail/"):
        return None
    title = anchor.attrs.get("title", "").strip()
    if not title:
        return None
    extra: dict[str, str] = {}
    position_div = anchor.find("div", class_contains="position")
    if position_div is not None:
        h6 = position_div.find("h6")
        if h6 is not None and h6.text().strip():
            extra["position"] = h6.text().strip()
        money = position_div.find("span", class_contains="money")
        if money is not None and money.text().strip():
            extra["compensation"] = money.text().strip()
    requirement = anchor.find("div", class_contains="requirement")
    if requirement is not None:
        spans = [s.text().strip() for s in requirement.find_all("span")]
        # notes.md 口径：顺序固定 = [学历, 学科, 人数]
        if len(spans) >= 2 and spans[1]:
            extra["discipline"] = spans[1]
        if len(spans) >= 1 and spans[0]:
            extra["degree"] = spans[0]
        if len(spans) >= 3 and spans[2]:
            extra["headcount"] = spans[2]
    region = anchor.find("div", class_contains="region")
    if region is not None:
        school = region.find("span", class_contains="school")
        if school is not None and school.text().strip():
            extra["org"] = school.text().strip()
        city = region.find("span", class_contains="city")
        if city is not None and city.text().strip():
            extra["city"] = city.text().strip()
    return RawItem(
        source=SOURCE_ID,
        url=urljoin(_BASE_URL, href),
        title=title,
        published_on=None,  # 列表页无日期字段（M1 复核确认）
        extra=extra,
    )


class GaoxiaojobAdapter:
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
        board = root.find("div", class_contains="job-board")
        if board is None:
            return FetchOutcome(
                source=SOURCE_ID,
                failure=SourceFailure(
                    source=SOURCE_ID, code=FailureCode.PARSE_EMPTY, detail="job-board not found"
                ),
            )
        items: list[RawItem] = []
        for anchor in board.find_all("a"):
            item = _parse_entry(anchor)
            if item is None:
                href = anchor.attrs.get("href", "")
                logger.warning("gaoxiaojob: skip unparseable entry href=%r", href)
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
