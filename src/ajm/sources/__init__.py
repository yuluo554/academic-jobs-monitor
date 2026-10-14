"""sources 包：适配器模块与注册入口。

各适配器独立模块（K5 不共享解析假设），在此集中登记进 registry。
"""

from __future__ import annotations

from . import acabridge, fudan, gaoxiaojob, nju, pku
from .registry import register

register(acabridge.SOURCE_ID, acabridge.AcabridgeAdapter)
register(fudan.SOURCE_ID, fudan.FudanAdapter)
register(gaoxiaojob.SOURCE_ID, gaoxiaojob.GaoxiaojobAdapter)
register(nju.SOURCE_ID, nju.NjuAdapter)
register(pku.SOURCE_ID, pku.PkuAdapter)

__all__ = ["acabridge", "fudan", "gaoxiaojob", "nju", "pku", "register"]
