# HANDOFF-M3 — 交棒：字段抽取 + 快照/变更检测（招牌模式）

> M2（5 源适配器）收尾落盘。下一对话启动提示词：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M3.md" 继续完成任务`。

## 一、M2 产出与证据（详细见 HANDOFF-M2 第八/九节）

- **5 源适配器全部实现并注册**：`src/ajm/sources/{gaoxiaojob,pku,fudan,nju,acabridge}.py`（独立模块，实现 `SourceAdapter` 协议，K5）；公共解析层 `sources/_htmlutil.py`（标准库 html.parser → 轻量 DOM，无站点假设）。
- **口径拍板**（plan/06 M2 决策行）：新增 `FailureCode.WAF_BLOCKED`；pku 外链整条跳过；nju 无日期条目跳过；gaoxiaojob `published_on=None`。
- **真实抓取演示**（2026-10-14，`jobsctl crawl`）：4/5 ok（fudan 14 / gaoxiaojob 60 / nju 24 / pku 18 items），acabridge `waf_blocked` 失败隔离，exit=0。
- **验证**：pytest **24 passed**（13 骨架/fixtures + 11 适配器回放）；ruff 全绿；本地等价校验口径不变（D1 缓议）。
- **git**：M2 提交见 git log 最新一条。无远端。

## 二、M3 待办（下一对话从这里开始）

1. **字段抽取**（`src/extract/`，题面任务 2）：
   - 截止日期多格式正则族（每条规则命名登记，如 `deadline_iso`、`deadline_cn_ymd`、`deadline_chinese_until`）；
   - 岗位/单位/学科方向/待遇规则模板（gaoxiaojob 列表页的 requirement/region 结构化字段可直接映射为 verified 证据）；
   - 纪律：未命中 → `status=pending` 不臆测（K6）；多候选全保留 → `ambiguous`；每字段带 `Evidence(rule_name, snippet)`；
   - 输入是 `RawItem`（M2 产出）→ 输出 `JobPosting`（models.py 已定）。
2. **快照与变更检测**（`src/snapshot/`，题面任务 3）：
   - 持久快照（storage.py SQLite 已有骨架，核对字段是否满足 M3 需求）；
   - 字段级 diff 四类事件（`EventKind`：NEW_POSTING / DEADLINE_CHANGED / CONTENT_CHANGED / ANNOUNCEMENT_REMOVED）；
   - 删除去抖 N=3（`REMOVAL_DEBOUNCE_ROUNDS`，K4 口径）；变更时间线可查询；
   - 注意 pku notes 边界：title 含"（更新）"后缀的条目，title 不宜直接入 content_hash（M1 已预警）。
3. **受控两轮样本验证**：四类事件全检出且无误报（首轮真值库对 fixtures 初测；gaoxiaojob 无日期 → deadline 恒 pending，正是门控演示场景）。
4. **文档同步**：data/README.md 如需补抽取口径；plan/05 M3 DoD 逐项勾选；plan/06 决策行（如新增规则命名规范等口径）。
5. 写 `plan/HANDOFF-M4.md`（M4 = 真值基准 + 订阅推送）。

## 三、既定口径清单（沿用 K1–K10，全部有效）

K1 `_StrEnum` 3.10 兼容；K2 CI PYTHONUTF8 + fetch-depth:0；K3 CLI/脚本 UTF-8 守卫；K4 限频 3.0s + 去抖 N=3（改动=口径变更）；K5 失败隔离 + 禁启发式兜底（抽取规则同理：未命中 pending，不猜）；K6 仅 verified 进推送、pending 不臆测；K7 测试全离线走 fixtures；K8 假名白名单；K9 品牌隔离；K10 raw HTML 只落 cache/。

## 四、M2 实现要点备忘（M3 会用到）

- `_htmlutil.parse_html` 可复用于详情页解析（M3 若做二级页抓取）；`Node.find/find_all/text()` 用法见各适配器。
- `FetchOutcome.items` 即 RawItem 流；`fetched_at` 已带时区（`_utcnow`），快照 round 编号需在 storage 层新增。
- 详情页抓取属扩展项（gaoxiaojob 日期在详情页）：如做，须走 `Fetcher`（K4 限频）且逐源新增 fixture + 回放测试；不做则 gaoxiaojob deadline 恒 pending（合规口径可接受）。
- 真实页 gaoxiaojob 列表页体积 ~480KB（60 条目），解析性能无虞；首页 1.17MB 不碰（M1 口径）。
- pku 真实页还会出现其他非招聘 li>a（有"发布日期："的都收进 RawItem），M3 抽取层负责招聘/非招聘分类（nju 同理），属题面任务 2 职责。

## 五、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 当前 24 项，全离线
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe sources           # 5 适配器
.venv/Scripts/jobsctl.exe crawl             # 真实抓取一轮（限频 3s，约 20s）
```

## 六、M2 DoD checklist（已全部完成）

见 HANDOFF-M2 第九节表格。

## 七、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M3.md" 继续完成任务
```
