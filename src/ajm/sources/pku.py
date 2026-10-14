"""pku 适配器（K5：独立解析假设）。

M1 复核结论（fixtures/pku/notes.md）：
- 入口 `https://hr.pku.edu.cn/`，条目 `li > a[title*="发布日期"]`；
- title 属性格式 `"<标题> 发布日期：YYYY-MM-DD "`（全角冒号，可能有尾随空格）；
  文本有省略号截断风险，以 title 属性为准；
- href 为相对路径，urljoin 拼接；
- 外链（他域，如博士后栏）整条跳过 —— 首期只收站内招聘条目（M2 拍板，
  plan/06 登记外链不属于本源可验证的招聘公告，跳过而非臆测）。
"""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from ..config import AppConfig, FailureCode, SourceId
from ..fetch import Fetcher
from ..models import RawItem
from ._htmlutil import parse_html
from .base import FetchOutcome, SourceFailure

logger = logging.getLogger(__name__)

SOURCE_ID = SourceId.PKU
LIST_URL = "https://hr.pku.edu.cn/"
_BASE_URL = "https://hr.pku.edu.cn/"
_ALLOWED_HOST = "hr.pku.edu.cn"

# title 属性中"发布日期：YYYY-MM-DD"（全角冒号），标题在前。
_TITLE_DATE_RE = re.compile(r"^(?P<title>.+?)\s*发布日期：(?P<date>\d{4}-\d{2}-\d{2})\s*$", re.S)


def _parse_entry(anchor) -> RawItem | None:  # type: ignore[type-arg]
    title_attr = anchor.attrs.get("title", "").strip()
    href = anchor.attrs.get("href", "").strip()
    if not title_attr or not href:
        return None
    match = _TITLE_DATE_RE.match(title_attr)
    if match is None:
        return None
    url = urljoin(_BASE_URL, href)
    if urlparse(url).hostname != _ALLOWED_HOST:
        return None  # 外链（如博士后专栏跳他域）整条跳过
    published = date.fromisoformat(match.group("date"))
    return RawItem(
        source=SOURCE_ID,
        url=url,
        title=match.group("title").strip(),
        published_on=published,
    )


class PkuAdapter:
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
        for anchor in root.find_all("a"):
            if "发布日期：" not in anchor.attrs.get("title", ""):
                continue
            item = _parse_entry(anchor)
            if item is None:
                href = anchor.attrs.get("href", "")
                logger.warning("pku: skip unparseable/external entry href=%r", href)
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
