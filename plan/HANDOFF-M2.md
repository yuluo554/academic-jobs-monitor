# HANDOFF-M2 — 交棒：5 源适配器实现

> M1（数据源实测复核 + 回放 fixtures）收尾落盘。下一对话启动提示词：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M2.md" 继续完成任务`。

## 一、M1 产出与证据

- **逐源直连复核完成**（2026-10-14 当轮，原始页留存 `cache/raw/verify/`，git-ignored）：
  - gaoxiaojob：入口变更（原 `/zhaopin/index.html` 404 → 用 `/column/<id>.html`）；**列表页无发布日期**；
  - acabridge：302 换主域（acabridge.net）+ 阿里云 WAF 滑块**稳定拦截**（3+1 轮复测）→ 降级"注册但稳定失败隔离"；
  - pku / fudan / nju：结构无变化。
- **fixtures 入仓**：`src/ajm/sources/fixtures/<source_id>/`（gaoxiaojob list.html；acabridge waf_interstitial.html；pku/fudan/nju list.html），逐源 `notes.md` 记容器选择器/字段位置/日期格式/边界样例/脱敏说明。全部单位名为假名白名单（K8），`tests/test_fixtures.py` 内置真实校名黑名单自查。
- **RawItem 勘误结论**：字段（title/url/published_on/source + raw_html_path）对照真实页面**无需改动**；gaoxiaojob 无日期 = `published_on: date | None` 的既有设计场景（K6 不臆测）。已登记 plan/06。
- **文档同步**：data/README.md 五源表已更新为 M1 复核口径；plan/06 新增 M1 决策行 + 待拍板项 **D5（acabridge 去留，推荐 A 维持 5 源）**。
- **验证**：pytest **13 passed**（7 骨架 + 6 fixtures）；ruff 全绿。仍为本地等价校验，未接远端（诚实口径，plan/06 尾注）。
- **git**：M1 提交见 git log 最新一条。无远端（D1 仍缓议）。

## 二、M2 待办（下一对话从这里开始）

1. **5 源适配器实现**（`src/ajm/sources/` 逐源独立模块，实现 `SourceAdapter` 协议，K5 契约）：
   - gaoxiaojob：入口 `/column/11.html`，解析 `.job-board li > a[href^=/job/detail/]`，`published_on=None`；
   - pku：`li > a[title*="发布日期："]`，title 属性拆标题/日期，`urljoin` 相对路径；
   - fudan：`a.column-news-item`，`column-news-title`/`column-news-date`；
   - nju：`li.news`，标题取 `a` 的 `title` 属性（文本是截断版），日期 `span.news_meta`，无日期条目整条跳过；
   - acabridge：识别 WAF 拦截页（`aliyun_waf_aa` 特征）→ `FetchOutcome.failure`（原因码 M2 拍板：建议 `http_error` + detail，或新增 `WAF_BLOCKED` 枚举——若新增属口径变更须同步 plan/06 + 测试）。
2. **registry 注册**：`jobsctl sources` 从空表变为 5 适配器；`crawl --source ""` 汇总表含 5 源成败计数。
3. **fetch.py 接线**：适配器统一走 `Fetcher`（限频 3s K4 不动）；解析用标准库（html.parser 或正则按 notes.md 定位规则，禁止启发式兜底 K5）。
4. **fixture 回放测试**：每源至少 1 个"fixture → RawItem 列表"断言（含边界样例：nju 无日期条目跳过、pku 外链处置、gaoxiaojob 4 条目无日期）；acabridge 断言失败隔离。
5. **真实抓取 1 轮演示**（4 源可解析 + acabridge 稳定失败），证据写本文件 M2 节或 plan/05。
6. 写 `plan/HANDOFF-M3.md`（M3 = 字段抽取 + 快照/变更检测）。

## 三、既定口径清单（沿用 HANDOFF-M1 K1–K10，全部有效）

K1 `_StrEnum` 3.10 兼容；K2 CI PYTHONUTF8 + fetch-depth:0；K3 CLI/脚本 UTF-8 守卫；K4 限频 3.0s + 去抖 N=3（改动=口径变更）；K5 失败隔离 + 禁启发式兜底；K6 仅 verified 进推送、pending 不臆测；K7 测试全离线走 fixtures；K8 假名白名单；K9 品牌隔离；K10 raw HTML 只落 cache/。

## 四、本机环境坑（沿用 HANDOFF-M1 第四节，全部实测有效）

- venv 3.12（`.venv/Scripts/python.exe` 正斜杠可跑）；3.8 跑不了本项目。
- pip 代理污染：`NO_PROXY="*" no_proxy="*"` 前缀。
- 请求侧注意：直连复核用 urllib + `Accept-Encoding: gzip` 手工解压；acabridge 换任何浏览器头都过不了 WAF（勿浪费时间重试，合规红线也不允许绕）。

## 五、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 当前 13 项，全离线
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe sources           # M2 后应为 5 适配器
.venv/Scripts/jobsctl.exe crawl --source pku  # 单源真实抓取（走 Fetcher 限频）
```

## 六、M1 DoD checklist

| 项 | 证据 |
|---|---|
| 5 源直连复核 + 当轮证据 | cache/raw/verify/*.html（5 源 8 份）；data/README.md M1 复核行 |
| fixtures 入仓（脱敏） | src/ajm/sources/fixtures/*/list.html + notes.md（5 目录 10 文件）；test_fixtures 黑名单自查通过 |
| 结构差异逐源标注 | gaoxiaojob 入口/无日期、acabridge WAF——notes.md 与 data/README.md 双登记 |
| RawItem 勘误 | 结论"无需改动"，plan/06 M1 决策行 |
| 测试绿 | pytest 13 passed；ruff All checks passed（本地等价校验口径） |
| HANDOFF-M2 | 本文件 |

## 七、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M2.md" 继续完成任务
```
