"""抓取适配器协议与基础结果类型。

契约（题面任务 1 的确定性纪律，骨架层强制）：
1. 每源一个独立适配器，互不共享解析假设（不继承公共解析基类，只实现协议）；
2. 解析不出整条跳过并记录，不做启发式猜测、无兜底正则；
3. 某源失败隔离不中断：任何异常由 registry 捕获转为 FetchOutcome.failure；
4. 请求统一经 fetch.Fetcher（UA 自标识 + 限频 + 超时），适配器不得自建 HTTP 客户端。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..config import AppConfig, FailureCode, SourceId
from ..fetch import Fetcher
from ..models import RawItem


@dataclass(slots=True)
class SourceFailure:
    """单源失败登记：原因码 + 细节，不携带异常栈（日志可追溯即可）。"""

    source: SourceId
    code: FailureCode
    detail: str = ""


@dataclass(slots=True)
class FetchOutcome:
    """一轮单源抓取结果：items 与 failure 互斥（成功必有 items，失败必有原因码）。"""

    source: SourceId
    items: list[RawItem] = field(default_factory=list)
    failure: SourceFailure | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None


class SourceAdapter(Protocol):
    """适配器协议。实现类放在 sources/ 下各自独立模块，不共享解析假设。"""

    source_id: SourceId

    def fetch_list(self, fetcher: Fetcher, config: AppConfig) -> FetchOutcome:
        """抓取列表页并解析为 RawItem 列表。

        解析失败条目整条跳过（可打印告警）；整源失败时返回 FetchOutcome.failure，
        不得抛出异常（registry 会兜底捕获，但契约要求适配器自净）。
        """
        ...
