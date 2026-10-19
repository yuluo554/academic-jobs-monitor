"""全局配置与枚举。

确定性纪律在配置层落点：
- SourceId / EventKind / FieldStatus / FailureCode 全部用枚举，禁止裸字符串漂移；
- FAKE_ORG_WHITELIST 是合成样例唯一允许的单位名集合（data/README.md 第五节纪律）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

APP_NAME = "academic-jobs-monitor"
APP_VERSION = "0.1.0"

# 合规：抓取 UA 自标识（可被站点识别与联系），占位邮箱发布前替换为真实联系方式。
USER_AGENT = (
    f"{APP_NAME}/{APP_VERSION} "
    "(+https://github.com/yuluo554/academic-jobs-monitor; contact: yuluo554@example.com) "
    "public-notice-aggregator"
)

# 每源请求最小间隔（秒）：合规限频下限，适配器不得调低。
MIN_REQUEST_INTERVAL_SECONDS = 3.0

DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0

# 快照删除判定的去抖轮数：连续 N 轮缺失才产出 ANNOUNCEMENT_REMOVED。
REMOVAL_DEBOUNCE_ROUNDS = 3


class _StrEnum(StrEnum):
    """统一枚举基类：成员即其字符串值（`str(x) == x.value`，禁止裸字符串漂移）。

    M0 时是 `(str, Enum)` str 混入（`enum.StrEnum` 是 3.11+，为 3.10 底线让路）；
    M7 迭代把解释器 floor 抬到 3.12（DEC3=B）后改用 `enum.StrEnum`——对外行为不变
    （`__str__`/`__format__` 都返回 value），保留本基类名使四处枚举仍统一走一个基类。
    """


class SourceId(_StrEnum):
    """首期 5 源（设计决策，见 plan/00 决策记录；清华/浙大等不纳入）。"""

    GAOXIAOJOB = "gaoxiaojob"
    ACABRIDGE = "acabridge"
    PKU = "pku"
    FUDAN = "fudan"
    NJU = "nju"


class FieldStatus(_StrEnum):
    """字段状态门控：只有 verified 字段可进入推送路径。"""

    VERIFIED = "verified"
    PENDING = "pending"


class EventKind(_StrEnum):
    """快照 diff 四类事件（题面任务 3）。"""

    NEW_POSTING = "new_posting"
    DEADLINE_CHANGED = "deadline_changed"
    CONTENT_CHANGED = "content_changed"
    ANNOUNCEMENT_REMOVED = "announcement_removed"


class FailureCode(_StrEnum):
    """适配器失败原因码：单列登记，失败隔离不中断。"""

    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    ROBOTS_DISALLOWED = "robots_disallowed"
    WAF_BLOCKED = "waf_blocked"  # 反爬拦截页（acabridge 阿里云 WAF，禁止绕过，失败隔离）
    PARSE_EMPTY = "parse_empty"
    ENCODING_ERROR = "encoding_error"
    UNKNOWN = "unknown"


# 合成样例单位名假名白名单（data/README.md 第五节）。
FAKE_ORG_WHITELIST: frozenset[str] = frozenset(
    {
        "某高校",
        "示例大学",
        "示例研究院",
        "示例学院",
        "某研究院",
    }
)


@dataclass(slots=True)
class AppConfig:
    """运行期配置；storage/raw 路径默认在项目 cache/ 下（git-ignored）。"""

    storage_dir: Path = field(default_factory=lambda: Path("cache"))
    raw_dir: Path = field(default_factory=lambda: Path("cache/raw"))
    db_path: Path = field(default_factory=lambda: Path("cache/ajm.sqlite3"))
    subscribe_file: Path = field(default_factory=lambda: Path("subscribe.yaml"))
    request_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS
    timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    removal_debounce_rounds: int = REMOVAL_DEBOUNCE_ROUNDS

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)


def default_config() -> AppConfig:
    """从当前工作目录解析默认配置（CLI 与 webapp 共用同一入口）。"""
    cfg = AppConfig()
    cfg.ensure_dirs()
    return cfg
