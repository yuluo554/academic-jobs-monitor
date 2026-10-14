"""内置基准（题面任务 5）：真值抽取对账 + 受控变更样本，一条命令可重复运行。

模块布局：
- truth.json（bench/fixtures/）：真实公告 URL + 人工标注 5 字段真值；
- change_cases/（bench/fixtures/）：同一页面多轮受控构造的变更样本；
- run_truth()：逐字段准确率（口径见 bench/README.md 与 README 指标口径节）；
- run_change_cases()：四类事件检出率（变更检测基准）。

判定口径（plan/06 M4 决策行登记）：
- 真值 null：正确行为 = pending。verified 或 ambiguous 均记错（臆测即扣分，K5/K6）；
- 真值非 null：value 相等记对；ambiguous 且真值 ∈ candidates 记对（ambiguous_right
  单独统计）；pending 记错；verified 值不等记错；
- deadline_pending_expected 样例：正确行为 = pending + 证据保留，pending 记对、
  verified/ambiguous 记错，不计入准确率分母（相对期限恒 pending 是既定口径）；
- expect_all_pending 样例：全字段 pending 才对（分类不可判定条目的字段门控）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ajm.config import FieldStatus, SourceId
from ajm.models import RawItem
from extract.engine import extract_posting, is_recruitment

BENCH_DIR = Path(__file__).resolve().parents[2] / "bench" / "fixtures"
TRUTH_PATH = BENCH_DIR / "truth.json"
CHANGE_CASES_DIR = BENCH_DIR / "change_cases"

_FIELDS = ("position", "organization", "discipline", "compensation", "deadline")


@dataclass(slots=True)
class FieldScore:
    """单字段计分：分母/分子 + 分类明细（ambiguous、pending 期望单独计）。"""

    total: int = 0
    correct: int = 0
    ambiguous_right: int = 0
    ambiguous_wrong: int = 0
    miss_should_verify: int = 0
    hallucinated: int = 0  # 真值 null 却 verified/ambiguous（臆测，最严重）

    def as_dict(self) -> dict[str, int | float]:
        rate = (self.correct / self.total) if self.total else 1.0
        return {
            "total": self.total,
            "correct": self.correct,
            "accuracy": round(rate, 4),
            "ambiguous_right": self.ambiguous_right,
            "ambiguous_wrong": self.ambiguous_wrong,
            "miss_should_verify": self.miss_should_verify,
            "hallucinated": self.hallucinated,
        }


@dataclass(slots=True)
class TruthReport:
    """真值基准报告：逐字段准确率 + 分类对错 + 失败明细。"""

    fields: dict[str, FieldScore] = field(default_factory=dict)
    classified_total: int = 0
    classified_correct: int = 0
    failures: list[str] = field(default_factory=list)

    def field_scores(self) -> dict[str, dict[str, int | float]]:
        return {name: score.as_dict() for name, score in self.fields.items()}

    def overall_accuracy(self) -> float:
        total = sum(s.total for s in self.fields.values())
        correct = sum(s.correct for s in self.fields.values())
        return (correct / total) if total else 1.0


def _load_cases() -> list[dict]:
    data = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def _score_field(score: FieldScore, truth, extracted) -> bool:
    """单字段判定；返回是否正确。口径见模块 docstring。"""
    f_status = extracted.status.value
    f_value = extracted.value

    if truth is None:
        if f_status == FieldStatus.PENDING.value:
            score.total += 1
            score.correct += 1
            return True
        score.total += 1
        score.hallucinated += 1
        return False

    score.total += 1
    if f_status == FieldStatus.VERIFIED.value and f_value == truth:
        score.correct += 1
        return True
    if extracted.ambiguous and truth in (extracted.candidates or []):
        score.ambiguous_right += 1
        score.correct += 1
        return True
    if extracted.ambiguous:
        score.ambiguous_wrong += 1
        return False
    if f_status == FieldStatus.PENDING.value:
        score.miss_should_verify += 1
        return False
    score.hallucinated += 1  # verified 但值不等
    return False


def run_truth() -> TruthReport:
    """真值抽取对账：truth.json 全样例逐字段判定。"""
    report = TruthReport()
    report.fields = {name: FieldScore() for name in _FIELDS}
    for case in _load_cases():
        item = RawItem(
            source=SourceId(case["source"]),
            url=case["url"],
            title=case["title"],
            published_on=(
                date.fromisoformat(case["published_on"]) if case.get("published_on") else None
            ),
            extra=case.get("extra") or {},
        )
        posting = extract_posting(item, case.get("body_text") or "")

        # 分类对账（标注了 is_recruitment 的样例；None 期望同样对账）
        if "is_recruitment" in case:
            report.classified_total += 1
            if is_recruitment(item) is case["is_recruitment"]:
                report.classified_correct += 1
            else:
                report.failures.append(f"{case['url']}: classification mismatch")

        # 非招聘条目与生产口径一致：不入快照、不进字段抽取分母
        #（SnapshotPipeline.ingest 显式跳过 is_recruitment=False，字段对账只对入库条目）。
        if case.get("is_recruitment") is False:
            continue

        # expect_all_pending：分类不可判定条目，全字段 pending 才对
        if case.get("expect_all_pending"):
            for name, f in posting.fields().items():
                if f.status.value != FieldStatus.PENDING.value:
                    report.failures.append(
                        f"{case['url']}: {name} expected pending, got {f.status.value}={f.value}"
                    )
            continue

        for name in _FIELDS:
            truth = case["truth"].get(name)
            extracted = posting.fields()[name]
            # deadline 相对期限样例：pending 是正确行为，不计分母（K6 既定口径）
            if name == "deadline" and case.get("deadline_pending_expected"):
                if extracted.status.value != FieldStatus.PENDING.value:
                    report.failures.append(
                        f"{case['url']}: deadline expected pending (relative), "
                        f"got {extracted.status.value}"
                    )
                continue
            ok = _score_field(report.fields[name], truth, extracted)
            if not ok:
                report.failures.append(
                    f"{case['url']}: {name} truth={truth} "
                    f"got={extracted.value or extracted.candidates} ({extracted.status.value})"
                )
    return report
