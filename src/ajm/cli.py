"""CLI 入口：jobsctl（与 Web 面板共享同一引擎层，双入口结论一致）。

骨架阶段：子命令占位 + 已实现能力立即可用；M2 起逐个填充实现。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from . import __version__
from .config import AppConfig, SourceId, default_config
from .fetch import Fetcher
from .models import ChangeEvent
from .sources import registry
from .storage import Storage


def _ensure_utf8_stdio() -> None:
    """非 UTF-8 管道（CI cp1252 等）下 print 中文会 UnicodeEncodeError。

    按编码探针 reconfigure；UTF-8 / 中文控制台 cp936 保持不动（本机习惯 -X utf8
    只救"我们敲的命令"，救不了 CI 与用户机器，入口守卫才救真实通路）。
    """
    for stream in (sys.stdout, sys.stderr):
        enc = getattr(stream, "encoding", "") or ""
        if enc.lower().replace("-", "") not in ("utf8", "cp936", "gbk", "gb2312"):
            try:
                stream.reconfigure(encoding="utf-8", errors="strict")
            except (AttributeError, OSError):  # pragma: no cover
                pass


def _cmd_crawl(args: argparse.Namespace) -> int:
    """抓取一轮：M2 实现 5 源适配器后此命令即全链路第一步。"""
    cfg: AppConfig = default_config()
    source_ids = (
        [SourceId(s) for s in args.source.split(",")] if args.source else None
    )
    with Fetcher(cfg) as fetcher:
        outcomes = registry.fetch_all(source_ids, fetcher, cfg)
    ok_count = 0
    for out in outcomes:
        if out.ok:
            ok_count += 1
            print(f"[OK]   {out.source}: {len(out.items)} items")
        else:
            assert out.failure is not None
            print(
                f"[FAIL] {out.source}: {out.failure.code.value} — {out.failure.detail}",
                file=sys.stderr,
            )
    codes = Counter(
        out.failure.code.value for out in outcomes if out.failure is not None
    )
    print(
        f"\nround summary: {ok_count}/{len(outcomes)} sources ok; "
        f"failure codes: {dict(codes) or 'none'}"
    )
    return 0 if ok_count else 1


def _cmd_sources(_: argparse.Namespace) -> int:
    """列出已注册适配器（骨架验收用）。"""
    for sid in registry.registered_sources():
        print(sid)
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    """抽取演示：对最近一轮 raw 留证或 fixture 跑规则族，打印字段与证据链。"""
    from pathlib import Path

    from ajm.extract.engine import extract_posting, is_recruitment
    from ajm.extract.rules import RULES

    cfg: AppConfig = default_config()
    paths: list[Path] = []
    if args.fixture:
        fx = Path(__file__).resolve().parent / "sources" / "fixtures" / args.fixture
        if not fx.exists():
            print(f"unknown source fixture: {args.fixture}", file=sys.stderr)
            return 2
        paths = sorted(fx.glob("*.html"))
    else:
        verify = cfg.raw_dir / "verify"
        paths = sorted(verify.glob("*.html")) if verify.exists() else []
    if not paths:
        print("no html available (run crawl first, or pass --fixture <source>)", file=sys.stderr)
        return 2

    from ajm.sources import registry as _reg

    for path in paths:
        source_id = args.fixture if args.fixture else path.stem
        try:
            SourceId(source_id)
        except ValueError:
            continue
        factory = _reg._REGISTRY.get(SourceId(source_id))
        if factory is None:
            continue
        html = path.read_text(encoding="utf-8")
        # 直接复用适配器解析假设：无需网络——用 FakeFetcher 回放（与测试同口径，K7）。
        from ajm.fetch import FetchResult

        def _replay_get(url: str, *, rate_limit_key: str, _body: str = html) -> FetchResult:
            return FetchResult(ok=True, status_code=200, body=_body)

        class _Replay:
            get = staticmethod(_replay_get)

        adapter = factory()
        outcome = adapter.fetch_list(_Replay(), cfg)  # type: ignore[attr-defined]
        if not outcome.ok:
            assert outcome.failure is not None
            print(f"[FAIL] {source_id}: {outcome.failure.code.value}")
            continue
        print(f"[OK]   {source_id}: {len(outcome.items)} items")
        for item in outcome.items:
            cls = is_recruitment(item)
            tag = {True: "recruit", False: "non-recruit", None: "unknown"}.get(cls, "?")
            posting = extract_posting(item)
            print(f"  - [{tag}] {posting.title}")
            for name, f in posting.fields().items():
                ev = f"- ({f.evidence.rule_name})" if f.evidence else ""
                cands = f" candidates={f.candidates}" if f.ambiguous else ""
                print(f"      {name}: {f.status.value}={f.value}{cands} {ev}")
    print(f"\nregistered deadline rules: {[r.name for r in RULES]}")
    return 0


def _cmd_snapshot(args: argparse.Namespace) -> int:
    """真实抓取一轮 → 抽取 → 快照入库 → diff 事件（四类事件时间线可查询）。"""
    from ajm.snapshot import SnapshotPipeline

    cfg: AppConfig = default_config()
    storage = Storage(cfg.db_path)
    pipeline = SnapshotPipeline(storage, cfg)
    try:
        round_no = storage.begin_round()
        print(f"round {round_no} begin")
        source_ids = (
            [SourceId(s) for s in args.source.split(",")] if args.source else None
        )
        total_events: list[ChangeEvent] = []
        seen_urls: set[str] = set()
        with Fetcher(cfg) as fetcher:
            outcomes = registry.fetch_all(source_ids, fetcher, cfg)
        for out in outcomes:
            if out.ok:
                seen_urls.update(item.url for item in out.items)
                events = pipeline.ingest(out.source, out.items)
                total_events.extend(events)
                print(f"[OK]   {out.source}: {len(out.items)} items, {len(events)} events")
            else:
                assert out.failure is not None
                print(
                    f"[FAIL] {out.source}: {out.failure.code.value} — {out.failure.detail}",
                    file=sys.stderr,
                )
        total_events.extend(pipeline.close_round(seen_urls))
        for ev in total_events:
            print(f"  [{ev.kind.value}] {ev.url} {ev.detail}")
        codes = Counter(
            out.failure.code.value for out in outcomes if out.failure is not None
        )
        print(
            f"\nround {round_no} summary: "
            f"{sum(1 for o in outcomes if o.ok)}/{len(outcomes)} sources ok; "
            f"events: {len(total_events)}; failure codes: {dict(codes) or 'none'}"
        )
        return 0
    finally:
        storage.close()


def _cmd_timeline(args: argparse.Namespace) -> int:
    """查询任意 URL 的变更时间线（题面任务 3 可查询性）。"""
    cfg: AppConfig = default_config()
    storage = Storage(cfg.db_path)
    try:
        if args.url:
            events = storage.events_for_url(args.url)
        else:
            round_no = storage.current_round()
            events = storage.events_for_round(round_no) if round_no else []
        if not events:
            print("(no events)")
            return 0
        for ev in events:
            print(f"round {ev.round} [{ev.kind.value}] {ev.url} {ev.detail}")
        return 0
    finally:
        storage.close()


def _cmd_feed(args: argparse.Namespace) -> int:
    """订阅匹配 → RSS + HTML 摘要落盘（cache/feeds/；题面任务 4）。

    匹配域：最近一轮事件（缺省）或 --url 指定条目的全历史；
    标题从快照库补齐；未配置订阅文件时提示并返回 2。
    """

    from ajm.subscribe import FeedEntry, SubscriptionConfig, match_events, render_html, render_rss

    cfg: AppConfig = default_config()
    sub = SubscriptionConfig.from_file(cfg.subscribe_file)
    if not sub.rules:
        print(
            f"no subscriptions configured: copy subscribe.example.yaml to "
            f"{cfg.subscribe_file} and edit it",
            file=sys.stderr,
        )
        return 2

    storage = Storage(cfg.db_path)
    try:
        if args.url:
            events = storage.events_for_url(args.url)
            round_no = None
        else:
            round_no = storage.current_round()
            events = storage.events_for_round(round_no) if round_no else []
        if not events:
            print("(no events to feed)")
            return 0
        titles = storage.all_titles()
        matched = match_events(sub, events, titles)
        entries = [
            FeedEntry(event=ev, title=titles.get(ev.url, ev.detail.get("title", ev.url)))
            for hits in matched.values()
            for ev in hits
        ]
    finally:
        storage.close()

    feed_dir = cfg.storage_dir / "feeds"
    feed_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"round{round_no}" if round_no else "url-history"
    rss_path = feed_dir / f"feed-{stamp}.xml"
    html_path = feed_dir / f"feed-{stamp}.html"
    rss_path.write_text(
        render_rss(entries, channel_title="学术招聘监控推送", channel_link="https://localhost/"),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(entries, channel_title="学术招聘监控推送"), encoding="utf-8"
    )
    print(f"rules: {len(sub.rules)}, matched entries: {len(entries)}")
    for rule_name, hits in matched.items():
        print(f"  [{rule_name}] {len(hits)} hits")
    print(f"rss:  {rss_path}")
    print(f"html: {html_path}")
    return 0


def _cmd_bench(_: argparse.Namespace) -> int:
    """内置基准：真值抽取逐字段准确率 + 受控变更样本检出（题面任务 5）。"""
    from ajm.bench.change_cases import run_change_cases
    from ajm.bench.truth import run_truth

    report = run_truth()
    print("== 真值抽取基准（src/ajm/bench/fixtures/truth.json）==")
    field_scores = report.field_scores()
    for name, s in field_scores.items():
        print(
            f"  {name:<13} {s['correct']}/{s['total']} = {s['accuracy']:.1%}"
            f"  (ambiguous_right={s['ambiguous_right']}, miss={s['miss_should_verify']},"
            f" hallucinated={s['hallucinated']})"
        )
    total = sum(s["total"] for s in field_scores.values())
    correct = sum(s["correct"] for s in field_scores.values())
    print(
        f"  overall {correct}/{total} = {report.overall_accuracy():.1%}; "
        f"classification {report.classified_correct}/{report.classified_total}"
    )
    for failure in report.failures:
        print(f"  [MISS] {failure}")

    print("\n== 变更检测基准（src/ajm/bench/fixtures/change_cases）==")
    all_ok = True
    for name, change_report in run_change_cases():
        all_ok = all_ok and change_report.ok
        print(f"  {name}: {change_report.summary()}")
        for miss in change_report.missed:
            print(f"    [MISSED] {miss}")
        for fp in change_report.false_positives:
            print(f"    [FALSE-POSITIVE] {fp}")
    failures = len(report.failures)
    if failures or not all_ok:
        print(f"\nbench: NOT PASSED ({failures} truth failures, change_cases ok={all_ok})")
        return 1
    print(f"\nbench: PASSED (overall {report.overall_accuracy():.1%}, 阈值口径见 README)")
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    """启动本地 Web 面板（M5）：只读快照库视图，与 CLI 共享同一编排函数。"""
    from ajm.webapp.app import run as run_webapp

    print(f"web: http://{args.host}:{args.port}  (Ctrl+C 退出)")
    run_webapp(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobsctl",
        description="高校学术招聘聚合监控器 CLI（多源抓取 · 字段抽取 · 快照 diff · 订阅推送）",
    )
    parser.add_argument("--version", action="version", version=f"jobsctl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_crawl = sub.add_parser("crawl", help="抓取一轮列表页（M2）")
    p_crawl.add_argument(
        "--source",
        default="",
        help="逗号分隔的源 id（gaoxiaojob,acabridge,pku,fudan,nju）；缺省 = 全部已注册源",
    )
    p_crawl.set_defaults(func=_cmd_crawl)

    sub.add_parser("sources", help="列出已注册适配器").set_defaults(func=_cmd_sources)

    p_extract = sub.add_parser("extract", help="结构化字段抽取演示（M3，fixture/raw 回放）")
    p_extract.add_argument(
        "--fixture",
        default="",
        help="指定源 id 用其回放 fixture 演示；缺省用 cache/raw/verify 下的最近留证",
    )
    p_extract.set_defaults(func=_cmd_extract)

    p_snap = sub.add_parser("snapshot", help="抓取一轮 → 抽取 → 快照 diff 事件（M3）")
    p_snap.add_argument(
        "--source",
        default="",
        help="逗号分隔的源 id；缺省 = 全部已注册源",
    )
    p_snap.set_defaults(func=_cmd_snapshot)

    p_tl = sub.add_parser("timeline", help="查询变更时间线（M3）")
    p_tl.add_argument("--url", default="", help="指定 URL 查询；缺省打印最近一轮全部事件")
    p_tl.set_defaults(func=_cmd_timeline)
    sub.add_parser("feed", help="订阅匹配 → RSS/HTML 摘要（M4）")
    p_feed_url = sub.choices["feed"]
    p_feed_url.add_argument(
        "--url", default="", help="指定 URL 出其全历史事件的订阅命中；缺省用最近一轮"
    )
    p_feed_url.set_defaults(func=_cmd_feed)
    sub.add_parser("bench", help="内置基准：真值抽取 + 受控变更样本（M4）").set_defaults(
        func=_cmd_bench
    )
    p_web = sub.add_parser("web", help="启动本地 Web 面板（M5）")
    p_web.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    p_web.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    p_web.set_defaults(func=_cmd_web)
    return parser


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
