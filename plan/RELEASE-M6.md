# RELEASE-M6 — 脱敏与发布留档

> M6 执行台账：脱敏四步 → 干净环境验证 → 演示物料 → 发布。命令与结论逐条落盘，供发布后复核与 HANDOFF-M7 引用。

## 一、脱敏四步（HANDOFF-M6 §三.1）

### ① 历史全量假名扫描（K8）

- 方法：对 `git rev-list --all` 全部提交做全 blob `git grep -l -E "北京大学|清华大学|复旦大学|南京大学|中国科学院"`（排除 `bench/truth.json` 路径），并对 K8 黑名单标记（`tests/test_m4_bench_subscribe.py` 的 `real_org_markers`）复跑。
- **结论**：真实院校名出现在三类位置——
  1. `bench/fixtures/truth.json`（真值标注对象本体，27 例真实公告 URL + 人工标注，K8 显式豁免）；
  2. 文档事实陈述（README 源清单、`data/README.md` 源实测表、plan/01 题面）——高校人事处页面的**公开 URL 本身**是题面"真实公告可回溯"要求的一部分；
  3. 代码注释/测试断言（`src/extract/rules.py` 句式注释、`tests/test_fixtures.py` 黑名单字面量、`tests/test_m4_bench_subscribe.py` 抽取用例）——均为公开机构名，非个人信息。
- **合规判断**：以上均为公开公告元数据（机构名 + 公开 URL），不构成个人信息或未公开数据；fixtures 内院校名已全部假名化（各源 `notes.md` 脱敏说明行佐证），符合 README"合规与隐私"承诺。**待用户拍板后定稿**（HANDOFF-M6 要求 truth.json 豁免发布前重议）。
- 个人信息扫描：全历史 blob 无 `2824098035`（QQ 号）以外个人标识；公告联系人姓名/电话未入任何入仓文件（K 口径）。

### ② git 提交元数据

- `git log --format='%an <%ae>'` 全 8 提交：作者 `yuluo554 <2824098035@qq.com>`。
- **发现**：HANDOFF-M6 预期"占位邮箱即可"，实际是**真实 QQ 邮箱**（本机 git 全局配置所致；plan/06 D2 拍板 B 即"M6 脱敏时统一处理"）。
- **处置（待拍板）**：
  - A. 接受现状公开（QQ 邮箱公开可见）；
  - B. `git filter-repo --email-callback`（或 `git filter-branch`）把全历史邮箱替换为 `yuluo554@users.noreply.github.com`，代价是全部提交 hash 变更（本地仓未推送，无协作影响）。
  - 推荐 **B**（plan/06 D2 拍板 B 的自然延伸；推送前做零成本）。

### ③ raw/cache/subscribe.yaml 不在历史 blob

- `git rev-list --all | git ls-tree -r` 全树文件清单中无 `cache/`、`raw/`、`subscribe.yaml`（`git log --all -- cache raw subscribe.yaml data/raw` 为空）；
- `.gitignore` 已含 `cache/`、`*.db`、`subscribe.yaml`、`_private/`；
- `git ls-files` 复核：无任何真实抓取产物入仓。

### ④ 假名扫描测试复跑（CI 维度）

- 本地全量：`pytest` **67 passed** + `ruff check src tests` 全绿（2026-10-14，M6 启动时复跑）；
- 含 `test_repo_fixtures_use_fake_org_names_k8`（K8 扫描）在干净 clone 中再跑一遍（见下节）。

## 二、干净环境验证（HANDOFF-M6 §三.2）

- 干净 clone：`git clone <repo> /d/ProgramData/zcode/_m6_clean_verify`（HEAD = 6f218b7）；
- 全新 venv：Python 3.12.10；`pip install -e .[dev]` 成功；
- `pytest` → **67 passed**；
- `jobsctl sources` → 5 源齐；`jobsctl bench` → overall 108/109 = 99.1%，变更 11 期望全检出零误报，**exit 1**（诚实扣分项在，如实记录）；
- `jobsctl extract --fixture gaoxiaojob` → 4 items verified 字段正常；
- `jobsctl feed`（先 `cp subscribe.example.yaml subscribe.yaml`）→ 空库 `(no events to feed)` 优雅渲染；
- `jobsctl timeline` → 空库 `(no events)`；
- `jobsctl web --port 8899` → `/ /timeline /subscribe /bench` 全 200，`/docs` 404，bench 页数字 108/109；
- `jobsctl --help` 门禁正常（K7：真实起服务不进单测，人工冒烟补位）。

## 三、演示物料（HANDOFF-M6 §三.3 输入）

- 面板截图（headless Edge 1280×1600，真实快照库 104 条）：`docs/screenshots/panel-{index,timeline,subscribe,bench}.png`；bench 页如实显示 NOT PASSED 与失败明细（不隐藏）。
- 推送样例（真实库 round3 3 条命中，ASCII 文件名）：`docs/release-samples/sample-feed.html`、`docs/release-samples/sample-feed.rss`（RSS 2.0）。
- README 已把 `docs/` 占位指向改为上述具体路径。

## 四、发布执行记录（拍板后回填）

| 步骤 | 命令 | 结论 |
|---|---|---|
| 拍板 | truth.json 口径 / 邮箱处置 / D5 acabridge / 建仓推送 | ✅ 2026-10-14 用户拍板：truth.json **保留真名**（标注对象本体）；邮箱**重写历史为 noreply**；D5 **维持 5 源**；**确认发布** |
| 邮箱重写 | `git-filter-repo --email-callback`（QQ 邮箱 → `yuluo554@users.noreply.github.com`，全 9 提交；备份 `/d/ProgramData/zcode/_m6_backup_pre_rewrite`） | ✅ `git log --all --format='%ae'` 仅剩 noreply；重写后 pytest 67 passed |
| tag | `git tag -a v0.1.0-m6` | ✅ 已打并随 push 同步 |
| 建仓推送 | `gh repo create yuluo554/academic-jobs-monitor --public --source . --push`（网络抖动重试后 main + tag 均成功） | ✅ https://github.com/yuluo554/academic-jobs-monitor |
| CI 首跑 | Actions 页 push 数 = run 数逐条配对 | ✅ run id **38594705592**，success，19s；触发数（main 1 次 push；tag 不触发）= run 数 1，对账一致。此前 GitHub 连接中断约数分钟（443 拒连，api.github.com 可达），重试后恢复，无影响 |
| Release | `gh release create v0.1.0-m6 docs/screenshots/*.png docs/release-samples/*` | ✅ https://github.com/yuluo554/academic-jobs-monitor/releases/tag/v0.1.0-m6（附件 6 个：4 截图 + sample-feed.html + sample-feed.rss，ASCII 名） |
| 发布后复核 | 全新 clone 复跑 pytest + bench（exit 1 如实记录） | ✅ `gh repo clone` → 新 venv → **pytest 67 passed**；bench overall 108/109 = 99.1%，**exit 1（扣分项仍在，如实记录）** |

## 五、诚实口径

- bench exit 1（position 95.5%，『<实验室>主任』句式未覆盖）发布时**在**，发布后复核仍在（如实记录，不隐藏）；
- CI 首跑 run id 38594705592（success，19s），已回填 plan/06 §四尾注；
- 发布时实际推送的 hash 与本文件早期记录的开发期 hash 不同（邮箱重写导致全历史 hash 变更，备份见 §四拍板行）。
