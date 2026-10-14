# acabridge fixture 结构笔记

- **实测日**：2026-10-14（M1 当轮直连复核，3 轮独立请求 + 浏览器 UA 1 轮，证据留存 `cache/raw/verify/acabridge.html`）。
- **结构性变化（vs data/README.md 2026-10-14 记录"可直连、初始列表服务端渲染"）**：
  1. `https://zpjob.acabridge.cn/` 现 **302 跳转** 到 `https://www.acabridge.net/#/job`（换主域 + hash 路由 SPA）；
  2. 落地页被**阿里云 WAF 滑块验证**稳定拦截（响应含 `aliyun_waf_aa/bb` meta + captcha 脚本），换浏览器 UA/Referer/Sec-Fetch 头均不通过；
  3. 无服务端渲染的列表条目可解析（页面 16KB 全为 WAF 脚本，无 title、无列表链接）。
- **fixture 文件**：`waf_interstitial.html` 为拦截页最小结构复刻（脚本截断、特征类名保留），供 M2 适配器的"识别 WAF 拦截页 → `FailureCode.HTTP_ERROR`（或新增专用原因码）"离线测试用。
- **M2 处置口径**：acabridge 适配器仍注册但预期返回 failure（原因码待 M2 拍板：`http_error` + detail="waf_interstitial"）；**不得**试图绕过滑块验证（合规红线）。是否改判"首期 4 源"由用户在决策记录拍板——fixture 与测试按"5 源注册、1 源稳定失败隔离"写。
- **脱敏说明**：WAF 页无院校名/个人信息；meta content 值替换为 fixture-placeholder。
