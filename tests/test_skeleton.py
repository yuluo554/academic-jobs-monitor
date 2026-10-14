"""骨架冒烟测试：数据模型不变量 + 失败隔离调度 + CLI。全离线，不触网。"""

from __future__ import annotations

import json

import pytest

from ajm.cli import main
from ajm.config import AppConfig, FailureCode, SourceId
from ajm.fetch import Fetcher
from ajm.models import ExtractedField, content_hash, normalize_text
from ajm.sources import registry
from ajm.sources.base import FetchOutcome
from ajm.storage import Storage

# -- models ------------------------------------------------------------------


def test_content_hash_is_deterministic_and_whitespace_insensitive() -> None:
    a = content_hash("报名截止 2026 年 12 月 1 日")
    b = content_hash("报名截止\n 2026 年 12 月 1 日  ")
    assert a == b
    assert a == content_hash("报名截止 2026 年 12 月 1 日")  # 同输入恒定输出


def test_extracted_field_pending_is_default_gate() -> None:
    f = ExtractedField.unextracted("deadline")
    assert f.status == "pending"
    assert f.value is None


def test_normalize_text() -> None:
    assert normalize_text("a \n b\tc") == "a b c"


# -- 失败隔离 -----------------------------------------------------------------


class _BoomAdapter:
    source_id = SourceId.PKU

    def fetch_list(self, fetcher: Fetcher, config: AppConfig) -> FetchOutcome:
        raise RuntimeError("boom")


class _OkAdapter:
    source_id = SourceId.FUDAN

    def fetch_list(self, fetcher: Fetcher, config: AppConfig) -> FetchOutcome:
        return FetchOutcome(source=self.source_id, items=[])


def test_fetch_source_isolates_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(registry._REGISTRY, SourceId.PKU, _BoomAdapter)
    monkeypatch.setitem(registry._REGISTRY, SourceId.FUDAN, _OkAdapter)

    out_pku = registry.fetch_source(SourceId.PKU, None, AppConfig())  # type: ignore[arg-type]
    out_fudan = registry.fetch_source(SourceId.FUDAN, None, AppConfig())  # type: ignore[arg-type]

    assert not out_pku.ok
    assert out_pku.failure is not None
    assert out_pku.failure.code == FailureCode.UNKNOWN
    assert out_fudan.ok  # 异常源不影响其他源


def test_fetch_all_reports_each_source_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(registry._REGISTRY, SourceId.PKU, _BoomAdapter)
    monkeypatch.setitem(registry._REGISTRY, SourceId.FUDAN, _OkAdapter)
    monkeypatch.setattr(
        registry, "registered_sources", lambda: [SourceId.PKU, SourceId.FUDAN]
    )

    outcomes = registry.fetch_all(None, None, AppConfig())  # type: ignore[arg-type]
    assert [o.ok for o in outcomes] == [False, True]


# -- storage ------------------------------------------------------------------


def test_storage_round_and_event_timeline(tmp_path) -> None:
    st = Storage(tmp_path / "t.sqlite3")
    try:
        assert st.current_round() == 0
        r1 = st.begin_round()
        assert r1 == 1

        is_new = st.upsert_snapshot(
            url="http://example.com/j1",
            source=SourceId.PKU,
            title="某高校招聘",
            content_hash="abc",
            round_no=r1,
            extracted_json=None,
        )
        assert is_new
        assert not st.upsert_snapshot(
            url="http://example.com/j1",
            source=SourceId.PKU,
            title="某高校招聘",
            content_hash="def",
            round_no=2,
            extracted_json=json.dumps({"deadline": "2026-12-01"}),
        )

        from ajm.config import EventKind
        from ajm.models import ChangeEvent

        st.append_event(
            ChangeEvent(
                kind=EventKind.DEADLINE_CHANGED,
                url="http://example.com/j1",
                source=SourceId.PKU,
                round=2,
                detail={"deadline": "2026-12-01 -> 2026-11-15"},
            )
        )
        timeline = st.events_for_url("http://example.com/j1")
        assert len(timeline) == 1
        assert timeline[0].kind == EventKind.DEADLINE_CHANGED
        assert timeline[0].detail["deadline"] == "2026-12-01 -> 2026-11-15"
    finally:
        st.close()


# -- cli ----------------------------------------------------------------------


def test_cli_sources_and_milestone_gates(capsys) -> None:
    assert main(["sources"]) == 0
    # extract 已在 M3 实现（fixture 回放演示）；feed/bench/web 仍按里程碑返回 2
    assert main(["extract", "--fixture", "gaoxiaojob"]) == 0
    out = capsys.readouterr().out
    assert "registered deadline rules" in out
    assert main(["feed"]) == 2
    assert main(["bench"]) == 2
    assert main(["web"]) == 2
    out = capsys.readouterr().out
    assert "not implemented" in out
