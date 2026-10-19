"""字段抽取：命名规则族 + 确定性引擎（题面任务 2）。

模块布局：
- rules.py：规则登记表（每条规则具名，如 deadline_iso / deadline_cn_ymd）；
- engine.py：RawItem → JobPosting 的确定性抽取引擎。

确定性纪律（K5/K6 在抽取层的落点）：
- 规则未命中 → status=pending，绝不臆测、无启发式兜底；
- 同一输入恒定输出（规则按登记顺序试跑，第一个命中即取）；
- 多候选并存 → 全部保留 candidates 并标 ambiguous，不静默取第一个。
"""

from .engine import extract_posting, is_recruitment
from .rules import RULES, DeadlineRule

__all__ = ["RULES", "DeadlineRule", "extract_posting", "is_recruitment"]
