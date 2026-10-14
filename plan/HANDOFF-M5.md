# HANDOFF-M5 — 交棒：Web 面板 + 双形态对账 + 技术报告

> M4（真值基准 + 订阅推送）收尾落盘。下一对话启动提示词：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M5.md" 继续完成任务`。

## 一、M4 产出与证据

- **真值库**（`bench/fixtures/truth.json`，v1 27 例）：
  - 真实列表页条目（gaoxiaojob 6 / pku 5 / fudan 5 / nju 5，含 `extra` 结构化输入与 M1 合成 hash 文件名口径）+ deadline 规则族真实句式样例 5 条（acabridge WAF 阻断合规不绕过，占位 URL + `body_text` 真实句式并显式标注）+ 分类样例（非招聘 ×4、不可判定 ×1）；
  - 每条挂 `url` + `annotated_at` + 字段级 `evidence` 片段；无个人信息。
- **bench 引擎**（`src/bench/`）：`truth.py`（逐字段准确率，判定口径见 bench/README）+ `change_cases.py`（多轮受控构造走 `SnapshotPipeline` 生产路径）；
  - `jobsctl bench` 一条命令离线可复跑；**当前 overall 108/109 = 99.1%**（position 95.5%、其余 4 字段 100%、分类 5/5）；
  - **唯一扣分项诚实保留**：pku『新闻出版智能媒体技术重点实验室主任招聘公告』的 position（"主任"）句式未覆盖 → bench 退出码 1（NOT PASSED 不隐藏，plan/06 登记；修复句式后基准自然转绿）。
- **变更基准**（`bench/fixtures/change_cases/cases.json`，3 用例 11 期望）：四类事件 + 截止日改期 + 删除后复现 + （更新）后缀非变更，全检出零误报；runner 有期望"消费"语义（同一实际事件只命中一个期望，防重复计数）。
- **可证伪探活**：`test_truth_bench_is_falsifiable_injected_defect_must_fail` 运行时删 `deadline_cn_ymd` 规则 → bench 必报未达标。
- **订阅与推送**（`src/subscribe/`，题面任务 4）：
  - `matcher.py`：规则文件化（`subscribe.example.yaml` 入库；真实 `subscribe.yaml` git-ignored）；匹配域 = 标题 + URL + detail（AND 全命中、大小写不敏感）；sources/kinds 可选过滤；
  - `feeds.py`：RSS 2.0（标准库手写 XML、`xml.sax.saxutils.escape` 转义）+ HTML 摘要（内联样式 0 外链）；GUID = sha256(kind|url|round|detected_at) 同事件恒定；
  - `jobsctl feed [--url]`：最近一轮（或单 URL 全历史）事件 × 订阅规则 → `cache/feeds/feed-roundN.{xml,html}`；端到端实测 3 条命中落盘。
- **抽取引擎 M4 修正**（真值 dry-run 实证驱动，M3 测试无回归）：position/org 锚只扫标题；org 贪心最长复合机构名 + 年份前缀剥离；position 剥"招聘<N>名"人数前缀。**M4 起为既定口径**（plan/06）。
- **验证**：pytest **54 passed**（43 + 11 M4）+ ruff 全绿；真实 round3（引擎修正后首轮）9 条 content_changed 事件为锚修正的合法回归差异。

## 二、M5 待办（下一对话从这里开始）

1. **FastAPI Web 面板**（`src/webapp/`，题面交付"本地 Web 面板 + CLI 双形态"）：
   - 页面：条目列表（快照库）、URL 时间线、订阅预览（复用 `subscribe.match_events`）、基准报告（复用 `bench.run_truth/run_change_cases`）；
   - 零依赖内联单页（模板内联、0 外链，断网可演示）；`/docs` 关闭；
   - `jobsctl web` 启动（uvicorn，端口默认 127.0.0.1:8000）。
2. **双形态对账**：CLI 与面板共享编排函数组（建议提为 `src/ajm/orchestration.py` 或直接共用 SnapshotPipeline/bench 入口）；三方对账测试：CLI stdout = 直调编排函数 = 面板渲染（同一数据源断言一致）。
3. **技术报告**（`docs/技术报告.md`）：适配器设计（失败隔离/原因码）、规则族与 pending/ambiguous 纪律、diff 判定（字段级 + 去抖）、基准口径与当前指标、合规红线。语言口径 A（中文，plan/06 待定表 D4）。
4. **README 终稿**：演示截图（面板 + feed）、指标口径链接 bench/README、免责声明已有。
5. **M5 lint 测试**：webapp 路由离线测试（TestClient）；对账测试。
6. 写 `plan/HANDOFF-M6.md`（M6 = 脱敏发布：四步脱敏 + 干净环境验证 + tag/GitHub Release + CI 首跑对账）。

## 三、既定口径清单（K1–K10 + M3/M4 增补，全部有效）

K1 `_StrEnum` 3.10 兼容；K2 CI PYTHONUTF8 + fetch-depth:0；K3 CLI UTF-8 守卫；K4 限频 3.0s + 去抖 N=3；K5 失败隔离 + 禁启发式兜底（position/org 锚只扫标题即 M4 口径）；K6 仅 verified 出镜、pending 不臆测（feeds 层收口已测试断言）；K7 测试全离线走 fixtures；K8 假名扫描自动化（**truth.json 显式豁免**——真实 URL 标注对象，发布脱敏在 M6）；K9 品牌隔离；K10 raw HTML 只落 cache/。

**M4 新增口径**（详见 plan/06 M4 决策行）：bench 判定口径（null→pending 对/verified→错；ambiguous ∈ candidates 对；非招聘不进字段分母；`deadline_pending_expected` 不计分母）；订阅匹配域与 GUID 恒定；bench 退出码语义（有扣分即 1）。

## 四、M4 实现要点备忘（M5 会用到）

- `subscribe.match_events(config, events, titles)` 纯函数可直接被 webapp 复用；`titles` 从 `storage` snapshots 表查（`_cmd_feed` 有现成写法）。
- `bench.run_truth()` / `run_change_cases()` 返回结构化报告对象（`TruthReport.field_scores()` / `ChangeReport.ok`），webapp 基准页直接渲染；勿在 webapp 里重复实现判定。
- `FeedEntry(event, title)` + `render_rss/render_html` 是渲染契约；webapp 订阅预览可只复用 `match_events` 不渲染文件。
- CLI `_cmd_bench` 的打印即"CLI 形态"的基准输出；三方对账时以此为准（`jobsctl bench` 退出码 1 是当前诚实扣分项，对账测试勿断言 exit==0）。
- `Storage._conn` 暴露 sqlite3 连接（`_cmd_feed` 直接用了）；M5 若嫌脏可在 storage 加 `all_titles()` 门面，但**勿改 schema**。
- 真值库滚动补充：`bench/fixtures/truth.json` 追加 cases（真实 URL + annotated_at + evidence）；标注口径变化须同步 bench/README 与 plan/06。
- 唯一已知抽取缺口：『<实验室>主任招聘公告』position 句式（bench 扣分项）。M5 不必修（修了 bench 会转绿，属正向变更可顺手做，但要同步 bench/README 当前基准表）。

## 五、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 当前 54 项，全离线
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe bench             # 真值 99.1% + 变更样本全检出（退出码 1=诚实扣分项在）
.venv/Scripts/jobsctl.exe snapshot          # 真实一轮（限频 3s，全源约 20s）
.venv/Scripts/jobsctl.exe feed              # 需先 cp subscribe.example.yaml subscribe.yaml
.venv/Scripts/jobsctl.exe timeline          # 最近一轮事件
```

## 六、M4 DoD checklist（已全部完成，plan/05 已同步勾选）

| DoD 项 | 证据 |
|---|---|
| 真值库 + `jobsctl bench` 逐字段准确率 + README 口径 | `bench/fixtures/truth.json` 27 例；`src/bench/truth.py`；overall 99.1%；README + bench/README |
| 变更检测基准 + 可证伪探活 | `bench/fixtures/change_cases/cases.json` 3 用例 11 期望零误报；探活测试通过 |
| 订阅 → RSS + HTML，命中恒定，仅 verified | `src/subscribe/` + `jobsctl feed` 端到端 3 条命中；一致性/K6 测试断言 |
| HANDOFF-M5 落盘 | 本文件 |

## 七、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M5.md" 继续完成任务
```
