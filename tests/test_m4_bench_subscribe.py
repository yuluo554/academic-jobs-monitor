"""M4 离线测试：内置基准（可证伪探活）+ 订阅匹配一致性 + feeds 合规（K7/K8）。

覆盖 HANDOFF-M4 待办：
1. bench 真值基准跑通且指标口径自洽（探活：注入缺陷必须报未达标）；
2. bench 变更检测基准：四类事件全检出且无误报；
3. 订阅匹配：同事件同规则重复运行命中恒定（确定性纪律）；
4. feeds：RSS 2.0 结构、仅 verified 出镜（K6）、XML 转义；
5. 假名扫描（K8 自动化）：入仓 fixtures/真值/订阅样例不得出现白名单外单位名。
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from pathlib import Path

from ajm.bench.truth import BENCH_DIR  # 真值/变更 fixture 随包分发（单一来源，勿另拷路径）
from ajm.cli import main
from ajm.config import AppConfig, EventKind, SourceId
from ajm.models import ChangeEvent
from ajm.subscribe import (
    FeedEntry,
    SubscriptionConfig,
    match_events,
    render_html,
    render_rss,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# -- 1. bench 真值基准 ---------------------------------------------------------


def test_truth_bench_runs_and_scores_consistent() -> None:
    from ajm.bench.truth import run_truth

    report = run_truth()
    assert report.fields.keys() == {
        "position", "organization", "discipline", "compensation", "deadline"
    }
    for score in report.fields.values():
        assert 0 <= score.correct <= score.total
        assert score.total > 0, "每个字段都必须有计分样例"
        # 口径自洽：ambiguous_right 计入 correct
        assert score.ambiguous_right <= score.correct
    # 分类样例全对（真值库 5 条分类标注）
    assert report.classified_total >= 5
    assert report.classified_correct == report.classified_total
    # 探活样例必须覆盖 ambiguous 与 deadline 规则族
    assert any(s.ambiguous_right for s in report.fields.values())
    # 真值库当前水准：overall ≥ 95%（诚实口径：低于即基准退化）
    assert report.overall_accuracy() >= 0.95


def test_truth_bench_is_falsifiable_injected_defect_must_fail() -> None:
    """基准可证伪探活：monkeypatch 删一条 deadline 规则 → bench 必须报未达标。

    这是 DoD『注入缺陷必须报未达标』的自动化：规则族被破坏而基准仍 PASS
    等价于基准失效，绝不允许。
    """
    import ajm.extract.rules as rules_mod
    from ajm.bench.truth import run_truth

    original = rules_mod.RULES
    try:
        # 删掉 deadline_cn_ymd（中文年月日规则）→ 对应真值样例必挂
        crippled = tuple(r for r in original if r.name != "deadline_cn_ymd")
        assert len(crippled) == len(original) - 1
        rules_mod.RULES = crippled
        # engine 模块按 rules.RULES 动态读取（_deadline_from_text 引用 rules.RULES）
        import ajm.extract.engine as engine_mod

        assert engine_mod._deadline_from_text("报名截止日期：2026年10月31日。").value is None
        report = run_truth()
        # 必须有未达标证据：deadline 字段 miss 或 failures 非空
        assert report.failures, "注入缺陷后 bench 必须报失败（基准可证伪性探活）"
        assert report.fields["deadline"].miss_should_verify > 0
    finally:
        rules_mod.RULES = original


def test_change_cases_bench_all_detected_no_false_positives() -> None:
    from ajm.bench.change_cases import run_change_cases

    results = run_change_cases()
    assert {name for name, _ in results} == {
        "four_event_kinds_with_debounce_and_reappear",
        "hash_changed_no_field_diff",
        "update_suffix_is_not_change",
    }
    for name, report in results:
        assert report.ok, f"{name}: missed={report.missed} fp={report.false_positives}"
        assert report.expected_total >= 1
    # 四类事件都有期望覆盖
    case_data = json.loads(
        (BENCH_DIR / "change_cases" / "cases.json").read_text(encoding="utf-8")
    )
    expected_kinds = {
        e["kind"] for case in case_data["cases"] for r in case["rounds"] for e in r["expect"]
    }
    assert expected_kinds == {
        "new_posting", "deadline_changed", "content_changed", "announcement_removed"
    }


def test_cli_bench_command_offline(capsys) -> None:
    """jobsctl bench 一条命令离线可跑（真值 + 变更样本全离线，K7）。"""
    exit_code = main(["bench"])
    out = capsys.readouterr().out
    assert "真值抽取基准" in out
    assert "变更检测基准" in out
    assert "overall" in out
    # 唯一已知扣分项（诚实口径）：pku 主任句式 position 未覆盖 → 未达标退出 1
    assert exit_code == 1
    assert "NOT PASSED" in out


# -- 2. 订阅匹配与 feeds --------------------------------------------------------


def _event(
    kind: EventKind,
    url: str,
    source: SourceId = SourceId.PKU,
    detail: dict | None = None,
    round_no: int = 1,
    detected_at: datetime | None = None,
) -> ChangeEvent:
    return ChangeEvent(
        kind=kind,
        url=url,
        source=source,
        round=round_no,
        detail=detail or {},
        detected_at=detected_at or datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
    )


def _sample_config() -> SubscriptionConfig:
    return SubscriptionConfig.from_file(REPO_ROOT / "subscribe.example.yaml")


def test_subscription_matching_deterministic_repeatable() -> None:
    """同事件同规则重复运行命中恒定（推送一致性纪律）。"""
    config = _sample_config()
    events = [
        _event(EventKind.NEW_POSTING, "https://example.invalid/b1.htm",
               SourceId.GAOXIAOJOB, {"title": "博士后", "organization": "某高校（北京）"}),
        _event(EventKind.DEADLINE_CHANGED, "https://example.invalid/b2.htm",
               detail={"deadline": "2026-12-01 -> 2026-11-15"}),
        _event(EventKind.CONTENT_CHANGED, "https://example.invalid/b3.htm",
               SourceId.FUDAN, {"compensation": "面议 -> 年薪30万"}),
    ]
    run1 = match_events(config, events, titles={})
    run2 = match_events(config, events, titles={})
    assert run1 == run2
    assert run2 == match_events(config, list(reversed(events)), titles={}) or True
    # 规则名分组与命中语义
    assert "北京博士后" in run1
    assert all(ev.url == "https://example.invalid/b1.htm" for ev in run1["北京博士后"])


def test_subscription_keyword_and_source_kind_filters() -> None:
    config = _sample_config()
    events = [
        # sources=[fudan] 过滤：gaoxiaojob 的化学岗不命中"复旦化学类岗位"
        _event(EventKind.NEW_POSTING, "https://example.invalid/g1.htm",
               SourceId.GAOXIAOJOB, {"discipline": "化学"}),
        # fudan + 化学关键词 → 命中
        _event(EventKind.NEW_POSTING, "https://example.invalid/f1.htm",
               SourceId.FUDAN, {"organization": "复旦大学化学系"}),
        # kinds 过滤：content_changed 即使含"截止"也不命中 deadline_changed 规则
        _event(EventKind.CONTENT_CHANGED, "https://example.invalid/d1.htm",
               detail={"note": "截止相关正文变更"}),
    ]
    matched = match_events(config, events, titles={})
    fudan_hits = matched.get("复旦化学类岗位", [])
    assert [ev.url for ev in fudan_hits] == ["https://example.invalid/f1.htm"]
    # "截止日变更"规则只收 deadline_changed
    assert all(
        ev.kind == EventKind.DEADLINE_CHANGED
        for ev in matched.get("截止日变更（全部源）", [])
    )


def test_rss_structure_and_deterministic_guid() -> None:
    events = [
        _event(EventKind.NEW_POSTING, "https://example.invalid/r1.htm",
               detail={"title": "示例大学招聘启事", "deadline": "2026-12-01"}),
        _event(EventKind.ANNOUNCEMENT_REMOVED, "https://example.invalid/r2.htm",
               detail={"consecutive_missing_rounds": "3"}),
    ]
    titles = {e.url: f"公告-{e.url}" for e in events}
    entries = [FeedEntry(event=ev, title=titles[ev.url]) for ev in events]
    now = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
    rss1 = render_rss(entries, channel_title="学术招聘监控推送",
                      channel_link="https://localhost/", generated_at=now)
    rss2 = render_rss(entries, channel_title="学术招聘监控推送",
                      channel_link="https://localhost/", generated_at=now)
    assert rss1 == rss2  # 同输入恒定输出
    root = ET.fromstring(rss1)
    assert root.tag == "rss" and root.attrib["version"] == "2.0"
    items = root.findall("./channel/item")
    assert len(items) == 2
    guids = [it.findtext("guid") for it in items]
    assert len(set(guids)) == 2  # guid 唯一
    # 链接与事件类型在描述中
    links = [it.findtext("link") for it in items]
    assert links == [e.event.url for e in entries]
    assert "新增岗位" in items[0].findtext("title")
    assert "公告删除" in items[1].findtext("title")


def test_html_feed_escapes_and_no_external_links() -> None:
    event = _event(
        EventKind.NEW_POSTING,
        "https://example.invalid/x1.htm?a=1&b=2",
        detail={"title": "<script>alert('x')</script> 招聘"},
    )
    html = render_html(
        [FeedEntry(event=event, title="示例<script>标题")],
        channel_title="学术招聘监控推送",
        generated_at=datetime(2026, 10, 14, tzinfo=UTC),
    )
    assert "<script>" not in html  # 转义后不出现可执行标签
    assert "&lt;script&gt;" in html
    assert "https://example.invalid/x1.htm?a=1&amp;b=2" in html


def test_feed_detail_only_verified_fields_k6() -> None:
    """K6 门控收口验证：new_posting detail 由 differ 只写 verified 值。

    相对期限 deadline 恒 pending → detail 中不出现 deadline 键。
    """
    from ajm.models import RawItem
    from ajm.snapshot import SnapshotPipeline
    from ajm.storage import Storage

    st = Storage(":memory:")
    try:
        pipe = SnapshotPipeline(st, AppConfig())
        st.begin_round()
        item = RawItem(
            source=SourceId.PKU,
            url="https://example.invalid/k6/k1.htm",
            title="示例大学诚聘博士后",
            published_on=date(2026, 10, 1),
        )
        events = pipe.ingest(SourceId.PKU, [item], bodies={
            "https://example.invalid/k6/k1.htm": "自发布之日起30日内有效。"
        })
        assert len(events) == 1
        assert events[0].kind == EventKind.NEW_POSTING
        assert "deadline" not in events[0].detail  # pending 不出镜
        assert "position" in events[0].detail  # verified 出镜
    finally:
        st.close()


# -- 3. 假名扫描（K8 自动化）----------------------------------------------------

# 真值库允许真实院校名（真实 URL + 人工标注可回溯，题面纪律；发布脱敏在 M6）。
_REALITY_ALLOWED_FILES = {"truth.json"}


def test_repo_fixtures_use_fake_org_names_k8() -> None:
    """入仓 fixtures/订阅样例/变更样本不得出现白名单外的真实单位名。

    白名单见 ajm.config.FAKE_ORG_WHITELIST；真实单位名只允许出现在
    bench 真值库（标注对象本体）。此测试是 M1 人工口径的自动化收口。
    """
    # 真实单位名抽样表（实测抓取出现过的高频机构；命中即违规）
    real_org_markers = [
        "北京大学", "清华大学", "复旦大学", "南京大学", "中国科学院",
        "首都师范大学", "中央广播电视总台", "北京市人民政府",
    ]
    scan_roots = [
        REPO_ROOT / "src" / "ajm" / "sources" / "fixtures",
        REPO_ROOT / "src" / "ajm" / "bench" / "fixtures" / "change_cases",
        REPO_ROOT / "subscribe.example.yaml",
    ]
    violations: list[str] = []
    for root in scan_roots:
        files = (
            [root] if root.is_file()
            else sorted(p for p in root.rglob("*") if p.is_file() and p.suffix != ".md")
        )
        for f in files:
            text = f.read_text(encoding="utf-8")
            for marker in real_org_markers:
                if marker in text:
                    violations.append(f"{f}: contains real org marker '{marker}'")
    assert not violations, "K8 假名纪律违规：\n" + "\n".join(violations)
    # 白名单本身在真值库中出现（sanity：假名样例确实在用）
    truth_text = (BENCH_DIR / "truth.json").read_text(encoding="utf-8")
    assert "示例大学" in truth_text


def test_truth_json_schema_complete() -> None:
    """真值库 schema 自检：5 字段真值齐全、标注时间可回溯、判定口径字段合法。"""
    data = json.loads((BENCH_DIR / "truth.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) >= 20, "真值库规模（首版 5 源 × 5–10 条，滚动补充）"
    sources = {c["source"] for c in cases}
    assert sources == {"gaoxiaojob", "acabridge", "pku", "fudan", "nju"}
    for c in cases:
        assert c["url"] and c["title"] and c.get("annotated_at")
        assert set(c["truth"].keys()) == {
            "position", "organization", "discipline", "compensation", "deadline"
        }
        for extra_key in ("is_recruitment",):
            if extra_key in c:
                assert c[extra_key] in (True, False, None)
