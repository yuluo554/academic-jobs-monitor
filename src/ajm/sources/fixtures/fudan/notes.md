# fudan fixture 结构笔记

- **实测日**：2026-10-14（M1 当轮直连复核 `https://hr.fudan.edu.cn/15364/list.htm`，HTTP 200、UTF-8、约 30KB 服务端渲染；证据留存 `cache/raw/verify/fudan.html`）。结构与 data/README.md 原记录一致，无变化。
- **入口**：`/15364/list.htm`（"教学科研"栏目页，页面 title 即"教学科研"）。
- **列表容器**：`div#wp_news_w9`（或同构的 `wp_news_w*` 容器），条目为 `a.column-news-item`。
- **条目字段位置**：
  - 详情 URL：`a.column-news-item` 的 `href`，格式 `/xx/xx/c15364a<id>/page.htm`（站内绝对路径，`urljoin("https://hr.fudan.edu.cn/", href)`）；
  - 标题：`span.column-news-title`（无截断，纯文本）；
  - 日期：`span.column-news-date`（可能带 `news-date-hide` 修饰类）。
- **日期格式**：`YYYY-MM-DD`。
- **边界样例**（fixture 已含）：
  - 栏目导航链接（`/4841/list.htm` 等 `list.htm` 结尾）混在同页 → 适配器只取 `a.column-news-item`，天然隔离 `column-item-link`；
  - 页面还有博士后/科研助理子栏目入口（`/4841/list.htm`、`/10838/list.htm`），M2 可作扩展列表源。
- **脱敏说明**：真实院系/中心名替换为假名白名单组合；URL 中 a<id> 数字保持格式但取合成值附近改写；无个人信息。
