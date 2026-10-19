"""本地 Web 面板（M5，题面交付"本地 Web 面板 + CLI 双形态"）。

纪律：
- 零依赖内联单页：模板字符串内联、0 外链（无 CDN/字体/图片），断网可演示；
- 只读面板：不触发抓取、不改库（快照/事件只读查询，复用 webapp.views）；
- /docs 关闭（不暴露 OpenAPI 面）；
- 双形态对账：视图数据全部来自 webapp.views（CLI 同源），见 tests 对账测试。
"""

from __future__ import annotations

import html
import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import views

_KIND_LABELS = {
    "new_posting": "新增岗位",
    "deadline_changed": "截止日变更",
    "content_changed": "内容变更",
    "announcement_removed": "公告删除",
}


def _esc(v: object) -> str:
    return html.escape(str(v if v is not None else ""))


def create_app(cfg=None) -> FastAPI:
    """应用工厂（测试注入 tmp 配置；生产走 default_config）。"""
    if cfg is None:
        from ajm.config import default_config

        cfg = default_config()
    app = FastAPI(title="学术招聘监控面板", docs_url=None, redoc_url=None)
    app.state.cfg = cfg

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        rows = views.list_snapshots(cfg)
        parts = [
            "<h1>学术招聘监控面板</h1>",
            '<nav><a href="/">条目列表</a> · <a href="/timeline">变更时间线</a> · '
            '<a href="/subscribe">订阅预览</a> · <a href="/bench">基准报告</a></nav>',
            "<h2>条目列表（快照库）</h2>",
            f"<p>共 {_esc(len(rows))} 条</p>",
            "<table><tr><th>来源</th><th>标题</th><th>岗位</th><th>单位</th>"
            "<th>学科方向</th><th>待遇</th><th>截止日期</th><th>轮次</th><th>状态</th></tr>",
        ]
        for r in rows:
            status = f"缺失自 round {r.removed_since}" if r.removed_since else "在榜"
            fields_cells = "".join(
                f"<td>{_esc(r.field_display(name))}</td>" for name in views._FIELD_LABELS
            )
            parts.append(
                f"<tr><td>{_esc(r.source)}</td>"
                f'<td><a href="/timeline?url={_esc(r.url)}">{_esc(r.title)}</a></td>'
                f"{fields_cells}"
                f"<td>{r.first_round}–{r.last_seen_round}</td>"
                f"<td>{_esc(status)}</td></tr>"
            )
        parts.append("</table>")
        parts.append(_page_footer())
        return "\n".join(parts)

    @app.get("/timeline", response_class=HTMLResponse)
    def timeline(url: str = "") -> str:
        events = views.timeline_events(cfg, url=url)
        scope = f"URL 全历史：{_esc(url)}" if url else "最近一轮"
        parts = [
            "<h1>变更时间线</h1>",
            '<nav><a href="/">条目列表</a> · <a href="/timeline">变更时间线</a> · '
            '<a href="/subscribe">订阅预览</a> · <a href="/bench">基准报告</a></nav>',
            f"<h2>{scope}</h2>",
            f"<p>共 {_esc(len(events))} 条事件</p>",
            "<table><tr><th>轮次</th><th>类型</th><th>标题</th><th>来源</th>"
            "<th>详情</th><th>检出时间</th></tr>",
        ]
        for ev in events:
            kind = _KIND_LABELS.get(ev.kind, ev.kind)
            detail = json.dumps(ev.detail, ensure_ascii=False) if ev.detail else ""
            title = (
                f'<a href="/timeline?url={_esc(ev.url)}">{_esc(ev.title)}</a>'
                if ev.title
                else _esc(ev.url)
            )
            parts.append(
                f"<tr><td>{ev.round}</td><td>{_esc(kind)}</td><td>{title}</td>"
                f"<td>{_esc(ev.source)}</td><td>{_esc(detail)}</td>"
                f"<td>{_esc(ev.detected_at)}</td></tr>"
            )
        parts.append("</table>")
        parts.append(_page_footer())
        return "\n".join(parts)

    @app.get("/subscribe", response_class=HTMLResponse)
    def subscribe(url: str = "") -> str:
        matched, titles = views.feed_preview(cfg, url=url)
        scope = f"URL 全历史：{_esc(url)}" if url else "最近一轮"
        parts = [
            "<h1>订阅预览</h1>",
            '<nav><a href="/">条目列表</a> · <a href="/timeline">变更时间线</a> · '
            '<a href="/subscribe">订阅预览</a> · <a href="/bench">基准报告</a></nav>',
            f"<h2>{scope}（与 jobsctl feed 同一匹配函数）</h2>",
        ]
        if not matched:
            parts.append(
                "<p>（无订阅规则或无命中；配置方法见 subscribe.example.yaml）</p>"
            )
        for rule, hits in matched.items():
            parts.append(f"<h3>规则：{_esc(rule)}（{_esc(len(hits))} 条命中）</h3><ul>")
            for ev in hits:
                kind = _KIND_LABELS.get(str(ev.kind), str(ev.kind))
                title = titles.get(ev.url, ev.detail.get("title", ev.url))
                parts.append(
                    f"<li>[{_esc(kind)}] <a href=\"{_esc(ev.url)}\">{_esc(title)}</a>"
                    f" — {_esc(json.dumps(ev.detail, ensure_ascii=False))}</li>"
                )
            parts.append("</ul>")
        parts.append(_page_footer())
        return "\n".join(parts)

    @app.get("/bench", response_class=HTMLResponse)
    def bench() -> str:
        report = views.bench_report()
        verdict = "PASSED" if report["passed"] else "NOT PASSED（诚实扣分项，不隐藏）"
        parts = [
            "<h1>基准报告</h1>",
            '<nav><a href="/">条目列表</a> · <a href="/timeline">变更时间线</a> · '
            '<a href="/subscribe">订阅预览</a> · <a href="/bench">基准报告</a></nav>',
            f"<h2>真值抽取基准（overall {report['overall']['correct']}/"
            f"{report['overall']['total']}）—— {verdict}</h2>",
            "<table><tr><th>字段</th><th>准确率</th><th>对/总</th><th>ambiguous 对</th>"
            "<th>漏标</th><th>臆测</th></tr>",
        ]
        for name, label in report["field_labels"].items():
            s = report["fields"][name]
            parts.append(
                f"<tr><td>{_esc(label)}</td><td>{s['accuracy']:.1%}</td>"
                f"<td>{s['correct']}/{s['total']}</td>"
                f"<td>{s['ambiguous_right']}</td><td>{s['miss_should_verify']}</td>"
                f"<td>{s['hallucinated']}</td></tr>"
            )
        cls = report["classification"]
        parts.append(
            f"</table><p>分类对账：{cls['correct']}/{cls['total']}</p>"
            "<h2>变更检测基准</h2><ul>"
        )
        for case in report["change_cases"]:
            mark = "✅" if case["ok"] else "❌"
            parts.append(f"<li>{mark} {_esc(case['name'])}: {_esc(case['report'])}</li>")
        parts.append("</ul>")
        if report["failures"]:
            parts.append("<h3>失败明细（不隐藏）</h3><ul>")
            for failure in report["failures"]:
                parts.append(f"<li>{_esc(failure)}</li>")
            parts.append("</ul>")
        parts.append(_page_footer())
        return "\n".join(parts)

    return app


def _page_footer() -> str:
    return (
        '<footer><p>仅供参考，报名截止日期等关键信息以招聘单位官方公告原文为准。</p>'
        "<p>数据来自本地快照库（cache/ajm.sqlite3）；面板只读，抓取请用 jobsctl。</p></footer>"
    )


app = None


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """jobsctl web 入口：uvicorn 启动（懒加载，避免 CLI 常规路径导入 FastAPI）。"""
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port, log_level="info")
