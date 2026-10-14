"""fixtures 结构回归：全离线（K7），校验入仓 fixture 的解析假设不漂移。

这是 M1 结构复核的固化：适配器（M2）依赖的定位规则若有变化，此测试先行报警。
"""

from __future__ import annotations

import re
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "src" / "ajm" / "sources" / "fixtures"


def _read(sid: str, name: str) -> str:
    return (FIXTURES / sid / name).read_text(encoding="utf-8")


def _no_real_org_names(text: str) -> None:
    """K8 自查：fixture 中不得出现真实院校名（假名白名单是唯一合法单位名）。"""
    # 城市名（北京/上海等）是公开地域元数据不算院校名，故用校名专名做黑名单
    banned = ["北京大学", "复旦", "南京大学", "清华大学", "浙江大学", "中国科学院大学"]
    for w in banned:
        assert w not in text, f"fixture 疑含真实院校名: {w}"


def test_gaoxiaojob_list_structure() -> None:
    html = _read("gaoxiaojob", "list.html")
    items = re.findall(r'href="(/job/detail/\d+\.html)"', html)
    assert len(items) == 4
    assert re.search(r'<div class="position">\s*<h6>', html)
    assert '<span class="school"> 某高校 </span>' in html
    assert "20" + "26-" not in html  # 列表页无发布日期（复核结论）
    _no_real_org_names(html)


def test_acabridge_waf_interstitial() -> None:
    html = _read("acabridge", "waf_interstitial.html")
    assert "aliyun_waf_aa" in html
    assert "aliyunCaptcha-sliding-slider" in html
    assert not re.findall(r'href="[^"]*job[^"]*"', html)  # 无可解析条目


def test_pku_list_structure() -> None:
    html = _read("pku", "list.html")
    titles = re.findall(r'title="([^"]+) 发布日期：(\d{4}-\d{2}-\d{2}) ?"', html)
    assert len(titles) == 5
    assert titles[0] == ("2026年某高校教学科研岗位招聘启事", "2026-02-14")
    assert html.count("gp-ellipsis") >= 5
    _no_real_org_names(html)


def test_fudan_list_structure() -> None:
    html = _read("fudan", "list.html")
    items = re.findall(
        r'<a class="column-news-item[^"]*" href="([^"]+)">'
        r'<span class="column-news-title">([^<]+)</span>'
        r'<span class="column-news-date[^"]*">(\d{4}-\d{2}-\d{2})</span>',
        html,
    )
    assert len(items) == 4
    assert items[0][2] == "2026-10-12"
    # 栏目导航链接不得被误当条目
    assert "column-item-link" in html
    _no_real_org_names(html)


def test_nju_list_structure() -> None:
    html = _read("nju", "list.html")
    items = re.findall(
        r"<li class=\"news [^\"]*\"><span class=\"news_title\"><a href='([^']+)'[^>]*"
        r"title='([^']+)'>[^<]*</a></span><span class=\"news_meta\">(\d{4}-\d{2}-\d{2})</span>",
        html,
    )
    assert len(items) == 4
    assert items[0][2] == "2026-09-18"
    # 边界：无日期导航条目存在且必须可与其区分
    assert "lyb/list.htm" in html
    _no_real_org_names(html)


def test_every_source_has_notes() -> None:
    for sid in ("gaoxiaojob", "acabridge", "pku", "fudan", "nju"):
        assert (FIXTURES / sid / "notes.md").exists(), f"{sid} 缺 notes.md"
