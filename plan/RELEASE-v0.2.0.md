# RELEASE-v0.2.0 — 发布面回填：`src/` 五项改动进到下载者手里

> 上一版：`v0.1.0-m6`（2026-10-15）。
> 触发来源：轨 I（发布物一致性）I-1 —— `v0.1.0-m6` 之后 `src/` 有 **19 个文件**的改动
> （五子系统收进 `ajm` 命名空间、数据迁入包内、新增非 editable 安装门禁），
> 这些改动**从未随任何 tag 发布过**。下载 `v0.1.0-m6` 源码包的人拿到的是旧布局。

## 一、相对 v0.1.0-m6 改了什么

| 类别 | 内容 | 用户能否感知 |
|---|---|---|
`src/` 布局 | `src/{bench,extract,snapshot,subscribe,webapp}/` → `src/ajm/{...}/`（5 个子系统 17 个文件 `R100`/`R09x` 重命名） | **能**：`pip install` 不再向 `site-packages` 顶层投 `bench` / `extract` 这类通用名 |
随包数据 | `bench/fixtures/{truth.json,change_cases/cases.json}` → `src/ajm/bench/fixtures/`（`R100`） | **能**：wheel 里数据跟着包走 |
`src/ajm/cli.py` / `config.py` / `models.py` | 适配新布局；版本号来源统一 | 内部 |
`requires-python` | `>=3.10` → **`>=3.12`** | **能（破坏性）**：3.10/3.11 装不上 |
`build-system` | hatchling；`[tool.hatch.build.targets.wheel] packages = ["src/ajm"]` | 内部 |
`pytest` | 新增 `pythonpath = ["src"]` + `slow` marker | 开发期 |
测试 | 新增 `tests/test_packaging.py`（10 项，`slow`）；总量 67 → **84** | 开发期 |

**没有改**：抓取源清单、抽取规则、快照 diff 语义、订阅推送格式、Web 面板路由、
bench 真值（仍 108/109 = 99.1%，`position` 句式扣分如实保留，`jobsctl bench` 仍 exit 1）。

## 二、为什么版本号是 0.2.0 而不是 0.1.1

`requires-python` 由 3.10 抬到 3.12 是**不兼容变更**：0.x 阶段按 semver 惯例走 minor。
把它当补丁发会让「我锁了 0.1.x，py3.10 上突然装不上」变成静默事故。

## 三、验证

| 项 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `.venv/Scripts/python.exe -m pytest -q` | **84 passed** |
| ruff | `.venv/Scripts/python.exe -m ruff check src tests` | `All checks passed!` |
| HEAD 的 CI | `gh api repos/yuluo554/academic-jobs-monitor/commits/<sha>/check-runs` | 发布前 `6ef7cf9` 全 `success` |

## 四、附件形态

本仓的发布物是**源码**：没有 exe / wheel 附件（README 明确「PyPI 上不存在」，
两条安装路径都是源码）。故 Release 只附**源码包**，与 `v0.1.0-m6` 的形态不同
（那版附的是 4 张面板截图 + sample-feed.html/.rss）。

- 附件：`ajm-0.2.0.tar.gz`（确定性：`tar` 按路径排序 + 固定 mtime，与 `v0.1.0-m6` 同配方）
- sha256：见 Release 说明（**不写进包内**，自指必过期）

## 五、历史结论是否需重跑

**需要重跑一处**：`v0.1.0-m6` 的 bench 报告写的是旧布局下的命令路径。
判定结论（108/109 = 99.1%）**不变** —— 真值库逐字节未改（`R100`），
只是 `bench` 子命令的模块路径从 `bench.runner` 变成 `ajm.bench.runner`。
若你按旧报告里的 `import bench` 写脚本，需改成 `from ajm.bench import ...`。
