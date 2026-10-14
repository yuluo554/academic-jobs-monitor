# pku fixture 结构笔记

- **实测日**：2026-10-14（M1 当轮直连复核 `https://hr.pku.edu.cn/`，HTTP 200、UTF-8、约 52KB 服务端渲染；证据留存 `cache/raw/verify/pku.html`）。结构与 data/README.md 原记录一致，无变化。
- **入口**：首页即含招聘条目；招聘专栏路径前缀 `rczp/`（教学科研 `rczp/jxky/`、行政教辅 `rczp/xzjf/`、应届毕业生 `rczp/yjbys/`）。
- **列表容器**：首页新闻列表 `li > a[href^="rczp/"]`（fixture 用 `ul.news-list` 简化包裹，真实页容器类名不同但 li>a 结构一致——适配器按 `li > a[title*="发布日期"]` 定位，不依赖外层容器类名）。
- **条目字段位置**：
  - 标题 + 发布日期：均在 `a` 的 `title` 属性，格式 `"<标题> 发布日期：YYYY-MM-DD "`（注意尾随空格；日期与标题之间是全角冒号"："）；
  - 冗余日期：`a > div.date > span.gp-f16`（同值，可交叉校验）；
  - 标题冗余：`a > div.mode1r > p.gp-ellipsis`（有省略号截断风险，**以 title 属性为准**）。
- **日期格式**：`YYYY-MM-DD`。
- **边界样例**（fixture 已含）：
  - 外链条目：博士后栏跳 `http://postdocs.…`（绝对 URL 他域）→ 适配器应整条跳过或按 absolute URL 处理，M2 拍板；
  - title 含"（更新）"后缀（内容更新型条目，变更检测注意 title 不宜直接入 content_hash）；
  - 条目相对路径（无前导 `/`），拼 URL 需 `urljoin("https://hr.pku.edu.cn/", href)`。
- **脱敏说明**：真实校名/院系名替换为假名白名单；详情页 32 位 hash 文件名替换为 `aa0…1` 合成值；无个人信息。
