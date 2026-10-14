"""HTTP 会话：统一 UA 自标识、超时、每源限频（合规内建，见 config.py）。

适配器不直接 import httpx，一律经由此模块发请求，保证：
- UA / 超时 / 限频策略单点收敛，适配器无机会绕过；
- 失败以 FailureCode 单列返回，供失败隔离登记。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from .config import USER_AGENT, AppConfig, FailureCode


@dataclass(slots=True)
class FetchResult:
    """单次 HTTP 结果：ok 时 body 有值，失败时 failure_code 单列原因。"""

    ok: bool
    status_code: int | None = None
    body: str | None = None
    failure_code: FailureCode | None = None
    failure_detail: str = ""


class RateLimiter(Protocol):
    def wait(self, key: str) -> None: ...


class MinIntervalLimiter:
    """按 key（如 SourceId）限频：两次请求间隔不小于 min_interval 秒。"""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._last: dict[str, float] = {}

    def wait(self, key: str) -> None:
        now = time.monotonic()
        last = self._last.get(key)
        if last is not None:
            remain = self._min_interval - (now - last)
            if remain > 0:
                time.sleep(remain)
        self._last[key] = time.monotonic()


class Fetcher:
    """同步 HTTP 客户端门面。"""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._limiter = MinIntervalLimiter(config.request_interval_seconds)
        self._client = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=config.timeout_seconds,
            follow_redirects=True,
        )

    def get(self, url: str, *, rate_limit_key: str) -> FetchResult:
        """GET 一个页面；失败返回 failure_code（TIMEOUT / HTTP_ERROR / UNKNOWN）。"""
        self._limiter.wait(rate_limit_key)
        try:
            resp = self._client.get(url)
        except httpx.TimeoutException as exc:
            return FetchResult(ok=False, failure_code=FailureCode.TIMEOUT, failure_detail=str(exc))
        except httpx.HTTPError as exc:
            return FetchResult(
                ok=False, failure_code=FailureCode.HTTP_ERROR, failure_detail=str(exc)
            )
        if resp.is_error:
            return FetchResult(
                ok=False,
                status_code=resp.status_code,
                failure_code=FailureCode.HTTP_ERROR,
                failure_detail=f"HTTP {resp.status_code}",
            )
        # 显式 UTF-8 解码失败的容错：让 ENCODING_ERROR 单列而非抛异常。
        try:
            body = resp.content.decode(resp.encoding or "utf-8")
        except (UnicodeDecodeError, LookupError):
            try:
                body = resp.content.decode("utf-8", errors="replace")
            except Exception as exc:  # pragma: no cover - 理论不可达
                return FetchResult(
                    ok=False, status_code=resp.status_code,
                    failure_code=FailureCode.ENCODING_ERROR, failure_detail=str(exc),
                )
        return FetchResult(ok=True, status_code=resp.status_code, body=body)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
