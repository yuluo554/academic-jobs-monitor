# HANDOFF-M6 — 交棒：脱敏发布（GitHub 公开仓 + Release + CI 首跑对账）

> M5（Web 面板 + 双形态对账 + 技术报告）收尾落盘。下一对话启动提示词：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M6.md" 继续完成任务`。

## 一、M5 产出与证据

- **FastAPI 面板**（`src/webapp/`，题面交付"本地 Web 面板 + CLI 双形态"）：
  - `views.py` 共享视图层（**双形态单一事实源**）：`list_snapshots / timeline_events / feed_preview / bench_report`——CLI 与面板路由都从这里取数，任何一侧不重复实现查询/判定；
  - `app.py` 应用工厂：`/`（条目列表 5 字段出镜）、`/timeline`（缺省最近一轮、`?url=` 单条全历史）、`/subscribe`（复用 `subscribe.match_events`）、`/bench`（直接渲染 `bench.run_truth/run_change_cases` 报告对象）；
  - 纪律落地：零外链内联单页（断网可演示）、`/docs`+`/redoc` 404、**只读不改库**（测试字节级断言 db 文件不变）、空库优雅渲染；
  - `jobsctl web [--host --port]` uvicorn 启动（默认 127.0.0.1:8000），真实启动冒烟 4 页 200 + docs 404。
- **三方对账测试**（`tests/test_m5_webapp.py`，13 项）：同一 tmp 快照库上 CLI stdout = 直调视图函数 = 面板渲染（时间线事件集合 / 订阅命中数 / 基准数字三处一致）；bench 当前扣分项 exit==1 在对账中如实保留（不断言 0）。
- **Storage 小改**：新增 `all_titles()` 门面（feed/订阅预览共用；schema 未动）。CLI `_cmd_feed` 已改用它。
- **骨架门禁测试更新**：`jobsctl web` 从"占位返回 2"改为 `--help` 门禁（真实起服务不进离线测试，K7）。
- **技术报告**：`docs/技术报告.md`（中文，D4 口径 A）——适配器失败隔离/规则族与 pending 纪律/字段级 diff/基准口径/双形态对账/合规红线。
- **README**：M5 状态 ✅ + "本地 Web 面板"一节（用法/双形态同源/零外链说明）。
- **验证**：pytest **67 passed**（54 + 13 M5）+ ruff 全绿；plan/05 M5 DoD 全勾 + plan/06 M5 决策行登记。

## 二、M5 实现要点备忘（M6 会用到）

- 面板页是**内联片段式 HTML**（非完整 `<html>` 文档），测试断言"无 `<script src>/<link>/<img>` 外链"；M6 Release 如需截图，浏览器全页截图即可。
- `views.bench_report()` 返回结构化 dict（`passed` 字段 = 无 truth failures 且变更全 ok）；当前恒为 False（诚实扣分项），修复『<实验室>主任』position 句式后自动转 True——届时须同步 bench/README 当前基准表 + plan/06 + 本文件"已知缺口"行。
- 对账测试里 bench 数字断言 `108/109` 是**锚定断言**：truth.json 变更（滚动补充样例）会合法改变它，需同步更新测试与 bench/README。
- `webapp.run()` 懒加载 uvicorn（CLI 常规路径不导入 FastAPI）；`create_app(cfg)` 支持注入 tmp 配置（测试用）。

## 三、M6 待办（下一对话从这里开始）

1. **脱敏四步**（plan/RELEASE-M6.md 留档命令与结论）：
   ① 历史全量扫描：假名白名单（K8）扫全部入仓文本（truth.json 豁免仅在开发期有效，**发布前必须重新决策其脱敏口径**——真实 URL 是标注对象本体，脱敏会破坏"可回溯"属性，需拍板：保留真名 or 打码 URL 保留句式）；② git 历史提交元数据（作者/邮箱）检查——当前本地仓历史含 `yuluo554@example.com` 占位即可，若有真实邮箱须 filter-repo；③ raw/cache/subscribe.yaml 确认全部 git-ignored 且不在历史 blob 中（`git log --all --full -- cache subscribe.yaml` 等）；④ 假名扫描测试在 CI 维度再跑一遍。
2. **干净环境验证**：新目录 clone（本地 path clone 即可）+ 全新 venv `pip install -e .[dev]` → 照 README 逐条跑通（`jobsctl sources/extract --fixture/bench/web`；`snapshot` 需网络可选）+ `pytest` 全绿；收集数对账（同一 extras 口径）。
3. **发布**：git tag（**须用户确认后**打）→ GitHub 公开仓 `yuluo554/academic-jobs-monitor` push → Release 附演示截图（面板 + feed HTML）+ 样例 RSS（ASCII 附件名）。
4. **CI 首跑对账**：push 数 = run 数按提交逐条配对（Actions 页核对）；首跑若挂（Windows-only 编码问题最可能）修复后补记；据实回填"CI 从未运行"尾注（plan/06 诚实口径尾注）。
5. **发布后复核**：全新 clone 复跑 pytest + bench（退出码 1 = 扣分项仍在，如实记录）。
6. 写 `plan/HANDOFF-M7.md`（或 HANDOFF-FINAL）：收尾清点（题目交付对标逐行核对 plan/01 ↔ plan/06）+ 演示脚本。

## 四、既定口径清单（K1–K10 + M3/M4/M5 增补，全部有效）

K1 `_StrEnum` 3.10 兼容；K2 CI PYTHONUTF8 + fetch-depth:0；K3 CLI UTF-8 守卫；K4 限频 3.0s + 去抖 N=3；K5 失败隔离 + 禁启发式兜底（position/org 锚只扫标题 = M4 口径）；K6 仅 verified 出镜、pending 不臆测（feeds 层收口 + 面板 field_display 同口径）；K7 测试全离线走 fixtures（web 服务不进单测，用 TestClient）；K8 假名扫描自动化（truth.json 开发期豁免，**M6 发布前重议**）；K9 品牌隔离；K10 raw HTML 只落 cache/。

**M5 新增口径**（详见 plan/06 M5 决策行）：双形态单一事实源 = `webapp/views.py`；面板只读 + 零外链 + `/docs` 关闭；对账测试不断言 bench exit==0（诚实扣分项在）。

## 五、已知缺口（诚实保留，不隐藏）

- 唯一 bench 扣分项：『<实验室>主任招聘公告』position 句式未覆盖（overall 99.1%，bench exit 1）。M5 未修（口径见 HANDOFF-M5 四节：修了属正向变更，需同步 bench/README）。
- 演示截图未生成（README 已留 docs/ 指向；M6 Release 必附）。
- CI 从未运行（plan/06 诚实口径尾注；M6 首跑后据实补记）。
- D1（建仓时机）/ D2（邮箱）/ D5（acabridge 去留）等待拍板项见 plan/06 第三节。

## 六、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 当前 67 项，全离线
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe bench             # 99.1% + 变更全检出（exit 1=扣分项在）
.venv/Scripts/jobsctl.exe web               # 面板 http://127.0.0.1:8000（Ctrl+C 退出）
.venv/Scripts/jobsctl.exe web --port 8765   # 换端口
.venv/Scripts/jobsctl.exe timeline          # 最近一轮事件
.venv/Scripts/jobsctl.exe feed              # 需先 cp subscribe.example.yaml subscribe.yaml
```

## 七、M5 DoD checklist（已全部完成，plan/05 已同步勾选）

| DoD 项 | 证据 |
|---|---|
| FastAPI 面板四页 + 零外链 + `/docs` 关闭 | `src/webapp/app.py`；TestClient 13 项 + 真实启动冒烟 200/404 |
| 共享编排函数组 + 三方对账测试 | `src/webapp/views.py`；`tests/test_m5_webapp.py` CLI=直调=面板三处一致 |
| 技术报告 + README 终稿 | `docs/技术报告.md`（中文）；README M5 ✅ + 面板一节 |
| HANDOFF-M6 落盘 | 本文件 |

## 八、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M6.md" 继续完成任务
```
