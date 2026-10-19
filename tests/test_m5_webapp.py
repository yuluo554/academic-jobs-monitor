"""M5 离线测试：Web 面板路由 + 双形态三方对账（K7 全离线，tmp 快照库）。

三方对账口径（HANDOFF-M5 待办 2）：
  CLI stdout（jobsctl timeline/feed/bench 打印）= 直调共享视图函数（webapp.views）
  = 面板渲染（webapp.app 路由）。
同一 tmp 数据源断言一致；jobsctl bench 退出码 1 是当前诚实扣分项，对账不断言 exit==0。
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ajm.cli import main
from ajm.config import AppConfig, SourceId
from ajm.models import RawItem
from ajm.snapshot import SnapshotPipeline
from ajm.storage import Storage
from ajm.webapp import views
from ajm.webapp.app import create_app


def _seed_config(tmp_path: Path) -> AppConfig:
    """tmp 快照库 + 两轮受控数据：round1 新增、round2 截止日改期（假名 K8 合规）。"""
    cfg = AppConfig()
    cfg.storage_dir = tmp_path / "cache"  # CLI default_config 以 cwd 解析 cache/ajm.sqlite3
    cfg.raw_dir = cfg.storage_dir / "raw"
    cfg.db_path = cfg.storage_dir / "ajm.sqlite3"
    cfg.subscribe_file = tmp_path / "subscribe.yaml"
    cfg.subscribe_file.write_text(
        "subscriptions:\n"
        "  - name: 博士后\n"
        '    keywords: ["博士后"]\n'
        "    kinds: [new_posting, deadline_changed]\n",
        encoding="utf-8",
    )
    storage = Storage(cfg.db_path)
    try:
        pipeline = SnapshotPipeline(storage, cfg)
        url = "https://example.invalid/m5-a"
        storage.begin_round()
        item1 = RawItem(
            source=SourceId.PKU,
            url=url,
            title="示例大学2026年博士后招聘公告",
            published_on=None,
        )
        pipeline.ingest(SourceId.PKU, [item1], bodies={url: "报名截止日期：2026年11月30日"})
        storage.begin_round()
        item2 = RawItem(
            source=SourceId.PKU,
            url=url,
            title="示例大学2026年博士后招聘公告",
            published_on=None,
        )
        pipeline.ingest(SourceId.PKU, [item2], bodies={url: "报名截止日期：2026年12月15日"})
        pipeline.close_round({url})
    finally:
        storage.close()
    return cfg


@pytest.fixture()
def seeded_cfg(tmp_path: Path) -> AppConfig:
    return _seed_config(tmp_path)


@pytest.fixture()
def client(seeded_cfg: AppConfig) -> TestClient:
    return TestClient(create_app(seeded_cfg))


# -- 路由离线测试 ---------------------------------------------------------------


def test_pages_render_with_zero_external_links(client: TestClient) -> None:
    for path in ("/", "/timeline", "/subscribe", "/bench"):
        resp = client.get(path)
        assert resp.status_code == 200
        body = resp.text
        # 零外链单页：无 http(s) 外链资源引用、无 CDN/图片/字体（断网可演示）
        for marker in ("http://cdn", "https://cdn", "<script src", "<link ", "<img "):
            assert marker not in body, f"{path} 含外链资源 {marker}"
        assert "<html" not in body.lower() or path == "/"  # 内联片段式页面即可


def test_docs_disabled(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_index_lists_snapshot_rows(client: TestClient) -> None:
    body = client.get("/").text
    assert "示例大学2026年博士后招聘公告" in body
    assert "2026-12-15" in body  # deadline verified 出镜（round2 最新值）
    assert "在榜" in body


def test_timeline_page_shows_deadline_change(client: TestClient) -> None:
    body = client.get("/timeline").text
    assert "截止日变更" in body
    assert "2026-11-30 -&gt; 2026-12-15" in body  # 页面 HTML 转义


def test_bench_page_reports_field_scores(client: TestClient) -> None:
    body = client.get("/bench").text
    assert "overall" in body
    assert "2026-10" not in body  # 报告只含基准数字，不含抓取数据
    assert "变更检测基准" in body


def test_readonly_panel_does_not_write_db(seeded_cfg: AppConfig) -> None:
    before = seeded_cfg.db_path.read_bytes()
    client = TestClient(create_app(seeded_cfg))
    for path in ("/", "/timeline", "/subscribe", "/bench"):
        client.get(path)
    assert seeded_cfg.db_path.read_bytes() == before  # 只读面板不改库


# -- 三方对账：CLI stdout = 直调视图函数 = 面板渲染 ------------------------------


def _cli_stdout(cfg: AppConfig, *argv: str, expect_code: int = 0) -> str:
    import os

    cwd = os.getcwd()
    buf = io.StringIO()
    try:
        os.chdir(cfg.storage_dir.parent)  # 种子库 = <cwd>/cache/ajm.sqlite3，对齐 CLI 解析
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(argv))
    finally:
        os.chdir(cwd)
    assert code == expect_code, f"CLI {argv} 退出码 {code} != {expect_code}"
    return buf.getvalue()


def test_reconciliation_timeline_cli_views_page(seeded_cfg: AppConfig, client: TestClient) -> None:
    """时间线三方对账：CLI 打印的事件集合 = views.timeline_events = /timeline 页渲染。"""
    stdout = _cli_stdout(seeded_cfg, "timeline")
    events = views.timeline_events(seeded_cfg)
    page = client.get("/timeline").text

    # 直调 = CLI：同一事件集合（kind/url/round/detail）；CLI timeline 缺省打最近一轮
    cli_events = []
    for line in stdout.splitlines():
        if line.startswith("round "):
            parts = line.split(maxsplit=3)
            cli_events.append((parts[1], parts[2], parts[3]))
    assert len(cli_events) == len(events) == 1  # round2 只产出 deadline_changed
    assert any("2026-11-30 -> 2026-12-15" in line for line in stdout.splitlines())
    # 面板 = 直调：deadline 变更值出镜，事件条数一致
    assert "2026-11-30 -&gt; 2026-12-15" in page  # 页面 HTML 转义
    assert page.count("<tr>") - 1 == len(events)


def test_reconciliation_feed_cli_views_page(seeded_cfg: AppConfig, client: TestClient) -> None:
    """订阅预览三方对账：CLI feed 命中数 = views.feed_preview = /subscribe 页。"""
    stdout = _cli_stdout(seeded_cfg, "feed")
    matched, titles = views.feed_preview(seeded_cfg)
    page = client.get("/subscribe").text

    assert list(matched.keys()) == ["博士后"]
    assert len(matched["博士后"]) == 1  # 缺省 = 最近一轮，round2 只有 deadline_changed
    assert "[博士后] 1 hits" in stdout
    assert "规则：博士后（1 条命中）" in page
    assert "示例大学2026年博士后招聘公告" in page
    assert titles  # 标题来自快照库，匹配域一致


def test_reconciliation_bench_cli_views_report(seeded_cfg: AppConfig, client: TestClient) -> None:
    """基准三方对账：CLI bench 数字 = views.bench_report = /bench 页（与库无关，恒定）。"""
    # 用 bench CLI 真实退出码路径（当前诚实扣分项 exit==1，勿断言 0）
    stdout = _cli_stdout(seeded_cfg, "bench", expect_code=1)
    report = views.bench_report()
    page = client.get("/bench").text

    overall = report["overall"]
    assert f"{overall['correct']}/{overall['total']}" in page
    # CLI 与视图层同一 bench 入口：overall 数字必须一致（当前 108/109 = 99.1%）
    assert f"{overall['correct']}/{overall['total']}" == "108/109"
    assert "108/109" in stdout
    for _name, score in report["fields"].items():
        assert f"{score['accuracy']:.1%}" in page
    # 失败明细不隐藏：CLI 与面板同列唯一扣分项
    assert report["failures"], "当前必须保留诚实扣分项（position 句式缺口）"
    assert "NOT PASSED" in stdout and "NOT PASSED" in page


def test_views_empty_database_renders_gracefully(tmp_path: Path) -> None:
    """空库（首轮未跑）：面板各页空态可渲染、视图层返回空集合。"""
    cfg = AppConfig()
    cfg.storage_dir = tmp_path
    cfg.db_path = tmp_path / "empty.sqlite3"
    cfg.subscribe_file = tmp_path / "none.yaml"
    assert views.list_snapshots(cfg) == []
    assert views.timeline_events(cfg) == []
    matched, _ = views.feed_preview(cfg)
    assert matched == {}
    client = TestClient(create_app(cfg))
    for path in ("/", "/timeline", "/subscribe"):
        assert client.get(path).status_code == 200


def test_url_scoped_timeline_and_subscribe(seeded_cfg: AppConfig, client: TestClient) -> None:
    """--url 语义对账：指定 URL 时出全历史（CLI/视图/面板三处同语义）。"""
    url = "https://example.invalid/m5-a"
    events = views.timeline_events(seeded_cfg, url=url)
    assert len(events) == 2
    page = client.get(f"/timeline?url={url}").text
    assert "URL 全历史" in page
    assert "2026-11-30 -&gt; 2026-12-15" in page  # 页面 HTML 转义


def test_cli_web_help_mentions_options() -> None:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        with pytest.raises(SystemExit) as exc:
            main(["web", "--help"])
    assert exc.value.code == 0
    assert "--port" in buf.getvalue()
    assert "--host" in buf.getvalue()


def test_views_json_roundtrip_matches_storage_extracted_json(seeded_cfg: AppConfig) -> None:
    """视图层字段结构与快照库 extracted_json 同源（对账数据单一来源）。"""
    storage = Storage(seeded_cfg.db_path)
    try:
        raw = storage._conn.execute(
            "SELECT extracted_json FROM snapshots LIMIT 1"
        ).fetchone()["extracted_json"]
    finally:
        storage.close()
    rows = views.list_snapshots(seeded_cfg)
    assert rows[0].fields == json.loads(raw)["fields"]
    assert rows[0].field_display("deadline") == "2026-12-15"
