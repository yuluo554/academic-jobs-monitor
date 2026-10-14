"""适配器注册表与逐源隔离调度。

失败隔离在此单点实现：单源异常 / 失败结果只登记，不影响其他源本轮产出。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..config import AppConfig, FailureCode, SourceId
from ..fetch import Fetcher
from .base import FetchOutcome, SourceFailure

logger = logging.getLogger(__name__)

# 延迟导入：各适配器模块在 M2 逐个落地后登记于此。
# 设计约束：注册表只做"查表 + 调度"，不承载任何解析逻辑。
AdapterFactory = Callable[[], object]

_REGISTRY: dict[SourceId, AdapterFactory] = {}


def register(source_id: SourceId, factory: AdapterFactory) -> None:
    _REGISTRY[source_id] = factory


def registered_sources() -> list[SourceId]:
    return sorted(_REGISTRY)


def fetch_source(source_id: SourceId, fetcher: Fetcher, config: AppConfig) -> FetchOutcome:
    """抓取单源；任何异常兜底转 FetchOutcome.failure（UNKNOWN 原因码）。"""
    factory = _REGISTRY.get(source_id)
    if factory is None:
        return FetchOutcome(
            source=source_id,
            failure=SourceFailure(
                source=source_id, code=FailureCode.UNKNOWN, detail="adapter not registered"
            ),
        )
    try:
        adapter = factory()
        return adapter.fetch_list(fetcher, config)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - 失败隔离边界，必须兜底
        logger.warning("source %s failed with exception: %s", source_id, exc)
        return FetchOutcome(
            source=source_id,
            failure=SourceFailure(source=source_id, code=FailureCode.UNKNOWN, detail=repr(exc)),
        )


def fetch_all(
    source_ids: list[SourceId] | None, fetcher: Fetcher, config: AppConfig
) -> list[FetchOutcome]:
    """顺序抓取多源（限频已内建，无需并发）；None = 全部已注册源。"""
    ids = source_ids if source_ids is not None else registered_sources()
    return [fetch_source(sid, fetcher, config) for sid in ids]
