"""acabridge 适配器：注册但预期稳定失败（M1 复核口径，plan/06 D5 推荐 A）。

M1 复核结论（fixtures/acabridge/notes.md）：
- `https://zpjob.acabridge.cn/` 302 跳 `https://www.acabridge.net/#/job`；
- 落地页被阿里云 WAF 滑块稳定拦截（换任何头均不通过，合规红线禁止绕过）；
- 适配器职责：抓取落地页 → 识别 WAF 拦截特征 → 返回 FetchOutcome.failure
  （新增 WAF_BLOCKED 原因码，plan/06 M2 决策行登记）；绝不重试绕过。
"""

from __future__ import annotations

import logging

from ..config import AppConfig, FailureCode, SourceId
from ..fetch import Fetcher
from ._htmlutil import parse_html
from .base import FetchOutcome, SourceFailure

logger = logging.getLogger(__name__)

SOURCE_ID = SourceId.ACABRIDGE
LIST_URL = "https://zpjob.acabridge.cn/"  # 302 → www.acabridge.net/#/job（Fetcher 跟随）

# 阿里云 WAF 拦截页结构特征（M1 复核 + fixture waf_interstitial.html 固化）。
_WAF_MARKERS: tuple[str, ...] = ("aliyun_waf_aa", "aliyunCaptcha-sliding-slider")


def _is_waf_interstitial(body: str) -> bool:
    """WAF 特征检测：meta 自闭合标签不入 DOM 树，故对原文做特征串匹配。"""
    return all(marker in body for marker in _WAF_MARKERS)


class AcabridgeAdapter:
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
        if _is_waf_interstitial(result.body):
            logger.warning("acabridge: WAF interstitial detected (compliance: no bypass)")
            return FetchOutcome(
                source=SOURCE_ID,
                failure=SourceFailure(
                    source=SOURCE_ID, code=FailureCode.WAF_BLOCKED, detail="aliyun_waf_interstitial"
                ),
            )
        # 非 WAF 页面：当前无服务端渲染列表可解析（SPA hash 路由），如实报 parse_empty。
        if not parse_html(result.body).find_all("a"):
            return FetchOutcome(
                source=SOURCE_ID,
                failure=SourceFailure(
                    source=SOURCE_ID, code=FailureCode.PARSE_EMPTY, detail="no anchors in page"
                ),
            )
        return FetchOutcome(
            source=SOURCE_ID,
            failure=SourceFailure(
                source=SOURCE_ID, code=FailureCode.PARSE_EMPTY, detail="no parseable list (SPA)"
            ),
        )
