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
from .sources import registry


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


def _cmd_extract(_: argparse.Namespace) -> int:
    print("extract: not implemented yet (M3)")
    return 2


def _cmd_snapshot(_: argparse.Namespace) -> int:
    print("snapshot: not implemented yet (M3)")
    return 2


def _cmd_feed(_: argparse.Namespace) -> int:
    print("feed: not implemented yet (M4)")
    return 2


def _cmd_bench(_: argparse.Namespace) -> int:
    print("bench: not implemented yet (M4)")
    return 2


def _cmd_web(_: argparse.Namespace) -> int:
    print("web: not implemented yet (M5)")
    return 2


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
    sub.add_parser("extract", help="结构化字段抽取（M3）").set_defaults(func=_cmd_extract)
    sub.add_parser("snapshot", help="快照入库与变更检测（M3）").set_defaults(func=_cmd_snapshot)
    sub.add_parser("feed", help="生成 RSS / HTML 摘要（M4）").set_defaults(func=_cmd_feed)
    sub.add_parser("bench", help="内置基准：真值抽取 + 受控变更样本（M4）").set_defaults(
        func=_cmd_bench
    )
    sub.add_parser("web", help="启动本地 Web 面板（M5）").set_defaults(func=_cmd_web)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
