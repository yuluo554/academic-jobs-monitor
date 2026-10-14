# HANDOFF-M1 — 交棒：数据源实测复核 + 适配器回放 fixtures

> M0（计划与骨架）收尾落盘。下一对话用启动提示词续接：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M1.md" 继续完成任务`（绝对路径只在会话启动命令里，库内一律相对路径）。

## 一、当前进度与证据

- **M0 DoD 已达成**（详见 [05-里程碑.md](05-里程碑.md) M0 节）：
  - plan/ 体系 00–06 齐全；data/README.md 实测记录已固化（2026-10-14，8 源三态）。
  - 可安装骨架：`pip install -e .[dev]`（Python 3.12.10 venv）成功；`jobsctl --version/sources/extract/crawl` 冒烟通过。
  - 核心模块已实现：`src/ajm/config.py`（枚举：SourceId 5 源、FieldStatus、EventKind 四类、FailureCode、FAKE_ORG_WHITELIST；限频 3s；删除去抖 N=3）、`models.py`（RawItem/Evidence/ExtractedField/JobPosting/Snapshot/ChangeEvent + `content_hash`/`normalize_text`）、`storage.py`（SQLite 三表 + 轮次 + 时间线查询）、`fetch.py`（UA 自标识/限频/超时/FetchResult 原因码）、`sources/base.py`（SourceAdapter 协议 + FetchOutcome 契约）、`sources/registry.py`（逐源异常兜底隔离）、`cli.py`（8 子命令，crawl/sources 可用，其余占位返回 2）。
  - 证据：pytest **7 passed**（tests/test_skeleton.py：哈希确定性/status 门控/失败隔离/快照时间线/CLI）；ruff **全绿**；cp1252 管道下 CLI 中文输出实测不炸（`_ensure_utf8_stdio` 生效）。
- **git**：本地 main；提交 `4307ef8`（题定稿）→ `304caaf`（骨架首版）→ M0 纪律修复提交（见 git log 最新）。**无远端**（D1 决策缓议中）。

## 二、M1 待办（下一对话从这里开始）

1. **逐源直连复核**（5 源）：gaoxiaojob.com / zpjob.acabridge.cn / hr.pku.edu.cn / hr.fudan.edu.cn（/15364/list.htm）/ hr.nju.edu.cn——data/README.md 的实测是 2026-10-14 的，M1 要留当轮新证据；结构有变逐源标注差异并更新 data/README.md。
2. **每源产 1 份脱敏回放 fixture** 入仓（建议 `src/ajm/sources/fixtures/<source_id>/list.html` + `notes.md` 结构笔记：列表容器选择器、条目字段位置、日期格式、边界样例如置顶/分页参数）。
3. **原始条目模型勘误**：用真实页面对照 `RawItem` 字段（title/url/published_on/source），有出入则三处同步——models.py + 决策记录（plan/06）+ fixtures。
4. 写 `plan/HANDOFF-M2.md` 收尾（M2 = 5 源适配器实现）。

## 三、既定口径清单（动了会打挂测试/基准，先对照再动手）

- **K1** 枚举基类 `_StrEnum`（str 混入，config.py），不迁 `enum.StrEnum`——Python 3.10 兼容底线，CI 有 3.10 矩阵。
- **K2** CI 必带 `PYTHONUTF8=1` env；所有 checkout step `fetch-depth: 0`（历史扫描守门前置）。
- **K3** CLI 入口 `_ensure_utf8_stdio()` 已挂 main()；后续新增任何会打印中文的脚本（tools/ 下也要）必须同款守卫——"windows 全挂 + ubuntu 全过"家族的防线。
- **K4** 限频下限 3.0s/源（`MIN_REQUEST_INTERVAL_SECONDS`）、删除去抖 N=3（`REMOVAL_DEBOUNCE_ROUNDS`）——改这两个数 = 口径变更，须登记 plan/06 决策记录并同步测试。
- **K5** 失败隔离契约：适配器 `fetch_list` 不抛异常、返回 `FetchOutcome`；registry 兜底捕获是最后防线不是常规路径。解析不出整条跳过，禁止启发式兜底正则。
- **K6** status 门控：只有 `verified` 字段可进推送路径（M4 feeds 实现时在模型层强制）；`pending` 绝不臆测补值。
- **K7** 测试全离线：任何测试不得触网；真实页面结构一律走 fixtures 回放。
- **K8** 假名白名单 `FAKE_ORG_WHITELIST`：合成样例单位名唯一合法来源；fixtures 入仓前必须过"无真实院校名/无个人信息"自查。
- **K9** 品牌隔离：不复制姊妹项目代码；公开文档不提其余项目业务领域。
- **K10** 缓存边界：raw HTML 只落 `cache/`（git-ignored）；入仓 fixtures 是脱敏挑选的最小片段。

## 四、本机环境坑（只记实测过的）

- 本机 Python：`py -0p` = 3.8.8 + 3.12.10；项目 venv 用 3.12（`.venv/`，已 git-ignore）。3.8 通道**跑不了本项目**（requires-python ≥3.10）。
- Git Bash 下运行 venv 可执行：用 `.venv/Scripts/python.exe` / `.venv/Scripts/jobsctl.exe` 正斜杠相对形式可跑。
- pip 装包如遇代理污染（127.0.0.1:7897 报错）：`NO_PROXY="*" no_proxy="*"` 前缀。
- 中文路径在 git 输出里是八进制转义（显示问题，hash 与内容可信）；需要可读路径加 `-c core.quotepath=false`。

## 五、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 全量测试（当前 7 项，全离线）
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe --version         # CLI 冒烟
.venv/Scripts/jobsctl.exe sources           # 已注册适配器列表（M0 期:空）
.venv/Scripts/jobsctl.exe crawl --source "" # 抓取空源集的汇总表输出
```

## 六、M0 DoD checklist（已完成项的证据指针）

| 项 | 证据 |
|---|---|
| plan 00–06 齐全 | plan/ 目录 7 文件 |
| 可安装 + CLI 冒烟 | `pip install -e .[dev]` 输出；`jobsctl --version` = 0.1.0 |
| 测试绿 | pytest 7 passed（0.13s）；ruff All checks passed |
| M0 基建 | .gitattributes（eol=lf + 二进制标注）；ci.yml（PYTHONUTF8/fetch-depth:0/3.10+3.12 矩阵）；cli.py `_ensure_utf8_stdio` |
| 3.10 兼容修复 | config.py `_StrEnum`；决策记录 plan/06 2026-10-14 行 |
| 诚实口径 | plan/06 第四节："未接远端，CI 待首推验证"，无"CI 绿"表述 |

## 七、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M1.md" 继续完成任务
```
