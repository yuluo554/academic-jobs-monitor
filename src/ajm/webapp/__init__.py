"""Web 面板（M5）：FastAPI 内联单页 + 共享视图层（CLI 双形态对账单一事实源）。"""

from .app import create_app, run

__all__ = ["create_app", "run"]
