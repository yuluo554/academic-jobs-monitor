"""M3 离线测试：字段抽取规则族 + 快照 diff 四类事件（全离线，K7）。

覆盖 HANDOFF-M3 待办：
1. deadline 多格式正则族逐规则命中（含非法日期不臆测、相对期限 pending）；
2. gaoxiaojob extra 结构化字段 → verified 证据映射；
3. 未命中 pending、多候选 ambiguous（K6）；
4. 招聘/非招聘分类（nju/pku 首页通知混入边界）；
5. 受控两轮样本：四类事件全检出且无误报（含删除去抖 N=3 与"删除后复现"）。
"""

from __future__ import annotations

from datetime import date

from ajm.config import AppConfig, EventKind, FieldStatus, SourceId
from ajm.extract import RULES, extract_posting, is_recruitment
from ajm.extract.engine import _deadline_from_text  # noqa: PLC2701  直接测规则族
from ajm.models import Evidence, RawItem
from ajm.snapshot import SnapshotPipeline
from ajm.storage import Storage


def _item(
    title: str,
    url: str = "https://example.edu.cn/j1.htm",
    source: SourceId = SourceId.PKU,
    extra: dict[str, str] | None = None,
    published: date | None = None,
) -> RawItem:
    return RawItem(
        source=source,
        url=url,
        title=title,
        published_on=published,
        extra=extra or {},
    )


# -- 1. deadline 规则族 --------------------------------------------------------


def test_rule_registry_named() -> None:
    names = [r.name for r in RULES]
    # 命名规范：deadline_<格式语义>（plan/06 登记）
    assert names == [
        "deadline_iso",
        "deadline_cn_ymd",
        "deadline_chinese_until",
        "deadline_relative_from_now",
    ]


def test_deadline_iso_anchor() -> None:
    f = _deadline_from_text("报名截止时间：2026-12-01，逾期不受理。")
    assert f.status == FieldStatus.VERIFIED
    assert f.value == "2026-12-01"
    assert f.evidence is not None and f.evidence.rule_name == "deadline_iso"
    assert "报名截止" in f.evidence.snippet


def test_deadline_iso_date_before_截止() -> None:
    f = _deadline_from_text("2026-11-15前将简历发送至人事处。")
    assert f.status == FieldStatus.VERIFIED
    assert f.value == "2026-11-15"


def test_deadline_cn_ymd_anchor() -> None:
    f = _deadline_from_text("申请截止日期：2026年12月1日。")
    assert f.status == FieldStatus.VERIFIED
    assert f.value == "2026-12-01"
    assert f.evidence.rule_name == "deadline_cn_ymd"


def test_deadline_chinese_until() -> None:
    f = _deadline_from_text("即日起至2027年1月10日均可报名。")
    assert f.status == FieldStatus.VERIFIED
    assert f.value == "2027-01-10"
    assert f.evidence.rule_name == "deadline_chinese_until"


def test_deadline_relative_stays_pending_with_evidence() -> None:
    f = _deadline_from_text("自发布之日起30日内有效。")
    # 相对期限起点歧义（K6）：证据保留，日期 pending 不臆测
    assert f.status == FieldStatus.PENDING
    assert f.value is None
    assert f.evidence is not None and f.evidence.rule_name == "deadline_relative_from_now"


def test_deadline_invalid_date_not_guessed() -> None:
    # "13 月"匹配不了规则（月份字符集限制），但"2月30日"类非法组合必须 pending
    f = _deadline_from_text("报名截止：2026年2月30日。")
    assert f.status == FieldStatus.PENDING
    assert f.value is None


def test_deadline_miss_is_plain_pending() -> None:
    f = _deadline_from_text("欢迎优秀人才加盟。")
    assert f.status == FieldStatus.PENDING
    assert f.value is None
    assert f.evidence is None
    assert f.candidates == []


def test_deadline_ambiguous_keeps_all_candidates() -> None:
    # 两个不同候选 → 全保留 + ambiguous，不静默取第一个（题面纪律）
    text = "第一轮报名截止：2026-12-01；第二轮报名截止：2026-12-20。"
    f = _deadline_from_text(text)
    assert f.status == FieldStatus.VERIFIED
    assert f.ambiguous
    assert f.value is None
    assert f.candidates == ["2026-12-01", "2026-12-20"]


# -- 2. 结构化 extra 映射（gaoxiaojob 路径）------------------------------------


def test_gaoxiaojob_extra_maps_to_verified_evidence() -> None:
    item = _item(
        "博士后",
        url="https://www.gaoxiaojob.com/job/detail/9000001.html",
        source=SourceId.GAOXIAOJOB,
        extra={
            "position": "博士后",
            "compensation": "面议",
            "discipline": "化学",
            "degree": "博士研究生",
            "org": "某高校",
            "city": "北京",
        },
    )
    posting = extract_posting(item)
    assert posting.position.status == FieldStatus.VERIFIED
    assert posting.position.value == "博士后"
    assert posting.position.evidence is not None
    assert posting.position.evidence.rule_name == "structured_position"
    assert posting.organization.value == "某高校"
    assert posting.discipline.value == "化学"
    assert posting.compensation.value == "面议"  # "面议"也是页面原值，照常收


def test_title_anchor_extraction_fudan_style() -> None:
    item = _item("示例大学全球史研究院招聘启事", source=SourceId.FUDAN)
    posting = extract_posting(item)
    # 标题锚：单位后缀 + 招聘锚
    assert posting.organization.status == FieldStatus.VERIFIED
    assert posting.organization.value == "示例大学全球史研究院"
    assert posting.organization.evidence.rule_name == "org_title_anchor"


def test_all_pending_when_no_rules_hit() -> None:
    posting = extract_posting(_item("关于开展2026年度岗位聘用工作的通知"))
    assert all(f.status == FieldStatus.PENDING for f in posting.fields().values())
    assert all(f.value is None for f in posting.fields().values())


# -- 3. 招聘/非招聘分类 --------------------------------------------------------


def test_classification_recruit_vs_notice() -> None:
    assert is_recruitment(_item("2026年某高校教学科研岗位招聘启事")) is True
    assert is_recruitment(_item("示例研究院诚聘博士后")) is True
    # 显式排除：通知/培训/评定类
    assert is_recruitment(_item("关于做好2026年下半年示例学院教师资格认定工作的通知")) is False
    assert is_recruitment(
        _item("2026年度示例大学管理岗位人员初级、中级职员评定申报工作的通知")
    ) is False
    # "招聘工作的通知"——排除词优先于包含词
    assert is_recruitment(_item("关于公开招聘工作的培训通知")) is False
    # 不可判定 → None（不臆测）
    assert is_recruitment(_item("树立和践行正确政绩观")) is None


# -- 4. 受控两轮样本：四类事件全检出且无误报 ------------------------------------


class _TwoRoundWorld:
    """受控世界：pku 源 3 条目，两轮之间构造四类事件 + 去抖/复现边界。

    close_round(seen_urls) 与 CLI 编排同口径：全部源 ingest 后以并集登记缺失。
    """

    def __init__(self) -> None:
        self.storage = Storage(":memory:")
        self.pipeline = SnapshotPipeline(self.storage, AppConfig())
        self.events: list = []

    def _round(self, items: list[RawItem]) -> None:
        self.storage.begin_round()
        self.events += self.pipeline.ingest(SourceId.PKU, items)
        seen = {i.url for i in items}
        self.events += self.pipeline.close_round(seen)

    def round1(self) -> None:
        self._round(
            [
                _item("2026年某高校教学科研岗位招聘启事 发布", published=date(2026, 2, 14)),
                _item("示例研究院诚聘博士后", url="https://example.edu.cn/j2.htm"),
                _item("示例大学光纤研究中心招聘公告", url="https://example.edu.cn/j3.htm"),
                # 非招聘通知：不应入库、不应产生任何事件
                _item("关于做好2026年下半年教师资格认定工作的通知", url="https://example.edu.cn/n1.htm"),
            ]
        )

    def round2(self) -> None:
        self._round(
            [
                # NEW_POSTING：新增条目
                _item("示例学院公开招聘实验技术人员", url="https://example.edu.cn/j4.htm"),
                # j1 标题不变（deadline 变化路径由 test_deadline_change_event_field_level 覆盖）
                _item("2026年某高校教学科研岗位招聘启事 发布", published=date(2026, 2, 14)),
                # j2 消失（第 1 轮缺失，去抖 N=3 不应立即报删除）
                # j3 消失且将在 round4 复现（删除后复现边界）
            ]
        )

    def round3(self) -> None:
        self._round([])

    def round4(self) -> None:
        self._round(
            [_item("示例大学光纤研究中心招聘公告", url="https://example.edu.cn/j3.htm")]
        )


def test_controlled_two_rounds_four_event_kinds_detected_no_false_positive() -> None:
    world = _TwoRoundWorld()
    world.round1()
    world.round2()

    j1 = "https://example.edu.cn/j1.htm"
    j2 = "https://example.edu.cn/j2.htm"
    j3 = "https://example.edu.cn/j3.htm"
    n1 = "https://example.edu.cn/n1.htm"

    # 首轮：3 条招聘 → 3 个 NEW_POSTING；通知 n1 完全不入库
    assert not any(e.url == n1 for e in world.events)

    # —— 无误报断言 ——
    # round1 只允许 NEW_POSTING
    assert all(e.round != 1 or e.kind == EventKind.NEW_POSTING for e in world.events)
    # round2：j1 无变化 → 不应有 j1 的任何事件（deadline 未变、hash 未变）
    assert not any(e.url == j1 and e.round == 2 for e in world.events)

    # —— 四类事件全检出 ——
    # 1) NEW_POSTING（首轮 j1/j2/j3 + 次轮 j4）
    assert sum(1 for e in world.events if e.kind == EventKind.NEW_POSTING) == 4
    # 2) DEADLINE_CHANGED：round2 的 j1 需要deadline 字段变化才检出——
    #    本受控世界的 j1 两轮标题/extra 完全一致 → deadline 恒 pending、无 diff，
    #    DEADLINE_CHANGED 由单元级用例覆盖（下方 test_deadline_change_event_field_level）。
    # 3) ANNOUNCEMENT_REMOVED：j2 连续缺失达 N=3（round2/3/4 缺失）
    assert not any(
        e.kind == EventKind.ANNOUNCEMENT_REMOVED and e.round == 2 for e in world.events
    ), "去抖 N=3：缺失第 1 轮不得报删除"
    # round3：j2/j3 连续缺失第 2 轮，仍不报
    world.round3()
    assert not any(
        e.kind == EventKind.ANNOUNCEMENT_REMOVED and e.round == 3 for e in world.events
    ), "去抖 N=3：缺失第 2 轮仍不得报删除"
    # round4：j3 复现（missed_then_reappeared），j2 连续缺失第 3 轮 → 删除成立
    world.round4()
    removed = [e for e in world.events if e.kind == EventKind.ANNOUNCEMENT_REMOVED]
    assert len(removed) == 1
    assert removed[0].url == j2
    assert removed[0].round == 4
    assert removed[0].detail["consecutive_missing_rounds"] == "3"
    # 4) CONTENT_CHANGED：j3 删除后复现边界
    reappeared = [
        e
        for e in world.events
        if e.kind == EventKind.CONTENT_CHANGED and e.url == j3 and e.round == 4
    ]
    assert len(reappeared) == 1
    assert reappeared[0].detail["note"] == "missed_then_reappeared"

    # 时间线可查询：j2 全历史
    timeline = world.storage.events_for_url(j2)
    assert [e.kind for e in timeline] == [EventKind.NEW_POSTING, EventKind.ANNOUNCEMENT_REMOVED]
    # j2 复现不该发生（删除成立后未再出现）
    assert all(e.kind != EventKind.CONTENT_CHANGED for e in timeline)


def test_deadline_change_event_field_level() -> None:
    """DEADLINE_CHANGED 单元用例：同一条目两轮 deadline 字段级变化（详情页正文口径）。"""
    st = Storage(":memory:")
    pipe = SnapshotPipeline(st, AppConfig())
    try:
        st.begin_round()
        body1 = "报名截止：2026-12-01。"
        ev1 = pipe.ingest(
            SourceId.PKU,
            [_item("某高校招聘启事", url="https://example.edu.cn/d1.htm")],
            bodies={"https://example.edu.cn/d1.htm": body1},
        )
        assert [e.kind for e in ev1] == [EventKind.NEW_POSTING]

        st.begin_round()
        body2 = "报名截止：2026-11-15。"  # 截止日改期（M4 基准边界样例）
        ev2 = pipe.ingest(
            SourceId.PKU,
            [_item("某高校招聘启事", url="https://example.edu.cn/d1.htm")],
            bodies={"https://example.edu.cn/d1.htm": body2},
        )
        kinds = [e.kind for e in ev2]
        assert kinds == [EventKind.DEADLINE_CHANGED]
        assert ev2[0].detail == {"deadline": "2026-12-01 -> 2026-11-15"}
    finally:
        st.close()


def test_hash_only_change_still_emits_content_changed() -> None:
    """哈希变但字段级 diff 无差异：正文实质变更事件不丢（diff 纪律）。"""
    st = Storage(":memory:")
    pipe = SnapshotPipeline(st, AppConfig())
    try:
        st.begin_round()
        pipe.ingest(
            SourceId.PKU,
            [_item("某高校招聘启事", url="https://example.edu.cn/h1.htm")],
            bodies={"https://example.edu.cn/h1.htm": "正文版本一。"},
        )
        st.begin_round()
        ev2 = pipe.ingest(
            SourceId.PKU,
            [_item("某高校招聘启事", url="https://example.edu.cn/h1.htm")],
            bodies={"https://example.edu.cn/h1.htm": "正文版本二，表述不同但无字段变化。"},
        )
        assert [e.kind for e in ev2] == [EventKind.CONTENT_CHANGED]
        assert ev2[0].detail["note"] == "hash_changed_no_field_diff"
    finally:
        st.close()


def test_pku_update_suffix_not_flagged_as_change() -> None:
    """pku 边界（M1 预警）：title 带"（更新）"后缀 ≠ 内容变更，不产生事件。"""
    st = Storage(":memory:")
    pipe = SnapshotPipeline(st, AppConfig())
    try:
        st.begin_round()
        ev1 = pipe.ingest(
            SourceId.PKU,
            [_item("2026年示例大学生命科学学院教学科研岗位招聘启事", url="https://example.edu.cn/u1.htm")],
        )
        assert [e.kind for e in ev1] == [EventKind.NEW_POSTING]
        st.begin_round()
        ev2 = pipe.ingest(
            SourceId.PKU,
            [
                _item(
                    "2026年示例大学生命科学学院教学科研岗位招聘启事（更新）",
                    url="https://example.edu.cn/u1.htm",
                )
            ],
        )
        # "（更新）"剥离后标题等价、无字段级 diff、hash 以剥离后标题计算 → 无事件
        assert [e.kind for e in ev2] == []
    finally:
        st.close()


# -- 5. JSON 序列化回环（快照持久化契约）----------------------------------------


def test_jobposting_json_roundtrip() -> None:
    item = _item(
        "示例大学全球史研究院招聘启事",
        source=SourceId.FUDAN,
        extra={"position": "教学科研人才"},
    )
    posting = extract_posting(item, body_text="报名截止：2026-12-01。")
    restored = type(posting).from_json(posting.to_json())
    assert restored.title == posting.title
    assert restored.url == posting.url
    assert restored.deadline.value == "2026-12-01"
    assert restored.deadline.evidence is not None
    assert restored.deadline.evidence.rule_name == "deadline_iso"
    assert restored.organization.value == posting.organization.value
    assert restored.content_hash == posting.content_hash


def test_evidence_chain_present_on_every_verified_field() -> None:
    item = _item(
        "博士后",
        source=SourceId.GAOXIAOJOB,
        extra={"position": "博士后", "org": "某高校", "discipline": "化学", "compensation": "面议"},
    )
    posting = extract_posting(item, body_text="报名截止日期：2026年3月1日。")
    for name, f in posting.fields().items():
        if f.status == FieldStatus.VERIFIED:
            assert f.evidence is not None, f"{name} verified 字段缺证据链"
            assert isinstance(f.evidence, Evidence)
            assert f.evidence.rule_name
