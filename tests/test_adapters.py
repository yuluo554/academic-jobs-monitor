"""M2 适配器 fixture 回放测试：全离线（K7）。

每源 ≥1 个"fixture HTML → RawItem 列表"断言（HANDOFF-M2 待办 4），含边界样例：
- gaoxiaojob：4 条目全部 published_on=None（列表页无日期）；
- pku：外链条目整条跳过；title 属性拆标题/日期；
- fudan：栏目导航链接不混入；
- nju：无日期导航条目整条跳过；标题取 title 属性（非截断文本）；
- acabridge：WAF 拦截页 → WAF_BLOCKED 失败隔离。

适配器请求统一走 Fetcher（K4/K5 契约）：测试用 FakeFetcher 回放 fixture 内容。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ajm.config import AppConfig, FailureCode, SourceId
from ajm.fetch import FetchResult
from ajm.sources import acabridge, fudan, gaoxiaojob, nju, pku
from ajm.sources.base import FetchOutcome

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "ajm" / "sources" / "fixtures"


class FakeFetcher:
    """回放指定 URL → fixture 内容；禁止真实网络（K7）。"""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def get(self, url: str, *, rate_limit_key: str) -> FetchResult:  # noqa: ARG002
        body = self._mapping.get(url)
        if body is None:
            return FetchResult(
                ok=False, failure_code=FailureCode.HTTP_ERROR,
                failure_detail=f"no fixture mapped for {url}",
            )
        return FetchResult(ok=True, status_code=200, body=body)


def _outcome(adapter, mapping: dict[str, str]) -> FetchOutcome:
    return adapter.fetch_list(FakeFetcher(mapping), AppConfig())  # type: ignore[arg-type]


def test_gaoxiaojob_replay() -> None:
    html = (FIXTURES / "gaoxiaojob" / "list.html").read_text(encoding="utf-8")
    out = _outcome(gaoxiaojob.GaoxiaojobAdapter(), {gaoxiaojob.LIST_URL: html})
    assert out.ok
    assert len(out.items) == 4
    first = out.items[0]
    assert first.source == SourceId.GAOXIAOJOB
    assert first.title == "博士后"
    assert first.url == "https://www.gaoxiaojob.com/job/detail/9000001.html"
    assert first.published_on is None  # 列表页无日期（M1 复核结论）
    assert all(i.published_on is None for i in out.items)
    assert [i.title for i in out.items] == [
        "博士后",
        "副教授/特别研究助理-绿色低碳研究团队",
        "讲师",
        "人事组织岗",
    ]


def test_pku_replay_with_external_link_skip() -> None:
    html = (FIXTURES / "pku" / "list.html").read_text(encoding="utf-8")
    out = _outcome(pku.PkuAdapter(), {pku.LIST_URL: html})
    assert out.ok
    # 5 条目中 1 条外链（postdocs.example.edu.cn）整条跳过
    assert len(out.items) == 4
    first = out.items[0]
    assert first.source == SourceId.PKU
    assert first.title == "2026年某高校教学科研岗位招聘启事"  # title 属性拆出，非截断文本
    assert first.url == "https://hr.pku.edu.cn/rczp/jxky/aa0000000000000000000000000000001.htm"
    assert first.published_on == date(2026, 2, 14)
    # 尾随空格与无空格两种 title 格式都解析成功
    dates = [i.published_on for i in out.items]
    assert dates == [date(2026, 2, 14), date(2026, 10, 13), date(2026, 10, 13), date(2026, 10, 14)]
    assert all(i.url.startswith("https://hr.pku.edu.cn/") for i in out.items)


def test_fudan_replay_excludes_nav_links() -> None:
    html = (FIXTURES / "fudan" / "list.html").read_text(encoding="utf-8")
    out = _outcome(fudan.FudanAdapter(), {fudan.LIST_URL: html})
    assert out.ok
    # 仅 4 条 column-news-item；栏目导航（list.htm）不混入
    assert len(out.items) == 4
    first = out.items[0]
    assert first.source == SourceId.FUDAN
    assert first.title == "示例大学全球史研究院招聘启事"
    assert first.url == "https://hr.fudan.edu.cn/1d/93/c15364a794003/page.htm"
    assert first.published_on == date(2026, 10, 12)
    assert all(not i.url.endswith("list.htm") for i in out.items)


def test_nju_replay_skips_undated_nav_entry() -> None:
    html = (FIXTURES / "nju" / "list.html").read_text(encoding="utf-8")
    out = _outcome(nju.NjuAdapter(), {nju.LIST_URL: html})
    assert out.ok
    # 5 个 li.news 中 1 条无日期导航（意见反馈）整条跳过
    assert len(out.items) == 4
    assert out.items[0].title == "关于做好2026年下半年示例学院教师资格认定工作的通知"
    assert "..." not in out.items[0].title  # 取 title 属性，非截断文本
    assert out.items[0].url == "https://hr.nju.edu.cn/e1/a1/c5977a844001/page.htm"
    assert out.items[0].published_on == date(2026, 9, 18)
    assert [i.published_on for i in out.items] == [
        date(2026, 9, 18), date(2026, 9, 10), date(2026, 9, 1), date(2026, 10, 14),
    ]


def test_acabridge_waf_blocked_isolation() -> None:
    html = (FIXTURES / "acabridge" / "waf_interstitial.html").read_text(encoding="utf-8")
    out = _outcome(acabridge.AcabridgeAdapter(), {acabridge.LIST_URL: html})
    assert not out.ok
    assert out.items == []
    assert out.failure is not None
    assert out.failure.code == FailureCode.WAF_BLOCKED
    assert "waf" in out.failure.detail.lower()


def test_registry_has_five_sources() -> None:
    from ajm.sources import registry

    assert registry.registered_sources() == [
        SourceId.ACABRIDGE,
        SourceId.FUDAN,
        SourceId.GAOXIAOJOB,
        SourceId.NJU,
        SourceId.PKU,
    ]


@pytest.mark.parametrize(
    "adapter_cls",
    [
        acabridge.AcabridgeAdapter,
        fudan.FudanAdapter,
        gaoxiaojob.GaoxiaojobAdapter,
        nju.NjuAdapter,
        pku.PkuAdapter,
    ],
)
def test_fetch_error_passthrough(adapter_cls) -> None:
    """上游 HTTP 失败按原因码透传为 FetchOutcome.failure，不抛异常（失败隔离）。"""
    fetcher = FakeFetcher({})  # 全部 URL 未映射 → HTTP_ERROR
    out = adapter_cls().fetch_list(fetcher, AppConfig())  # type: ignore[attr-defined]
    assert not out.ok
    assert out.failure is not None
    assert out.failure.code == FailureCode.HTTP_ERROR
