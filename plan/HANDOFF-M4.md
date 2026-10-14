# HANDOFF-M4 — 交棒：真值基准 + 订阅推送

> M3（字段抽取 + 快照变更检测）收尾落盘。下一对话启动提示词：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M4.md" 继续完成任务`。

## 一、M3 产出与证据

- **字段抽取**（题面任务 2，`src/extract/`）：
  - `rules.py`：命名 deadline 规则族 4 条（`deadline_iso` / `deadline_cn_ymd` / `deadline_chinese_until` / `deadline_relative_from_now`，试跑顺序即登记顺序）+ 招聘/非招聘关键词模板 + 岗位/单位/学科/待遇标题锚正则；
  - `engine.py`：`extract_posting(RawItem, body_text) → JobPosting`（未命中 pending、多候选全保留 ambiguous、每 verified 字段带 `Evidence(rule_name, snippet)`）；`is_recruitment() → True/False/None`（None=不可判定，照常入库）；
  - 相对期限恒 pending（起点歧义，K6 不臆测）；非法日期（2月30日）跳过不猜。
- **快照与变更检测**（题面任务 3，`src/snapshot/differ.py`）：
  - `SnapshotPipeline`：`ingest(逐源)` → `close_round(seen_urls 并集兜底登记缺失 + 去抖判定)`；
  - 四类事件全实现且**持久化**到 SQLite events 表（`jobsctl timeline [--url]` 可查询）；
  - 删除去抖 N=3（`removed_since` 列）；缺失后复现 → `missed_then_reappeared` 事件；哈希变但字段无 diff → `hash_changed_no_field_diff` 事件（事件不丢）；
  - `Storage(":memory:")` 现已支持（测试用）。
- **CLI**：`jobsctl extract --fixture <源>`（回放演示字段+证据链）、`jobsctl snapshot [--source]`（真实一轮全链路）、`jobsctl timeline [--url]`（时间线查询）。`feed/bench/web` 仍返回 2（M4/M5）。
- **验证**：pytest **43 passed**（13 骨架/fixtures + 11 适配器 + 19 M3）+ ruff 全绿；**真实两轮实测**：round1 104 new_posting、round2 **0 事件零误报**（acabridge waf_blocked 照常隔离）。
- **受控样本**（`tests/test_m3_extract_snapshot.py::_TwoRoundWorld` 四轮场景）：NEW_POSTING ×4、DEADLINE_CHANGED（单元用例，字段级 `2026-12-01 -> 2026-11-15`）、ANNOUNCEMENT_REMOVED（去抖第 2/3 轮不报、第 4 轮成立 `consecutive_missing_rounds=3`）、CONTENT_CHANGED（missed_then_reappeared + hash_changed_no_field_diff）；无误报断言全过。
- **git**：M3 提交见 git log 最新一条。无远端（D1 仍待拍板）。

## 二、M4 待办（下一对话从这里开始）

1. **抽取真值库 + bench**（plan/04 资产清单）：
   - `bench/fixtures/truth.json`：真实公告 URL + 人工标注 5 字段真值（首版 5 源 × 5–10 条滚动补；每条挂 `url` + `annotated_at` + 字段级 evidence 片段；个人信息打码）；
   - `src/bench/`：`jobsctl bench` 一条命令出逐字段准确率（verified 判定口径：值相等 / ambiguous 处理口径要先写清）；指标口径写进 README；
   - 基准可证伪探活：注入缺陷（如删一条规则）必须报未达标。
2. **变更检测基准**：`bench/fixtures/change_cases/`（同一页面两轮受控构造；含"删除后复现""截止日改期"边界——M3 的 `_TwoRoundWorld` 场景可直接搬进 bench 编排）。
3. **订阅与推送**（题面任务 4，`src/subscribe/`，M4 第二半）：
   - 关键词订阅规则文件化（示例 `subscribe.example.yaml` 入库，真实订阅 git-ignored）；
   - RSS 2.0（标准库手写 XML）+ HTML 摘要（`jobsctl feed`）；
   - 纪律：同一事件同规则重复运行命中恒定；**仅 verified 字段出镜**（K6 门控在 feeds 层收口）；推送条目带来源 URL + 事件类型。
4. **M4 lint 测试**：扫描 fixtures/真值库无真实院校名（K8 自动化，M1 是人工口径）。
5. **文档同步**：README 指标口径；plan/05 M4 DoD 逐项勾选；plan/06 决策行（bench 判定口径如 ambiguous 算对/算错）。
6. 写 `plan/HANDOFF-M5.md`（M5 = Web 面板 + 双形态对账 + 技术报告）。

## 三、既定口径清单（沿用 K1–K10，全部有效）

K1 `_StrEnum` 3.10 兼容；K2 CI PYTHONUTF8 + fetch-depth:0；K3 CLI/脚本 UTF-8 守卫；K4 限频 3.0s + 去抖 N=3（改动=口径变更）；K5 失败隔离 + 禁启发式兜底（抽取规则同理：未命中 pending，不猜）；K6 仅 verified 进推送、pending 不臆测；K7 测试全离线走 fixtures；K8 假名白名单；K9 品牌隔离；K10 raw HTML 只落 cache/。

**M3 新增口径**（详见 plan/06 M3 决策行）：规则命名 `deadline_<格式语义>`；相对期限恒 pending；分类排除词优先；`RawItem.extra` 结构化直映射（`structured_*` 证据）；缺失登记在 `close_round(seen_urls)` 兜底（勿回退到逐源 ingest 内）；`strip_update_suffix` 剥"（更新）"后缀再入 hash。

## 四、M3 实现要点备忘（M4 会用到）

- 顶层包 `src/extract`、`src/snapshot` 与 `ajm` 平级（plan/03 §四映射口径）；`snapshot/differ.py` import `extract.engine` —— 两包是硬依赖对，bench 搬运场景时同样双 import。
- `JobPosting.to_json()/from_json()` 是快照持久化契约（含 `content_hash` 与字段证据）；bench 对账可直接复用。
- `ExtractedField.ambiguous` 时 `value=None`、`candidates` 全保留——bench 判定口径必须处理此态（建议：真值 ∈ candidates 记对，否则记错并单独统计 ambiguous 率）。
- 事件 detail 约定：`{"deadline": "旧 -> 新"}` / `{"note": "missed_then_reappeared", "missing_since_round": "N"}` / `{"note": "hash_changed_no_field_diff"}`；订阅匹配按 kind + url + detail 过滤。
- 真实页 deadline 命中依赖详情页正文（pku/fudan/nju 标题无日期）——bench 真值标注时对"标题可判"的样例优先；gaoxiaojob 若做详情页二级抓取（扩展项）须走 `Fetcher`（K4 限频）+ 新 fixture + 回放测试。
- CLI `_cmd_snapshot` 是真实全链路编排参考（begin_round → fetch_all → 逐源 ingest → close_round(seen_urls)），bench/feeds 编排同构。

## 五、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 当前 43 项，全离线
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe sources           # 5 适配器
.venv/Scripts/jobsctl.exe extract --fixture gaoxiaojob   # 抽取回放演示（字段+证据链）
.venv/Scripts/jobsctl.exe snapshot          # 真实一轮：抓取→抽取→快照→diff 事件（限频 3s，约 20s）
.venv/Scripts/jobsctl.exe timeline          # 最近一轮事件时间线（--url 查单条）
```

## 六、M3 DoD checklist（已全部完成，plan/05 已同步勾选）

| DoD 项 | 证据 |
|---|---|
| deadline 多格式正则族（命名登记）+ 字段模板；pending/ambiguous 纪律 | `src/extract/rules.py` 4 条命名规则；pytest 19 项 M3 用例（含 ambiguous 全保留、非法日期不猜、相对期限 pending） |
| 持久快照 + 字段级 diff 四类事件 + 去抖 N=3；时间线可查询 | `src/snapshot/differ.py` + `storage.py`（removed_since/append_event/events_for_url）；`jobsctl timeline` |
| 受控两轮样本四类事件全检出且无误报 | `_TwoRoundWorld` 四轮场景（离线）+ 真实两轮 round2 = 0 事件零误报 |
| HANDOFF-M4 落盘 | 本文件 |

## 七、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M4.md" 继续完成任务
```
