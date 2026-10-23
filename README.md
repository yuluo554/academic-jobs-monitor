# academic-jobs-monitor

> 高校学术招聘聚合监控器：多源人事处/招聘平台抓取 · 结构化字段抽取 · 快照与变更检测 · 截止监控推送。
> **本地 Web 面板 + CLI 双形态**（Python，基础功能零 AI 接口依赖）。

> ⚠️ 免责声明：本工具的抓取、抽取与推送结果**仅供参考**，报名截止日期等关键信息**一律以招聘单位官方公告原文为准**，不构成求职建议。

## 这是什么

高校教师招聘与博士招生公告散落在各高校人事处页面与聚合平台上，截止日期往往埋在正文里。本工具把"盯官网"变成可复现的数据管道：

1. **多源抓取适配器** — 首期 5 源：高校人才网、学术桥、北京大学人事部、复旦大学人事处、南京大学人力资源处；单源失败隔离不中断，失败原因码单列。
2. **结构化字段抽取** — 规则优先（正则 + 规则模板），抽取岗位/单位/学科方向/待遇/截止日期；每字段挂命中规则名 + 原文片段证据；规则未命中即标 `pending`，**无 LLM 兜底**。
3. **快照与变更检测** — 持久快照 + 字段级 diff，四类事件：新增岗位 / 截止日变更 / 正文实质变更 / 公告删除（连续 N 轮缺失去抖）。
4. **订阅与推送** — 关键词订阅规则文件化，输出 RSS 与 HTML 摘要；仅 `verified` 字段进入推送路径。
5. **内置基准** — 人工标注真值的抽取准确率基准 + 受控两轮样本的变更检测基准，一条命令可重复运行（指标口径见下文基准一节）。

## 快速开始

**要求**：Python **3.12+**（3.10 已过安全支持窗口，M7 迭代起不再支持）。

发行名是 `ajm`、入口命令是 `jobsctl`——**两者不同名**。当前**未发布到 PyPI**（`ajm`
在 PyPI 上不存在），所以只有下面两条源码安装路径，没有 `pip install ajm`。

```bash
git clone https://github.com/yuluo554/academic-jobs-monitor.git
cd academic-jobs-monitor

# 路径一（开发用，推荐）：editable 安装，改代码即时生效
pip install -e ".[dev]"

# 路径二（当产品用）：构建 wheel 后装进任意环境，不依赖源码目录
python -m pip wheel . -w dist/ --no-deps
pip install dist/ajm-0.2.0-py3-none-any.whl
```

```bash
jobsctl --help
jobsctl sources        # 查看已注册适配器
jobsctl crawl          # 抓取一轮（限频 3s/源，UA 自标识）
jobsctl snapshot       # 抓取一轮 → 抽取 → 快照 diff 事件
jobsctl timeline       # 查询变更时间线
jobsctl bench          # 运行内置基准（真值抽取 + 变更检测，离线）
jobsctl feed           # 订阅匹配 → RSS/HTML 摘要（先复制 subscribe.example.yaml 为 subscribe.yaml）
jobsctl web            # 启动本地面板（M5）
```

> **editable 与 wheel 的差别务必留意**：`pip install -e .` 会把仓库 `src/` 整个塞进
> `sys.path`，于是"wheel 漏打包"这类缺陷在本地完全看不出来。M7 迭代修掉了这个缺陷
> （5 个子系统已收进 `ajm` 命名空间），并新增非 editable 安装门禁
> （`tests/test_packaging.py` + CI `packaging` job）：wheel 内容、装进全新 venv、
> 在中立目录跑子命令三层都断言。

## 状态

M1–M7 全部完成，**v0.2.0 已发布**（[Release v0.2.0](https://github.com/yuluo554/academic-jobs-monitor/releases/tag/v0.2.0)）。

> **v0.1.0-m6 → v0.2.0 的破坏性变更**：`requires-python` 由 `>=3.10` 抬到 **`>=3.12`**。
> Python 3.10/3.11 上**装不上**本版。原因是 PEP 639 元数据（`license` 用 SPDX 表达式 +
> `license-files`）要求 `setuptools>=77`（本仓构建后端是 hatchling，但生态一致口径），
> 而现行生态里 compliance 相关依赖的最新线已集体要求 ≥3.12。若必须留在 3.10/3.11，
> 请继续用 `v0.1.0-m6` 的源码包。
>
> **另一处用户可感知的变化**：五个子系统（`extract` / `bench` / `snapshot` / `subscribe` /
> `webapp`）从 `src/` 顶层收进 `ajm` 命名空间 —— 之前 `pip install` 会把 `bench`、`extract`
> 这类**通用名**投到 `site-packages` 顶层（与别的包撞名），现在顶层只有 `ajm`。
> 从仓库 **clone 用 `pip install -e .` 的人不受影响**；只有 `import bench` 这类按顶层名
> 引用旧布局的脚本需要改成 `from ajm.bench import ...`。

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M1 | 数据源可获取性实测 + 依据查证 | ✅ |
| M2 | 5 源抓取适配器 + 失败隔离 | ✅ |
| M3 | 字段抽取规则族 + 快照字段级 diff | ✅ |
| M4 | 真值基准 + 订阅推送（RSS/HTML） | ✅ |
| M5 | Web 面板 + CLI 双形态 + 技术报告 | ✅ |
| M6 | GitHub Release 发布 | ✅ [v0.1.0-m6](https://github.com/yuluo554/academic-jobs-monitor/releases/tag/v0.1.0-m6) |
| M7 收尾 | 命名空间收敛 + 非 editable 安装门禁 + **v0.2.0 发布** | ✅ [v0.2.0](https://github.com/yuluo554/academic-jobs-monitor/releases/tag/v0.2.0) |

## 本地 Web 面板（双形态之一）

```bash
jobsctl web                 # 默认 http://127.0.0.1:8000（--host/--port 可改）
```

- **只读面板**：条目列表（快照库）/ 变更时间线（`?url=` 出单条全历史）/ 订阅预览 / 基准报告；抓取仍走 `jobsctl snapshot`；
- **双形态同源**：与 CLI 共享同一编排函数组（`src/ajm/webapp/views.py` 单一事实源），三方对账测试断言 CLI stdout = 直调视图函数 = 面板渲染一致；
- 零外链内联单页，断网可演示；`/docs` 关闭；演示截图见
  [docs/screenshots/](docs/screenshots/)（条目列表 / 时间线 / 订阅 / 基准四页），
  推送样例见 [docs/release-samples/](docs/release-samples/)（`sample-feed.html` / `sample-feed.rss`）。

技术设计详见 [docs/技术报告.md](docs/技术报告.md)（适配器失败隔离/规则族与 pending 纪律/字段级 diff/基准口径/合规红线）。

## 基准指标口径

**一条命令**：`jobsctl bench`（离线可复跑；权威定义见 [bench/README.md](bench/README.md)）。

**真值抽取基准**（`src/ajm/bench/fixtures/truth.json`，随包分发；v1 共 27 例：真实公告列表页条目 +
deadline 规则族真实句式样例，人工标注、`annotated_at` 可回溯）：

- 真值非空：verified 值相等记对；ambiguous 且真值 ∈ candidates 记对（单独计数）；
  pending 或值不等记错；
- 真值 null（公告可见信息中不存在该字段）：pending 记对，verified/ambiguous 记错
  （臆测即扣分，K5/K6）；
- 相对期限样例：正确行为是 pending + 证据保留，不计入分母（K6）；
- 非招聘条目只对账分类，不进字段分母（与生产编排一致）。

**变更检测基准**（`src/ajm/bench/fixtures/change_cases/`）：多轮受控构造走
`SnapshotPipeline` 生产路径，期望事件全检出且期望之外零事件（误报）才通过；
含"删除后复现""截止日改期""（更新）后缀非变更"边界。

**可证伪探活**：测试注入缺陷（删一条 deadline 规则）→ 基准必须报未达标。

**当前基准（2026-10-14）**：position 95.5%（『<实验室>主任招聘公告』句式未覆盖，
诚实缺口不隐藏）、organization / discipline / compensation / deadline 100%，
overall 108/109 = 99.1%；分类 5/5；变更样本 11 期望全检出、零误报。

## 合规与隐私

- 遵守各源 robots 与限频（默认 ≥3s 间隔）；抓取 UA 自标识，可被站点识别与联系；
- 仅缓存公开公告元数据（标题/URL/日期/抽取字段），不存整页镜像；
- 不采集个人信息：公告中联系人姓名/电话不入结构化字段库、不出现在推送摘要；
- 不抓取登录墙内数据（清华、浙大等首期不纳入，见 [data/README.md](data/README.md) 实测记录）。

## License

MIT — 见 [LICENSE](LICENSE)。
