# gaoxiaojob fixture 结构笔记

- **实测日**：2026-10-14（M1 当轮直连复核，留存 `cache/raw/verify/gzj_main.html` / `column11.html`，不入仓）。
- **入口变化（vs data/README.md 2026-10-14 记录）**：原 `https://www.gaoxiaojob.com/zhaopin/index.html` 返回 404；`/zhaopin/` 路径 403 反爬。可用入口：首页 `https://www.gaoxiaojob.com/`（200，约 1.17MB 服务端渲染）与地域栏目页 `https://www.gaoxiaojob.com/column/<id>.html`（200，约 480KB）。首期取 `/column/11.html`（北京地域）作列表源。
- **列表容器**：`.job-board .list ul`，条目为 `ul > li > a[href^="/job/detail/"]`。
- **条目字段位置**（全部在 `<a>` 内嵌 div）：
  - 职位名：`div.position h6`（`a` 的 `title` 属性同值，可作冗余校验）；
  - 待遇：`div.position span.money`（"面议" 或 "年薪30-50万"）；
  - 学历/学科/招聘人数：`div.requirement span`（3 个，顺序固定）；
  - 单位：`div.region span.school`；城市：`div.region .city-place span.city`。
- **详情 URL**：`https://www.gaoxiaojob.com/job/detail/<id>.html`。
- **日期**：列表页条目**无发布日期字段**（复核确认，全页仅 2 处"今日更新"型日期）→ M2 适配器 `published_on=None`（status 门控下不臆测），日期需详情页二级抓取（扩展项）。
- **分页**：`/column/<id>-<page>.html`（fixture 边界样例：4 页样式）。
- **风险**：深层列表/详情页有 403 反爬记录（data/README.md #1）；首页体积大（1.17MB），首期只解析栏目页。
- **脱敏说明**：真实页中的院校/单位名全部替换为 `FAKE_ORG_WHITELIST` 假名；URL id 改为 9000001 起的合成值；无个人信息。
