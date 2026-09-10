# 新会话提示词（复制整段粘贴给新窗口的 agent）

你是我的长期开发助手。以下是**当前项目**的完整交接，请先读 `README.md` 与 `docs/NEW_SESSION.md` 再动手。

## 项目
- **考研错题本 km-v2**，位于 **`D:\km-v2`**（生产端口 **8000**，唯一在用系统）。
- 后端 **FastAPI + SQLite（裸 sqlite3，无 ORM）**；前端 **Vue 3 + 自建设计系统「墨纸印」+ KaTeX**，Vite 构建；后端挂载 `frontend/dist`。
- 功能：错题录入（文本/多图截图）→ 错题库 → 复习（间隔重复 1/3/7/15/30 + 四模式练习）→ 沉淀（知识点库/公式/科目指南/统计/生词本）。
- 统一响应 `{code,data,message}`（`ok()/error()`）；有 SPA 回退与全局异常处理；可选 API_TOKEN 鉴权；AI 限流 `AI_RATE_LIMIT=30/min`。

## 铁律（改代码必须遵守）
1. **DeepSeek 为主**：`AI_BASE_URL=https://api.deepseek.com/v1`、`AI_MODEL=deepseek-chat`（文本）；视觉 `deepseek-v4-flash-vision-exp`（同一把 DeepSeek Key，无独立视觉密钥）。
2. **图片一律「先看图提文字(`_vision_extract_text`) → 再文本分析」**；**禁止**单次超大视觉生成（会 300s 超时/返回空）。单图/多图/带参考图都自动检测：**英语→整篇精读**，**数学/408→标准解析**。
3. **内容不许减少**：英语整篇＝原文(左右两栏对照)+全文翻译+逐句拆解(结构/句型)+点词查义+重点短语/生词+多题解析；数学/408 解析要「**懂一题会三题**」+「**先讲透考点（当作读者不会）**」+ **1.1/1.2 分步**。英语解析**不用** 1.1/1.2，用【定位/来源/思路/总结】，且【定位】要点名具体句并引用关键词。
4. **自动识别科目/二级科目**：解析输出 `subject_hint` → 后端 `_auto_subject_ids` 填 `subject_id`/`sub_subject_id`（英语→阅读理解、数学→高等数学、408→计算机网络、政治→马原）。
5. **JSON 健壮性**：`_extract_json` 自动修「未转义反斜杠 / 缺失逗号 / 尾逗号 / 空内容」；`_chat_json` 空或畸形**重试 3 次**、`max_tokens=8000`；连接级错误重试。
6. **英语整篇＝一条错题**：`english_questions` 存全部题目（每题带 `wrong`；错的打「答题失误」标签）；详情用 `EnglishAnalysisPanel`(readonly)；词汇只在智能录入显示，保存后只在生词本。
7. **多图全存**：长题多张截图全部保存到 `images`；错题列表卡片**只显示第 1 张**，点进详情显示全部。
8. **表格/图**：`RichText` 支持 Markdown 表格 + 十六进制等宽 `hex-dump`；AI 只识别不会重绘图，**正确表格/拓扑图看原图**。
9. **超时**：前端 axios 300s；后端 `AI_TIMEOUT=240`、`AI_OCR_TOTAL_TIMEOUT=290`、`AI_VISION_PRIMARY_TIMEOUT=240`。
10. **生词本**：`vocab_items.kind`(word/phrase) + 分类筛选 + 点词查义 `/api/ai/sense` + 去重导入 `/vocab/import-english`。
11. **临时文件放 `D:\temp`**；**密钥不打印**（`.env` 不入库）；改完 **`git add -A && git commit && git push`**。
12. **卡片整卡可点**：知识点/公式卡片点任意位置直接开详情（铺满的 `.k-hit`/`.f-hit` 点击层，操作按钮压在它之上，装饰元素 `pointer-events:none`）；卡片预览用 `markdownToPlain()` 去 Markdown 标记，详情才用 `RichText`。
13. **知识点多图**：`/ai/knowledge-from-image` 收 `{images:[...]}`，按序分批提文字后合并成**一条**草稿；弹窗打开即重置（新增清空/编辑载入），粘贴监听用 `watchEffect` 同步挂载；多文件读取用 `Promise.all` 而非 `for...of + await`。

## 关键文件
- 后端：`app/services/ai_service.py`、`app/routers/ai.py`（`/ai/english`、`/ai/ocr`、`/ai/analyze`、`/ai/sense`、`_auto_subject_ids`、`_vision_extract_with_fallback`）、`app/services/vocab_service.py`、`app/models/tables.py`、`app/database.py`。
- 前端：`components/EnglishAnalysisPanel.vue`（核心）、`views/CaptureView.vue`、`components/KnowledgeEditModal.vue`、`views/KnowledgeView.vue`、`views/FormulaView.vue`、`components/MistakeCard.vue`、`components/DetailMeta.vue`、`ui/QuestionImages.vue`、`utils/markdown.js`、`components/RichText.vue`、`ui/UiModal.vue`。

## 测试与验证（含手法的坑）
- 后端：`cd backend && python -m unittest discover -s tests`（54 个）。
- 前端：`cd frontend && npm test`（Vitest 31 个，含 DOM 级交互回归；`vite.config.js` 里 `test.environment='happy-dom'`）。
- **UiModal 是 Teleport 到 `document.body`**：测试里查弹窗必须 `document.querySelector`，不要用 `wrapper.find`。
- **测试收尾必须 `unmount()`**，不要在 `beforeEach` 里 `document.body.innerHTML=''`——直接清空会让 Vue 的 Teleport 记账错乱，组件监听器静默失效（踩过）。
- 真实浏览器端到端（可选）：Chrome `--headless=new --remote-debugging-port` + 裸 CDP（标准库即可），
  用 `history.pushState({},'','/knowledge')+dispatchEvent(new PopStateEvent('popstate'))` 切路由
  （router 是 `createWebHistory`，不是 hash 路由）。

## 启动与验证
```powershell
# 后端（8000）
Start-Process cmd -ArgumentList '/c','cd /d D:\km-v2\backend && start "" /b "D:\python\python.exe" main.py > km-server.log 2> km-server.err.log' -WindowStyle Hidden
# 验证：必须看 JSON，不能只看状态码
# ⚠️ 勿用 /stats —— 那是前端 SPA 路由，会被 `/{full_path:path}` 回退成 index.html 返回 200（假阳性）
(Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing).Content   # 期望 {"code":0,...,"status":"ok"}
# 也可看 /api/dashboard（错题/复习聚合）
# openviking（1933）
Start-Process cmd -ArgumentList '/c','start "" /b D:\python\python.exe D:\dsh-home\scripts\start_openviking.py' -WindowStyle Hidden
```
- 自启：启动文件夹 `考研错题本自启.vbs`（后端）、`OpenViking自启.vbs`（记忆服务）。**启动文件夹只在 Windows 登录时执行**——只重启 DSH 不会重跑。
- 改前端后必须重建：`cd D:\km-v2\frontend && npm run build`（后端从 dist 提供）。

## OpenViking 记忆库（已跑通，勿动坏）
- **权威配置**：`C:\Users\Administrator\.openviking\ov.conf`（工作区 `C:\Users\Administrator\.openviking`）。旧 `D:\dsh-home\openviking\ov.conf`、`start-server.cmd` 已弃用。
- **VLM**（记忆抽取/查询扩展）：`provider=openai, model=deepseek-v4-flash-vision-exp, api_base=https://api.deepseek.com/v1, api_key=app .env 的 AI_API_KEY`。
- **embedding**：智谱 `embedding-3`（2048 维）。
- 服务端 `127.0.0.1:1933`（`auth_mode=dev`）；`ov` CLI 已配 `local`；`pending/` 会话启动时回放（≤50/次、7 天 TTL、重试 3 次）。
- 自启：`OpenViking自启.vbs` → `D:\dsh-home\scripts\start_openviking.py`（其 CONF 必须指向权威配置）。
- 用法：`ov find "关键词"` / `ov read <viking://...>` / `ov add-memory`；会话里 `mcp__openviking__*` 需 DSH 把 openviking MCP 连到 agent 才可见。
- **经验**：`.overview.md`/`.abstract.md` 是**派生文件，不能手写**；要常驻就写普通资源 `viking://user/default/resources/<名>.md`，再 `ov reindex <uri> --mode semantic_and_vectors --wait true` 让 `find` 命中。

## 近期提交
`d20d838`（英语整篇/解析增强/自动科目/生词分类等大功能）、`d4fc2ab`（列表首图）、`93b261b`（hex 等宽）、`f60464c`（文档），以及后续修复若干。

请先 `git log --oneline -5` 与读 `README.md` 了解现状，再按上述铁律开发。
