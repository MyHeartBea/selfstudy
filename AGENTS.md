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
- `styles/tokens.css` + `styles/base.css`：墨韵 2.0 令牌与全局（见 6.5 节）。
- `views/AppLayout.vue` + `ui/AmbientLayer.vue` + `ui/DockNav.vue`：外壳三件套（氛围层/Dock/换肤）。
- `ui/`：基件库（GlassCard/MetricTile/RingProgress/AreaChart/BarRow/Heatmap/Skeleton/StageBadge + 全套表单反馈件）。
- `views/DesignView.vue`：/design 画廊（全组件双主题打磨场，不入导航）。
- `components/EnglishAnalysisPanel.vue`：整篇精读（核心）。
- `views/CaptureView.vue`：多图 / 粘贴目标 / 自动检测 / 分析进度叙事。
- `views/StatsView.vue`：Bento 统计；`views/ReviewView.vue`：复习沉浸舞台。
- `components/MistakeCard.vue`：列表首图；`components/DetailMeta.vue` + `ui/QuestionImages.vue`：详情全图 / 首图。
- `utils/markdown.js` + `components/RichText.vue`：Markdown 表格 / hex-dump。
- `ui/UiModal.vue`：加宽弹窗；设计系统「墨纸印」：`src/ui/`。

## 6.5 前端 v2 架构「墨韵 2.0」（2026-09 重构完成，改前端必读）

设计语言：宣纸 · 松烟墨 · 朱砂印 · 洒金。视觉基准原型 = `D:\temp\km-redesign\ink2-prototype.html`（仓库外，丢失可按本节重建）。

**令牌**（`src/styles/tokens.css`，变量名沿用 v1，全站即时换值）：
- 色彩：`--bg/--surface/--surface-2/--surface-glass/--glass`、`--ink/--ink-2/--ink-3`、`--accent(+soft/ink/ring/grad)`、辅助 `--teal/--gold/--green/--violet/--blue/--red`；
- 氛围层：`--wash1..3/--blob1..3/--aurora-o/--vig/--deco`；海拔：`--shadow-1/2/3`、`--e-glow`；动效：`--spring/--ease`；圆角 `--r-sm..xl`；字阶 `--fs-display 42/h1 32/h2 20/h3 16.5/body 15`；布局 `--content-max 1150px`。深浅主题 = `[data-theme='dark']` 覆盖同名变量。

**四条硬规则**：
1. **骑缝外挂**：徽章/悬浮 chip 放 `GlassCard` 的 `#badge` 插槽（外层包裹 overflow:visible）；卡片自身 overflow:hidden 只用于流光裁切。新卡片基件必须保持此结构。
2. **文本三通道**：AI 产出文本（题干/选项/答案/解析/翻译/原文）一律走 `MathText`（$..$ KaTeX+转义）或 `RichText`（Markdown 表格/hex-dump），**禁止裸插值**；英语点词逐字 token 化的句子除外。
3. **8pt 网格**：间距/尺寸取 4/8 倍数；chip 高 28px、圆角 999px；长标签一律 ellipsis、表格横向滚动。
4. **双主题审计**：每个页面改动后在 8000 生产上浅/深两主题各截图自查（深色切 `localStorage['km-theme']='dark'`）。全站遵循 `prefers-reduced-motion`。

**外壳**（`views/AppLayout.vue` v4 + `ui/AmbientLayer.vue` + `ui/DockNav.vue`）：
- 氛围层：底纱/旋转极光/视差光斑（单 rAF 循环）/呼吸墨渍/远山/墨字水印/纸纹噪点/暗角/浮尘/鼠标柔光，纯展示 fixed 层；
- 顶部悬浮玻璃 Dock：滑动 pill（`.dock-ind`）、悬浮标签（data-label+::after）、复习进度环、后端健康点；窄屏 ≤1100px 切换紧凑顶栏+抽屉；
- 换肤「墨漫纸面」：rAF+clip-path 圆形扩散（`theme-veil`，防重入锁 themeBusy），**不要改回 View Transitions**（用户浏览器实测有半途跳变 bug）；
- 开场编排：字体就绪（`document.fonts.ready`，700ms 兜底）后 `body.app-ready` 触发「氛围显影→Dock 落下→页面级联」。

**ui/ 基件一览**（全部零依赖，API 与 v1 兼容）：
- `UiButton`（variant=primary|ghost|outline|danger|success|subtle；primary=印章渐变+涟漪）、`UiModal`（玻璃+渐变描边，zIndex 可叠）、`UiTabs/UiSelect/UiDropdown/UiCheckbox/UiPagination/UiProgress/UiStars/UiTag/UiEmpty/ToastHost/ConfirmHost/CommandPalette/Icon(icons.js 内联 SVG)`；
- v2 新增：`GlassCard`（渐变描边玻璃+流光，#badge 骑缝）、`MetricTile`（tone=accent|teal|gold|green|violet|blue，#spark 插槽）、`RingProgress`（渐变环+生长动画）、`AreaChart`（手写 SVG 面积图，颜色传 `var(--xxx)` 自动跟主题）、`BarRow`、`Heatmap`（data=[{date,count}]，级联入场）、`Skeleton`（variant=text|rect|circle）、`StageBadge`（骑缝徽章，top:-15px）。
- ⚠️ scoped CSS 教训：`:global(A) B` 会被错编译成「把 B 的样式套到 A」（Phase 1 曾把 Dock 的 transform 套到 body 导致整页左移）；组合选择器要写 `:global(A B)`。
- ⚠️ 路由过渡必须带显式 `:duration`（AppLayout 已配）：后台标签页 transitionend 被浏览器推迟，否则切路由卡死白屏。

**门面页**：`StatsView`=Bento 网格（英雄卡+进度环+速览条+AreaChart+Heatmap+薄弱点直通）；`ReviewView`=沉浸舞台（流光进度线+StageBadge+玻璃题卡+落章完成页）；生词闪卡=真 3D 翻面（preserve-3d 双面卡）；公式背诵=翻卡 reveal 动效。四题型作答/全键盘流/判分反馈链（脉冲/抖动）逻辑层未动。

**字体**：`@fontsource/noto-serif-sc` 本地子集（按 unicode-range 分片按需加载，约 411 片 woff2），`main.js` 引 500/600/700/900 四字重；**已移除 Google Fonts CDN**。更新字体 = `npm update @fontsource/noto-serif-sc`。`/design` 画廊页（不入导航）是全组件双主题打磨场，改基件先在画廊验证。

**PowerShell 教训**：改含中文的文件**禁止** `Get-Content | Set-Content`（GBK/UTF-8 双重编码会把 `</title>` 等吃掉导致整页空白——Phase 6 实际翻过车）；一律用 Edit 工具或 `[System.IO.File]::ReadAllText/WriteAllText` 显式 UTF-8 无 BOM。

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
- **前端「墨韵 2.0」全面重构已完成**（7 个 Phase，commits：`2c1e52b` 地基→`5b47665` 外壳→`7f7331f` 基件库→`a7b16c7` 门面两页→`96619bc` 列表+录入→`d6b08b5` 生词/公式→`1458fdc` 全局审计）。架构与硬规则见第 6.5 节；视觉基准原型在 `D:\temp\km-redesign\ink2-prototype.html`。
- 后端契约零改动：41 个测试全绿；路由与 API 完全未动；零新增 npm 依赖（图表手写 SVG、字体走 @fontsource 包）。
- 真实验收已过：完整录入链路（粘贴文本→AI 解析→表单→保存→列表可见）、复习答题流（对/错/多选空态）、键盘流、换肤连点 10 次、窄屏 860px 抽屉、Ctrl+K、生词 3D 闪卡；10 路由深浅双主题巡检通过。
- 此前状态（AI 链路修复等）见 git log `9e4d887` 及更早；openviking 正常（见第 8 节）。
