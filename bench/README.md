# bench/ — 内置基准（题面任务 5，零 API、口径公开）

一条命令运行：`jobsctl bench`（离线，不触网；真实两轮实测数据走 `jobsctl snapshot`）。

## 目录

```
src/ajm/bench/
├── truth.py                   ← 真值抽取基准 runner
├── change_cases.py            ← 变更检测基准 runner
└── fixtures/                  ← 随 wheel 分发（非 editable 安装同样可用）
    ├── truth.json             ← 抽取真值库（真实公告 URL + 人工标注 5 字段真值）
    └── change_cases/
        └── cases.json         ← 变更检测基准（多轮受控构造，走 SnapshotPipeline 生产路径）
bench/
└── README.md                  ← 本文件（指标口径权威定义）
```

> 数据在包内（`src/ajm/bench/fixtures/`），runner 用 `Path(__file__).resolve().parent /
> "fixtures"` 解析——所以装成 wheel 后 `jobsctl bench` 读的是 site-packages 里的同一份
> 真值库，不会越界到安装树之外。

## 一、真值抽取基准（`src/ajm/bench/truth.py`）

### 样例构成

- **真实列表页条目**（gaoxiaojob 6 / pku 5 / fudan 5 / nju 5）：真实 URL + 人工标注
  （gaoxiaojob 附 `extra` 结构化输入；pku 详情页 hash 文件名按 M1 口径换合成值）；
- **deadline 规则族样例**（5 条，`example.invalid` 占位 URL + 真实句式 body_text）：
  acabridge 真实页受 WAF 阻断（合规不绕过），其截止日期样例以真实公告句式构造并明确标注；
- **分类样例**（`is_recruitment` 标注 5 条：非招聘通知 ×4、不可判定 ×1）。

### 判定口径（plan/06 M4 决策行 D-M4-1）

| 真值 | 抽取结果 | 判定 |
|---|---|---|
| 非空 | verified 且值相等 | ✅ 对 |
| 非空 | ambiguous 且真值 ∈ candidates | ✅ 对（`ambiguous_right` 单独计数） |
| 非空 | ambiguous 但真值 ∉ candidates | ❌ 错（`ambiguous_wrong`） |
| 非空 | pending | ❌ 错（`miss_should_verify`） |
| 非空 | verified 但值不等 | ❌ 错（计入 `hallucinated`） |
| null（不可见） | pending | ✅ 对 |
| null（不可见） | verified/ambiguous | ❌ 错（`hallucinated`，臆测最严重） |

- **准确率分母**：全部计分样例（真值 null 的 pending 正确也计入分子分母）。
- **相对期限样例**（`deadline_pending_expected: true`）：正确行为 = pending + 证据
  保留（K6），pending 记对；**verified/ambiguous 才记错**；此类不计入分母。
- **`expect_all_pending` 样例**（分类不可判定条目）：全字段 pending 才正确。
- **非招聘条目**（`is_recruitment: false`）：只对账分类，不进字段分母
  （与 `SnapshotPipeline.ingest` 显式跳过的生产口径一致）。
- **position 标注口径**：『教学科研岗位』等类别词不算岗位名；『招聘<N>名 X』的
  人数前缀剥离；『招聘研究人员』类标题动词宾语算岗位名。

### 当前基准（2026-10-14，v1 真值库 27 例）

| 字段 | 准确率 | 扣分项 |
|---|---|---|
| position | 21/22 = 95.5% | 『<实验室>主任招聘公告』句式未覆盖（诚实缺口，见 plan/06） |
| organization | 22/22 = 100% | — |
| discipline | 22/22 = 100% | — |
| compensation | 22/22 = 100% | — |
| deadline | 21/21 = 100%（ambiguous_right=1） | — |
| overall | 108/109 = 99.1% | classification 5/5 |

`jobsctl bench` 对唯一已知扣分项返回退出码 1（NOT PASSED）——**扣分项不隐藏**，
修复句式覆盖后基准自然转绿。

## 二、变更检测基准（`src/ajm/bench/change_cases.py`）

用例 = 多轮受控构造（`example.invalid` 合成域名 + 假名白名单，K8），逐轮
`begin_round → ingest → close_round(seen_urls)` 与生产编排同口径：

| 用例 | 覆盖 |
|---|---|
| four_event_kinds_with_debounce_and_reappear（8 期望） | NEW_POSTING、DEADLINE_CHANGED（截止日改期 2026-12-01→2026-11-15）、ANNOUNCEMENT_REMOVED（去抖 N=3）、CONTENT_CHANGED（删除后复现 + 待遇字段 diff） |
| hash_changed_no_field_diff（2 期望） | 哈希变但字段级无 diff 仍记事件（事件不丢失） |
| update_suffix_is_not_change（1 期望） | pku『（更新）』后缀 ≠ 内容变更（零误报边界） |

判定：期望事件（kind+url 必填，`detail_contains` 子串可选）全检出 **且**
期望之外零事件 = 用例通过（期望之外的事件即误报；同一实际事件只消费一个期望）。

## 三、可证伪探活

`tests/test_m4_bench_subscribe.py::test_truth_bench_is_falsifiable_injected_defect_must_fail`
注入缺陷（运行时删掉 `deadline_cn_ymd` 规则）→ 基准必须报失败。规则族被破坏而
基准仍 PASS 等价于基准失效，此测试保证绝不允许。

## 四、复跑与滚动补充

```bash
jobsctl bench        # 全量跑（真值 + 变更样本），约 0.3s，离线
```

真值库滚动补充方式：新样例追加到 `truth.json` 的 `cases`（真实 URL +
`annotated_at` + 字段级 evidence 片段；个人信息不入库）。标注口径变化须同步
本 README 与 plan/06 决策行。
