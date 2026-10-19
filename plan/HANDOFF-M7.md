# HANDOFF-M7 — 交棒：收尾清点与演示（最终里程碑）

> M6（脱敏发布）已全部完成并落盘。下一对话启动提示词：`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M7.md" 继续完成任务`。

## 一、M6 产出与证据（全部完成）

- **脱敏四步**（台账 `plan/RELEASE-M6.md`）：
  - ① 历史全量假名扫描：真实院校名仅在 truth.json（标注对象本体）+ 文档事实陈述 + 代码注释/测试黑名单；fixtures 全假名化；**用户拍板 truth.json 保留真名**；
  - ② 提交元数据：全历史 QQ 邮箱 → `git-filter-repo` 重写为 `yuluo554@users.noreply.github.com`（**全部 hash 已变**，备份 `/d/ProgramData/zcode/_m6_backup_pre_rewrite`；本地 git config 已同步 noreply）；
  - ③ cache/raw/subscribe.yaml 确认不在任何历史 blob；.gitignore 覆盖；
  - ④ pytest 67 passed + ruff 全绿（发布前本地 + 干净 clone 双重复跑）。
- **干净环境验证**：干净 clone + 全新 venv（3.12.10）→ `pip install -e .[dev]` → pytest 67 passed → sources/extract/bench/feed/timeline/web 全部按 README 跑通（bench exit 1 如实；web 4 页 200 + /docs 404）。
- **发布**：用户确认后打 tag `v0.1.0-m6` → 公开仓 https://github.com/yuluo554/academic-jobs-monitor → Release 附 4 截图 + sample-feed.html/.rss（ASCII 名）。过程中 GitHub 443 短时中断，重试恢复。
- **CI 首跑对账**：run id **38594705592**，success（19s）；触发数（main 1 次 push；tag 不触发）= run 数 1 ✓。plan/06 §四尾注已据实补记（"CI 从未运行"口径终结）。
- **发布后复核**：`gh repo clone` → 新 venv → pytest 67 passed + bench 108/109 = 99.1%，exit 1（扣分项仍在，如实记录）。
- README M6 行 ✅（Release 链接）；D1/D2/D5 拍板全部闭环。

## 二、M7 待办（下一对话从这里开始）

1. **题面交付对标逐行核对**（plan/01 §三 ↔ plan/06 §一）：
   | 题面提交材料 | 交付物 | 状态 |
   |---|---|---|
   | 1. Web 面板 + CLI 双入口 | `src/ajm/webapp/` + `src/ajm/cli.py`（三方对账测试） | ✅ |
   | 2. 核心代码框架（5 子系统） | `src/ajm/{sources,extract,snapshot,subscribe,bench}` | ✅ |
   | 3. 技术报告 | `docs/技术报告.md` | ✅ |
   | 4. 真值库与基准报告 | `src/ajm/bench/fixtures/truth.json` + `jobsctl bench` + bench/README | ✅ |
   | 5. Release 附截图/样例 RSS | v0.1.0-m6 附件 6 个 | ✅ |
   核对时逐行打开实物验证（勿只信本表），结论回填 plan/06 §一最后一列。
2. **演示脚本**（`docs/演示脚本.md`）：面向评分视角的 10 分钟走查——`jobsctl sources` → `snapshot`（真实一轮）→ `timeline` → `feed` → `bench`（99.1% + 诚实扣分）→ `web` 四页；每步给预期输出样例（可从本文件 §四与 RELEASE-M6 抄）。
3. （可选加分）修复『<实验室>主任』position 句式 → bench overall 100%、exit 0：须同步 bench/README、README 基准表、对账测试锚定断言 108/109、plan/06、RELEASE-M6 §五——改的是"正向变更"，纪律是全链路同步，不修也属诚实口径。
4. （可选）清理本地验证目录 `/d/ProgramData/zcode/_m6_clean_verify`、`_m6_post_release`、`_m6_backup_pre_rewrite`（确认稳定后删；备份至少保留到 M7 验收完）。
5. 收尾提交推送 + 本地 pytest/ruff 复跑，最终 commit 后在 plan/00 或 README 标注"项目收尾完成"。

## 三、既定口径（延续 M6 全部 K1–K10 + M5/M6 增补）

- K5 失败隔离禁启发式兜底；K6 仅 verified 出镜；K7 测试全离线（web 用 TestClient）；K8 假名扫描（truth.json 豁免已由用户拍板**永久保留真名**）；
- M6 新增：提交邮箱一律 `yuluo554@users.noreply.github.com`（本地 config 已设，后续新提交自动合规）；发布产物 hash 以 GitHub 远端为准；
- bench 锚定断言 108/109：滚动补样例合法变更时须同步测试 + bench/README + README。

## 四、关键命令速查

```bash
cd <项目根>
.venv/Scripts/python.exe -m pytest          # 77 项（67 + 10 打包守门），全离线
.venv/Scripts/python.exe -m pytest -m "not slow"   # 67 项，快反馈（CI test job 口径）
.venv/Scripts/python.exe -m pytest -m slow         # 10 项打包守门（CI packaging job 口径）
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/jobsctl.exe bench             # 99.1% + 变更全检出（exit 1=扣分项在）
.venv/Scripts/jobsctl.exe web               # http://127.0.0.1:8000
git push origin main                        # 远端已配好（https，noreply 邮箱）
gh run list --repo yuluo554/academic-jobs-monitor   # CI 对账
```

## 五、已知缺口（诚实保留）

- bench 唯一扣分项仍在（position 95.5%，overall 99.1%，exit 1）——M7 可选项 3 可修；
- 截止日期均为列表页/结构化字段所得，详情页二级抓取（gaoxiaojob 截止日期埋正文）未做——题面扩展项，非必交；
- 清华/浙大/博士招生网不可获取，首期不纳入（如实登记于 data/README.md 与 plan/01 §五）。

**【2026-10-19 已闭环】D1 非 editable 安装缺陷（原诊断 P1）**
原状态：`pyproject.toml` 只打包 `src/ajm`，而 `cli.py` 在 5 个子命令内部惰性 import
`extract`/`snapshot`/`subscribe`/`bench`/`webapp` 五个**顶层同级包**。`pip wheel .` 出来的
wheel 只含 `ajm/` + dist-info；装进全新 venv 后 8 个子命令里 5 个 `ModuleNotFoundError`。
本地与 CI 长期全绿是因为 hatchling 的 editable 安装把仓库 `src` 的绝对路径写进
`_editable_impl_ajm.pth`，`import extract` 因此成立——**"干净环境验证"实际全是 `-e`**。

修复（M7 迭代，见 plan/06 2026-10-19 行）：
- 五包 `git mv` 进 `src/ajm/`，import 全改 `ajm.` 前缀；真值库/变更样本迁到
  `src/ajm/bench/fixtures/` 并改相对本模块解析（原 `parents[2]` 在 site-packages 下越界）；
- 门禁：`tests/test_packaging.py`（9 项）+ CI `packaging` job，覆盖 wheel 内容、
  dist-info 元数据、venv 非 editable 自证、5 条子命令；CI `test` job 跑 `-m "not slow"`；
- 解释器 floor 抬到 3.12（DEC3=B），`_StrEnum` 改用 `enum.StrEnum`。

复验口径（已实测）：全新 venv 装 wheel + **中立目录**下跑
`sources` / `timeline` / `extract --fixture pku` / `bench` / `feed` / `web` 六条全通；
`bench` 仍是 108/109 = 99.1%、**exit 1**（诚实扣分项未动）。
仍待复验的是**新 CI 三 job 的实际结论**——需推送后才可见（本轮不推送）。

## 六、启动提示词（下一对话）

```
/goal 读取 "<项目绝对路径>\plan\HANDOFF-M7.md" 继续完成任务
```
