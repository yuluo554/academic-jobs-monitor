# nju fixture 结构笔记

- **实测日**：2026-10-14（M1 当轮直连复核 `https://hr.nju.edu.cn/`，HTTP 200、UTF-8、约 53KB 服务端渲染；证据留存 `cache/raw/verify/nju.html`）。结构与 data/README.md 原记录一致，无变化。
- **入口**：首页即含通知公告条目（人事处通知/公告区块）。
- **列表容器**：`li.news`（类名带序号修饰如 `news 1`/`news 2`），内含 `span.news_title`。
- **条目字段位置**：
  - 详情 URL：`span.news_title > a[href]`，格式 `/xx/xx/c5977a<id>/page.htm`（相对路径，`urljoin("https://hr.nju.edu.cn/", href)`）；
  - 标题：`a` 的 `title` 属性为完整标题；`a` 文本为**省略号截断版**（"…工作..."）→ **以 title 属性为准**；
  - 日期：`span.news_meta`（同级 span，格式 `YYYY-MM-DD`）；
  - 阅读数：`span.news_meta1`（`(888)`，不入字段库）。
- **日期格式**：`YYYY-MM-DD`。
- **边界样例**（fixture 已含）：
  - 无日期的导航类条目（意见反馈 `lyb/list.htm`，无 `news_meta`）→ 适配器应整条跳过（解析不出日期且非招聘类）；
  - a 文本与 title 属性不一致（截断）→ 用 title。
- **风险**：首页条目混有"通知/培训/评定"类非招聘公告 → M2 适配器先全量入 RawItem，招聘/非招聘分类留 M3 抽取层判定（题面任务 1 是"原始条目"，不做语义过滤）。
- **脱敏说明**：真实校名替换为假名白名单；URL id 改为 844001 起合成值；无个人信息。
