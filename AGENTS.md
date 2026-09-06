# AGENTS.md — 研错本（考研错题本 km-v2）

> 本文件是仓库级 Agent 指南（ZCode / Codex / Claude 等编码 Agent 均会读取）。
> 作用：无缝接管本系统，并按项目约定构建 / 维护。位置 `D:\km-v2`（**唯一在用系统**，生产端口 8000）。

## 0. 一句话
单用户考研错题本：错题录入（文本 / 多图截图）、错题库、复习（1/3/7/15/30 天）、生词本（英语单词闪卡）、知识点库、公式背诵、科目指南、统计。
后端 **FastAPI + SQLite（无 ORM）**，前端 **Vue3 + 自建设计系统「墨纸印」（零 UI 框架库）** + KaTeX，Vite 构建。

## 1. 关键位置
- 仓库根 = `D:\km-v2`
- 后端：`backend/`（入口 `backend/main.py`，挂 `frontend/dist`，监听 127.0.0.1:8000）
- 前端：`frontend/`（源码 `src/`，构建产物 `frontend/dist`）
- 数据：`data/kaoyan_mistakes.db`（SQLite；迁移版本门控 v5；启动前自动备份保留 20 份）
- 文档：`docs/`（api.md / architecture.md / NEW_SESSION.md / notes/）
- 视觉脚本：`scripts/vision_request.py`

## 2. 启动与构建
```bash
# 生产（默认，开机自启用）
cd backend && pip install -r requirements.txt && python main.py   # http://127.0.0.1:8000

# 前端构建
cd frontend && npm install && npm run build

# 开发（前后端分离，热更新）
# 后端照常 8000；另开终端：
cd frontend && npm run dev   # http://127.0.0.1:5174，已代理 /api 与 /images 到 8000

# 一键启动：双击 start_backend.cmd
# 开机自启：开始菜单启动文件夹中的 考研错题本自启.vbs（已在运行则跳过；日志 D:\temp\km-launch.log）

# 测试
cd backend && python -m unittest discover -s tests -v   # 临时库，不碰真实数据
```

## 3. 提交与数据规范（务必遵守）
- 每次完成代码 / 数据 / 文档修改并**验证通过**后：`git add -A && git commit -m "简短说明" && git push`
  - `origin = https://github.com/MyHeartBea/selfstudy.git`，分支 `main`，Git Credential Manager 已登录。
  - 若 push 报代理（`127.0.0.1:7897`）不可达：`git -c http.proxy= -c https.proxy= push -u origin main`（本机直连 github 是通的）。
- `.env`、数据库、`node_modules`、`dist`、日志一律**不入库**。
- C 盘空间紧张：临时文件一律放 `D:\temp`。
- **密钥不打印**：`backend/.env`、`~\.openviking\ov.conf` 里的任何 key，一律不得输出到对话 / 日志 / 提交。

## 4. AI 配置（backend/.env，不入库）
| 变量 | 值（示意） | 用途 |
|---|---|---|
| `AI_API_KEY` | DeepSeek key | 文本模型 |
| `AI_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek 端点 |
| `AI_MODEL` | `deepseek-chat` | 文本模型名 |
| `AI_VISION_MODEL` | `glm-4.6v-flash` | 视觉模型（当前**智谱**） |
| `AI_VISION_MODEL_FALLBACK` | `glm-4.6v-flashx` | 视觉兜底 |
| `AI_VISION_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | 智谱视觉端点 |
| `AI_VISION_API_KEY` | 智谱 key | 智谱视觉 / 嵌入 |

> 约定：视觉**首选 DeepSeek** `deepseek-v4-flash-vision-exp`（走 `AI_API_KEY` 同一把 DeepSeek key，已在 `GET /v1/models` 确认可用）。当前 `.env` 的 `AI_VISION_MODEL` 为智谱 `glm-4.6v-flash`。改视觉时以 `.env` 实际值为准，并遵循下方「先提文字再分析」。

超时：前端 axios 300s；后端 `AI_TIMEOUT=240`、`AI_OCR_TOTAL_TIMEOUT=290`、`AI_VISION_PRIMARY_TIMEOUT=240`。

## 5. 核心 AI 约定（修改 / 新增 AI 功能时务必遵守）
1. **图片一律「先看图提文字 → 再文本分析」**：`_vision_extract_text`（快、稳）→ `analyze_english` / `_analyze_standard_content`（文本）。**禁止单次超大视觉生成**（会 300s 超时 / 空返回）。单图 / 多图 / 带参考图都自动检测语言：英语 → 精读；数学 / 408 → 标准。
2. **内容不能减少**：
   - 英语整篇 = 原文**左右对照** + 全文翻译 + 逐句拆解（结构 + 句型）+ 重点短语 + 生词 + **多题解析**。
   - 数学 / 408 = 「懂一题会三题」+「先讲透考点（当作读者不会）」+ 1.1 / 1.2 分步详细。
   - 英语解析**不用** 1.1/1.2，用【定位 / 来源 / 思路 / 总结】；【定位】必须点名具体句并引用关键词。
3. **自动识别科目 / 二级科目**：解析输出 `subject_hint`（数学 / 英语 / 408 / 政治），后端 `_auto_subject_ids` 映射填 `subject_id` / `sub_subject_id`（英语→阅读理解，数学→高等数学，408→计算机网络，政治→马原）。
4. **超大 JSON 健壮性**：`_extract_json` 自动修复「未转义反斜杠 / 缺失逗号 / 尾逗号 / 空内容」；`_chat_json` 对空 / 畸形**重试 3 次**、`max_tokens=8000`；连接级错误重试。
5. **英语整篇 = 一条错题**：存一条错题（含 `english_questions` 全部题目，每题带 `wrong` 标记；错的题自动打「答题失误」标签 + 思路前缀）；详情用 `EnglishAnalysisPanel`（readonly）展示整篇；词汇只在智能录入显示，保存后只在生词本。
6. **多图全存**：长题多张截图**全部**保存到 `images`；错题列表卡片**只显示第 1 张**，点进详情显示全部。
7. **表格 / 图**：`RichText` 支持 Markdown 表格 + 十六进制等宽 `hex-dump`；AI 只会识别图不会重绘，正确表格 / 拓扑图看**原图**。
8. **生词本**：`vocab_items` 有 `kind`（word / phrase）+「全部 / 单词 / 短语」筛选 +「词语」标签；点词查义 `/api/ai/sense`；导入 `/vocab/import-english`（去重）。

## 6. 关键文件
后端（`backend/app/`）：
- `services/ai_service.py`：英语 / 标准分析、OCR→文本、JSON 修复、自动科目。
- `routers/ai.py`：`/ai/english`、`/ai/ocr`、`/ai/analyze`、`/ai/sense`、`_auto_subject_ids`。
- `services/vocab_service.py`：`kind` 等。
- `models/tables.py` + `database.py`：DDL、迁移门控 v5、备份。
- 其它 services：`mistake / review / knowledge / formula / stats / answer`；routers：`mistakes / reviews / knowledge / formulas / vocab / subjects / stats / transfer / ai / system`。

前端（`frontend/src/`）：
- `components/EnglishAnalysisPanel.vue`：整篇精读（核心）。
- `views/CaptureView.vue`：多图 / 粘贴目标 / 自动检测。
- `components/MistakeCard.vue`：列表首图；`components/DetailMeta.vue` + `ui/QuestionImages.vue`：详情全图 / 首图。
- `utils/markdown.js` + `components/RichText.vue`：Markdown 表格 / hex-dump。
- `ui/UiModal.vue`：加宽弹窗；设计系统「墨纸印」：`src/ui/`。

## 7. 功能备忘（改功能时留意）
- **错题库**：题型按科目感知（数学 / 408：选择·填空·解答；政治：单选·多选·分析；英语：客观题·翻译·作文）；筛选 / 排序 / 分页 / 批量操作 / URL 同步筛选状态 / 导入导出 JSON。
- **今日复习**：间隔重复 1 / 3 / 7 / 15 / 30 天；选择 / 多选（全对判分，顺序无关）/ 填空（别名 + 数值容差）/ 翻译（对照参考译文自评）/ 解答（AI 按步骤给分 0-100）；全键盘流（1-4 选答、Enter 下一题、Q/W 标记）。
- **自主练习**：记忆曲线 / 按错误时间 / 随机 / 真题专项，多条件筛选。
- **生词本**（英语）：闪卡快刷（认识→1/2/4/7/15/30/60 天阶梯，模糊→明天，不认识→留在队列）；批量导入词表；掌握度分布。
- **知识点库**：标签同义归一、AI 自动总结、贴图分析、服务端分页。
- **公式背诵**：分类 / 搜索 / 过卡循环背诵模式（没记住排队尾直到全会）。
- **科目指南**：各科复习重点与方法建议（政治 / 英语已预置默认档案，可编辑）。
- **统计**：8 指标卡（数字滚动）、复习热力图（119 天）、7 天趋势、掌握度 / 题型 / 来源分布、薄弱知识点直通练习、科目与二级科目统计。
- **前端体验**：墨纸印设计系统、启动动画、按钮涟漪、复习礼花、命令面板（Ctrl+K 全局搜索）、图片灯箱、深色模式（View Transitions 圆形扩散换肤）。

## 8. openviking 记忆库（已跑通，**勿动坏**）
详见 `docs/NEW_SESSION.md` 的 openviking 段。要点：
- **规范配置**：`~\\.openviking\\ov.conf`（JSON；工作区 `C:\\Users\\Administrator\\.openviking`，记忆库 `pending/vectordb/viking` 都在此），监听 127.0.0.1:1933。
- **embedding**：智谱 `provider=openai`、`api_base=https://open.bigmodel.cn/api/paas/v4`、`model=embedding-3`、`dimension=2048`、`api_key`=app `.env` 的 `AI_VISION_API_KEY`。
- **VLM**（生成式，用于**记忆抽取 + 查询扩展**）：`provider=openai`、`model=deepseek-v4-flash-vision-exp`、`api_base=https://api.deepseek.com/v1`、`api_key`=app `.env` 的 `AI_API_KEY`。缺此块会报 `api_key client option must be set` 导致记忆抽取失败。
- **自启**：启动文件夹唯一条目 `OpenViking自启.vbs`（幂等，先查 1933）→ `D:\\dsh-home\\scripts\\start_openviking.py`；该脚本 `CONF` 必须指向 `C:\\Users\\Administrator\\.openviking\\ov.conf`。
- **已弃用，勿再使用**：`start-server.cmd`、启动文件夹里 `openviking-server.cmd`、`D:\\dsh-home\\openviking\\ov.conf`（指向 D 盘另一工作区）。

## 9. 当前状态（2026-09-06）
- git HEAD = `0ccb8d9` 之后的「质量保持+全面修复」提交（见 git log 最新一条）。
- 后端 8000 运行中；前端 `frontend/dist` 已构建；41 个测试全绿。
- 2026-09-06 修复三处 d20d838 重构遗留：①`_vision_extract_text`/`ocr_image`/`analyze_english` 支持 `model/base_url/api_key` 通道透传（此前写死 DeepSeek，GLM/Agnes 回退失效）；②`/ai/english` 带图时按通道逐个回退；③英语整篇链内逐步扣减超时预算（防串行多次调用叠加超 300s）；④`test_regressions` 3 个用例同步新契约。
- 2026-09-06 第二轮（质量保持+全面修复）：⑤英语整篇改为**并行波次**（词汇‖题目清单、逐题并发，prompt/max_tokens 与串行一致，**质量不降只省墙钟**，超时兜底仅极端情况触发）；⑥`/api/mistakes` 列表瘦身（`LIST_COLUMNS` 排除英语大 JSON 字段，详情/编辑/复习仍 `SELECT *` 全量，`mistake_to_dict` 缺列不再补空键）；⑦新增 `test_export_import_round_trip`（41 测试）；⑧前端上传图片压缩 `utils/image.js`（长边 2000px，PNG 保持无损）+ 多图上限 5 张前端拦截；⑨`vocab_service` 弃用 `utcnow` 改时区感知；⑩`markdown.js` 链接/图片协议白名单（堵 `javascript:`）；⑪`docs/analysis-2026-08-14.md` 加归档标注（旧系统报告，勿据此改代码）。
- openviking 已修复并验证正常（2026-09-06 复核：1933 监听、`embedding.dense`=智谱 embedding-3/2048/key 已配置、`vlm`=DeepSeek VLM/key 已配置、`OpenViking自启.vbs` 唯一条目、脚本 CONF 指向 `C:\Users\Administrator\.openviking\ov.conf`；弃用条目均已 `.disabled`）。
