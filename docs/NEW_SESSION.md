# 【km-v2 考研错题本】新会话 / 新 Agent 交接提示词

> 打开新会话（或把本仓库交给 ZCode / Codex / Claude 等编码 Agent）时，把本块连同仓库一起交给对方即可无缝接管。项目在 **`D:\km-v2`**（生产端口 8000），是唯一在用系统。**先读 `README.md` 与仓库根 `AGENTS.md`**（内含完整约定）。

## 项目定位
单用户考研错题本：错题录入（文本/多图截图）、错题库、复习（1/3/7/15/30）、生词本、知识点库、公式、科目指南、统计。后端 FastAPI+SQLite（无 ORM），前端 Vue3+自建设计系统「墨纸印」（无 UI 框架库），Vite 构建。**先读 `README.md` 与 `AGENTS.md`，提交前 `git add -A && git commit && git push`，临时文件放 `D:\temp`，密钥不打印。**

## 关键约定（务必遵守）
1. **DeepSeek 视觉首选**：`AI_BASE_URL=https://api.deepseek.com/v1`，`AI_MODEL=deepseek-chat`（文本），视觉模型 `deepseek-v4-flash-vision-exp`（走同一把 DeepSeek Key，无额外密钥）。
2. **图片识别一律「先看图提文字→再用文本分析」**：`_vision_extract_text`（快、稳）→ `analyze_english`/`_analyze_standard_content`（文本）。**禁止**"单次视觉大生成"（会 300s 超时/空返回）。单图/多图/带参考图都自动检测语言（英语→精读；数学/408→标准）。
3. **内容不能减少**：英语整篇要原文(左右对照)/全文翻译/句子拆解(结构+句型)/重点短语/生词/多题解析；数学/408 解析要「懂一题会三题」+「先讲透考点(当作读者不会)」+ 1.1/1.2 分步详细。英语解析不用 1.1/1.2，用【定位/来源/思路/总结】，【定位】必须点名具体句并引用关键词。
4. **自动识别科目/二级科目**：解析输出 `subject_hint`（数学/英语/408/政治），后端 `_auto_subject_ids` 映射填 `subject_id`/`sub_subject_id`（英语→阅读理解，数学→高等数学，408→计算机网络，政治→马原）。
5. **超大 JSON 健壮性**：`_extract_json` 自动修复「未转义反斜杠、缺失逗号、尾逗号、空内容」；`_chat_json` 对空/畸形**重试 3 次**、`max_tokens=8000`；连接级错误重试。
6. **英语整篇 = 一条错题**：`整篇全部录入` 存一条错题（含 `english_questions` 全部题目，每题带 `wrong` 标记；错的题自动打「答题失误」标签+思路前缀）；详情用 `EnglishAnalysisPanel`（readonly）展示整篇（原文对照/翻译/拆解/各题选错/句型/词汇）；词汇只在智能录入显示，保存后只在生词本。
7. **多图全存**：长题多张截图**全部**保存到 `images`；错题列表卡片**只显示第 1 张**，点进详情显示全部。
8. **表格/图**：`RichText` 支持 Markdown 表格 + 十六进制等宽 `hex-dump`；AI 只会识别图不会重绘，正确表格/拓扑图看**原图**。
9. **超时**：前端 axios 300s；后端 `AI_TIMEOUT=240`、`AI_OCR_TOTAL_TIMEOUT=290`、`AI_VISION_PRIMARY_TIMEOUT=240`。
10. **生词本**：`vocab_items` 有 `kind`（word/phrase），页面有「全部/单词/短语」筛选+「词语」标签；点词查义 `/api/ai/sense`；导入 `/vocab/import-english`（去重）。

## 主要文件
- 后端：`app/services/ai_service.py`（英语/标准分析、OCR→文本、JSON 修复、自动科目）、`app/routers/ai.py`（`/ai/english`、`/ai/ocr`、`/ai/analyze`、`/ai/sense`、`_auto_subject_ids`）、`app/services/vocab_service.py`（kind）、`app/models/tables.py`+`app/database.py`（迁移）。
- 前端：`components/EnglishAnalysisPanel.vue`（整篇精读，核心）、`views/CaptureView.vue`（多图/粘贴目标/自动检测）、`components/MistakeCard.vue`（列表首图）、`components/DetailMeta.vue`+`ui/QuestionImages.vue`（详情全图/首图）、`utils/markdown.js`+`components/RichText.vue`（表格/hex）、`ui/UiModal.vue`（加宽）。

## openviking（已跑通，勿动坏；2026-09-06 修复配置分裂）
- **规范配置 = `~\.openviking\ov.conf`**（JSON）。工作区 = `C:\Users\Administrator\.openviking`（记忆库 `pending/vectordb/viking` 都在此）。
- 服务：`openviking-server.exe --config C:\Users\Administrator\.openviking\ov.conf`，监听 **127.0.0.1:1933**。
- **embedding**（检索/向量）：智谱 `provider=openai`、`api_base=https://open.bigmodel.cn/api/paas/v4`、`model=embedding-3`、`dimension=2048`、`api_key`=app `.env` 的 `AI_VISION_API_KEY`（读入配置、不打印）。
- **VLM**（生成式，用于**记忆抽取 + 查询扩展**）：`provider=openai`、`model=deepseek-v4-flash-vision-exp`、`api_base=https://api.deepseek.com/v1`、`api_key`=app `.env` 的 `AI_API_KEY`（DeepSeek 同一把）。⚠️ 此块缺失会报 `api_key client option must be set` 导致记忆抽取失败。
- **自启**：启动文件夹唯一条目 `OpenViking自启.vbs`（幂等，先查 1933）→ `D:\dsh-home\scripts\start_openviking.py`；**该脚本 `CONF` 必须指向上面规范配置**（曾误指 `D:\dsh-home\openviking\ov.conf`，已改回）。旧的 `start-server.cmd`、启动文件夹里 `openviking-server.cmd`、以及 `D:\dsh-home\openviking\ov.conf`（指向 D 盘另一工作区）**已弃用，勿再使用**。
- `pending/` 会话文件**会话启动时**由插件 `replayPending` 回填（每次≤50）；`ov find` 可语义检索。**MCP 工具 `mcp__openviking__*` 需宿主（DSH 等）把 openviking MCP 连到 agent 会话才可见。**
- 备份：`~\.openviking\ov.conf.bak`（原始）、`.bak-ds`（DeepSeek 改前）。`ov` CLI 已配置 `local`。

## 现状（2026-09-06）
- git HEAD = `aad766f`（修正 openviking 配置分裂说明）。历史：`d20d838`（大功能）、`d4fc2ab`（列表首图）、`93b261b`（hex 等宽）、`f60464c`（文档）。
- 后端 8000 运行中；前端 `frontend/dist` 已构建。
- openviking 已修复并验证正常：VLM = DeepSeek `deepseek-v4-flash-vision-exp`；规范配置 C 盘 `~\.openviking\ov.conf`；自启 vbs→`start_openviking.py`（其 CONF 指向规范配置）；`pending/` 已清理。
