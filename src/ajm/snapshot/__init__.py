"""快照与变更检测（题面任务 3）：持久快照 + 字段级 diff 四类事件 + 删除去抖。

- differ.SnapshotPipeline：CLI 与 Web 共用的编排入口（单一事实源）；
- storage（ajm.storage.SQLite）：快照/事件/去抖状态持久层；
- 四类事件见 config.EventKind；去抖 N=3 见 config.REMOVAL_DEBOUNCE_ROUNDS（K4）。
"""

from .differ import SnapshotPipeline

__all__ = ["SnapshotPipeline"]
