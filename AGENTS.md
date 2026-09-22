# AGENTS.md — 研错本（考研错题本 km-v2）

> 本文件是仓库级 Agent 指南（ZCode / Codex / Claude 等编码 Agent 均会读取）。
> 作用：无缝接管本系统，并按项目约定构建 / 维护。位置 `D:\km-v2`（**唯一在用系统**，生产端口 8000）。
> **文档分工**：本文件只放**约束与规定**（规矩、红线、架构约定）；"什么时候干了什么"（批次明细、踩坑叙事）一律写 `docs/WORKLOG.md`，新批次完成后在其末尾追加，不要往本文件堆。

## 0. 一句话
单用户考研错题本：错题录入（文本 / 多图截图）、错题库、真题库与整卷模考、复习（SM-2 简化版间隔重复）、生词本（英语单词闪卡）、知识点库、公式背诵、科目指南、统计。
后端 **FastAPI + SQLite（无 ORM）**，前端 **Vue3 + 自建设计系统「墨纸印」（零 UI 框架库）** + KaTeX，Vite 构建。

## 1. 关键位置
- 仓库根 = `D:\km-v2`
- 后端：`backend/`（入口 `backend/main.py`，挂 `frontend/dist`，监听 127.0.0.1:8000）
- 前端：`frontend/`（源码 `src/`，构建产物 `frontend/dist`）
- 数据：`data/kaoyan_mistakes.db`（SQLite；迁移版本门控 v10；启动前自动备份保留 20 份）
- 文档：`docs/`（api.md / architecture.md / NEW_SESSION.md / **WORKLOG.md 工作日志** / notes/）
- 视觉脚本：`scripts/vision_request.py`；图片巡检：`scripts/clean_orphan_images.py`（默认 dry-run，`--apply` 才删）

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
cd backend && python -m unittest discover -s tests -v   # 临时库，不碰真实数据（272 个）
cd frontend && npm test                                  # Vitest 138 个；含 DOM 级交互回归（happy-dom）与全量 SFC 静态扫描（templateBindings.test.js）
cd frontend && npm run test:e2e                          # Playwright 51 个（真 Chrome；自起 vite，/api 全部浏览器层打桩）；workers 已在配置里钉成 2

# 静态检查（CI 会跑；本地 pip install ruff pre-commit / npm i 即可）
cd backend && ruff check app tests && ruff format --check app tests
cd frontend && npx eslint src tests e2e playwright.config.js && npx prettier --check "src/**/*.{js,vue,css}" "tests/**/*.js" "e2e/**/*.js" "playwright.config.js"
pre-commit run --all-files    # ruff / eslint+prettier / 大文件与空白 / 密钥扫描
```

> **E2E 只补单测覆盖不到的盲区**（`frontend/e2e/`，Playwright，配置 `frontend/playwright.config.js`）：
> ①**真命中测试**——卡片整块可点（`.k-hit` 覆盖层被 `z-index:2` 子元素盖住那次事故，
> 单测用 `trigger('click')` 直接派发事件、**绕开命中测试**，所以永远抓不到）；
> ②**真 paste 事件**——智能录入多图暂存（原生 `ClipboardEvent` + `DataTransfer`），并断言
> **解析结果真的渲染出来**（`.ep-bilingual` / 译文），而不只是"请求发出去了"；
> ③**渲染烟测**——11 条主路由在真浏览器渲染且零 console/page 错误（HTTP 200 是假阳性：SPA 空壳也回 200）。
> 本机默认用**系统 Chrome**（`channel: 'chrome'`，不下载几百 MB 浏览器），
> `E2E_CHROME=0` 可切回自带浏览器；CI 单独 job 装官方 chromium。
> 默认端口 **5274**（刻意与开发端口 5174 错开，避免 `reuseExistingServer` 静默复用旧 checkout 的 dev server）。
> 所有 `/api/**` 都在浏览器层打桩（`e2e/fixtures.js` 的 `mockApi`），**不依赖后端、不碰真实数据库**。
> 后端把**视觉通道降级原因**放在响应的 `message` 里，`mockApi` 默认只回 `message:'success'` ——
> 要验这类"只在 message 里留痕"的行为，用 `withMessage(data, message)` 打桩（`e2e/capture.spec.js` 有例）。
> **`workers` 已钉成 2，别改回 `undefined`**：undefined 时 Playwright 取「核数一半」，全部 worker
> 共用一个 vite dev server，冷编译排队会把随机几个用例撑到 `Test timeout of 30000ms exceeded`
> （实测 41 个用例红 3~14 个，单跑或 `--workers=1` 全绿 —— 是并发额度问题，不是用例问题）。
>
> **写 E2E 时踩过的坑（都已写进代码注释，别再犯）**：
> - 路由正则**必须锚定 `^https?://host/api`**，否则会拦掉 `/src/api/request.js` 这个真实前端模块 → 白屏；
> - 打桩数据的**形状必须与真实接口一致**且**字段名要是响应形状**：`/api/knowledge/tags` 是
>   `[{tag,mistake_count}]` 不是 `{items:[...]}`；`/api/ai/english` 返回的是
>   `passage_text/english_sentences/...`（由 `ai_english.normalize_english_parsed` 规整）
>   而**不是** LLM 入参名 `passage/sentences`。写错不会红（前端自己 catch 掉了），
>   结果是"结果渲染"整条链路没人验 —— 这正是本次修掉的头号问题；
> - **否定断言在元素不存在时算通过**（Playwright 的 `not.toHaveText`），必须改成正向断言；
> - **断言同步点要放在"结果已渲染"**，别只 `poll` 请求次数（采样到 1 就放行，迟到的第二次请求看不到）；
> - 用 `expectAllApiStubbed(calls)` 兜住漏打桩（未打桩只回 404 时，axios 只弹 toast、
>   不写 console，`page.on('console')` 也抓不到，烟测会假绿）；
> - 定位隐藏 `input[type=file]` 用 `data-testid`，别按序号/文案（页面上有多个，会静默点错）。

> **CI 与本地不等价，别再被"本地全绿"骗一次**：CI 是 **Python 3.11**（本地 3.12）、
> **没有 `backend/.env`**、依赖只有 `fastapi uvicorn pydantic httpx coverage ruff`
> —— **没有 Pillow / pypdf / pypdfium2 / python-docx / winsdk**，用到它们的地方必须
> 自己 `skipIf`/`try-import` 兜底。要复现 CI：
> `git clone D:\km-v2 <临时目录> && git checkout <sha>`，删掉 `backend/.env`，
> 用 Python 3.11 venv 装上面那串依赖，再跑 `coverage run -m unittest discover -s tests`。
> **翻车过一次**：假渲染页返回 `bytes` 而非 PIL 对象，`bytes.save()` 的 AttributeError
> 被 `_pdf_ocr_pages` 里宽泛的 `except Exception: continue` 静默吞掉，
> 本地（有 Pillow）全绿、CI 报"返回空串"，排查了很久。**给渲染/IO 路径写假件时，
> 先确认返回类型真的是调用方要的对象类型**；遇到"莫名返回空值"优先怀疑被兜底 except 吃掉。

> **质量工具链**：后端 Ruff（`backend/pyproject.toml`，只选 F/B/T201，**刻意不含 I(isort)** ——
> isort 与 `ruff format` 在导入段空行上互不认账，会让 pre-commit 反复震荡）；前端 ESLint 扁平配置 +
> Prettier（`.prettierrc.json`）；钩子脚本在 `scripts/`（`check_secrets.py` / `preflight_check.py` /
> `frontend_lint.mjs`，用 Node 包装避免 Windows 上找不到 `bash`）。
> **改完前端必须跑 `npm run build`**：Vue 模板编译错误只有 build 抓得到（lint 和单测都会放过，
> 曾因此把两处多语句内联 `@click` 改坏）。CI 覆盖率门槛 55%，**按 CI 口径**（`coverage run -m unittest
> discover -s tests`，含 tests 目录）当前约 73%；加 `--source=app` 会是约 59%，两个口径别混着报。

## 3. 提交与数据规范（务必遵守）
- 每次完成代码 / 数据 / 文档修改并**验证通过**后：`git add -A && git commit -m "简短说明" && git push`
  - `origin = https://github.com/MyHeartBea/selfstudy.git`，分支 `main`，Git Credential Manager 已登录。
  - 若 push 报代理（`127.0.0.1:7897`）不可达：`git -c http.proxy= -c https.proxy= push -u origin main`（本机直连 github 是通的）。
  - 若报 `could not read Username for 'https://github.com'`：**别改 git config**，加 `-c credential.helper=manager` 即可
    （`GCM_INTERACTIVE=never git -c credential.helper=manager push origin main`）。原因：本机 git 被装在
    `~\.qoder-cn\bin\git\`，它找不到自己的 system config，于是 `~\.gitconfig` 里只剩
    `credential.helperselector.selected=manager` 而**没有 `credential.helper=manager` 那一行**，helper 根本没被注册。
- `.env`、数据库、`node_modules`、`dist`、日志一律**不入库**。
- **数据路径禁止静默失败**（出错照样 200、页面照样渲染、只有数据悄悄变坏的一律算 bug）：
  - 快照 / 备份失败不许继续宣称"可回滚"——`snapshot_database()` 返回 None 时写 ERROR 日志，调用方把降级写进响应 `message`（批量删除 / 导入已接，前端 `useBulkActions` **必须把这条 message 渲染成 warning toast**，写死"批量操作完成"就等于把降级藏起来）；
- **整库回滚只有一个入口：`database.restore_snapshot()`**（`POST /api/snapshots/restore` + `/snapshots` 页）。
  四条不可移动的桩：① 只接受 `SNAPSHOT_NAME_RE` 且解析后仍在 `BACKUP_DIR` 内的文件名；② 覆盖前必须先给当前现场
  打 `before-restore`，**打不出来就中止**（没有反悔点不动手）；③ 打反悔点会按 `MAX_BACKUPS` 清最旧一份，所以清完
  必须**复查目标还在** —— 少了这一步，`sqlite3.connect()` 会凭空建一个空库并把当前数据覆盖成空白；
  ④ 覆盖后重跑 `TABLES_DDL` + `migrate_database()`，否则回到 v8 那份会让 `/papers` 打到 500。
  验快照用的连接句柄**要在打反悔点之前关掉**（Windows 上打开的文件删不掉，会报成"反悔点失败"这种误导结论）。
  回滚**不含图片文件**，页面和响应都要明说。
  - 已花掉 AI 调用的结果不许因为一次 INSERT 失败变成 500——`/api/essays/grade` 返回 200 + `persisted:false` + `persist_error`，前端 toast 明说"未存档"；
  - 删行必须连带删文件：`batch_mistakes(action='delete')` 先取回 `images` 再删，事后 `remove_image_files()`。巡检跑 `python scripts/clean_orphan_images.py`（默认 dry-run；孤儿文件的内容仍能通过 `/images/<name>` 访问，这是隐私问题不是磁盘问题）。
- **PUT /api/mistakes 的"附加内容"键有特殊语义**：`images` 与 `passage_text / passage_translation / english_*`（见 `mistake_service.ATTACHMENT_KEYS`）**压根不带键**时服务层按库里原值回填，显式提交 `""` / `[]` 才是清空——这几列是 AI 整篇精读的唯一副本，被一个只含基础字段的表单覆盖就再也生成不回来。Pydantic 侧靠 `body.model_fields_set` 区分，新增字段时要一起维护那张名单。
- **全站"按关键词 LIKE"只有一个口径：`search_service.like_pattern()` + `ESCAPE '\'`**：`%`/`_` 是用户
  内容而不是查询语法（搜 `50%` 命中一切含 5 的东西就是静默给错数据）。新增可搜字段要复用它，别自己
  拼 `f"%{q}%"`；跨实体搜索也只改 `search_service.search_all`（响应形状已按"分组 + 每组 total"钉好）。
  命令面板的作用域 chips 是**对已取回的结果做本地过滤**（`commandPalette.visibleItems/visibleSections`
  里按 `scope` 挑组，不重新请求），所以"某组一条都没展示"只能是**这一组真的 0 命中**；
  新增过滤入口要复用这两个函数，别在组件里自己 `groups.filter(...)`（键盘 `activeIndex` 走的是
  **摊平后的一维下标**，两边各滤一次就会指错行）。
- **图片引用判定只有一个口径：`integrity_service`**（`GET /api/system/integrity` 与
  `scripts/clean_orphan_images.py` 都 import 它，脚本不再自带一套规则）。**库里新增带图片的列必须登记进
  `IMAGE_REF_SOURCES`**，否则那些图会被判成孤儿、`--apply` 就真删掉（真题图示题当初就是这么差点被误删）。
  按 **basename** 归并引用（错题存 `images/x.png`、真题存 `/images/exam_papers/1/p0.webp`，前缀不一样）。
  体检页与端点**只读**，删除永远要显式 `--apply`，且自动备份**不含图片目录**（删了找不回来）。
- **导入判重宁可漏判不可误判**：`mistake_service.question_fingerprint()` 归一后不足 8 字（纯图片题）
  **返回空串 = 不判重、照常入库**。误判的代价是"导入时静默丢题"，比"重复导入翻倍"严重；新增去重时
  保留这条返回空串的语义，并在响应里回 `duplicates:[{index, existing_id}]` + `message` 说明跳过几条。
- **索引归 `TABLES_DDL` 管，`migrate_database()` 里不许写 `CREATE/DROP INDEX`**：`init_database()` 每次启动都
  `executescript(TABLES_DDL)`，而 `migrate_database()` 在它**之后**跑 —— 同一处留两份 DDL，后跑的会把
  前面刚 `DROP` 的旧索引又建回来（v11 换 `essay_records(kind)`→`(kind,id DESC)` 时真踩了）。索引是幂等 DDL，
  **不需要**动 `MIGRATION_VERSION`（那个门控只管一次性全表扫描）。加索引要按**真实 SQL 形状**加并在
  `tests/test_index_coverage.py` 里用 `EXPLAIN QUERY PLAN` 验：只断言"索引名字存在"抓不到列序写反，
  而断言计划时**表里必须灌够量**（几百行 + `ANALYZE`），1~3 行时 SQLite 会诚实地选 SCAN。
  反例备查：`mistake_tag_map` 不缺索引——`(mistake_id, tag)` 主键就是 `WHERE mistake_id=?` 的 best index。
- **字母题判分以服务端为唯一口径**：`answer_service.judge_letters()`（取 A-D、去重、排序后整体相等），`review_mistake` 在 `user_answer` 非空时用它覆盖前端传来的 `result`。前端 `utils/examScoring.js::scoreLetters` 只为即时反馈存在，两边必须跑同一张用例表（`backend/tests/test_data_safety.py::TestScoringSingleSource` 与 `frontend/tests/examScoring.test.js` 各钉一遍）。
- **C 盘空间紧张：所有缓存 / 下载 / 临时文件一律放 D 盘**，C 盘只留程序本体。
  - 临时文件放 `D:\temp`（不要用系统 `%TEMP%`，它已在 C 盘积了几个 GB）。
  - 工具缓存放 `D:\caches\`，已配好的：pip（`pip.ini` 的 `global.cache-dir=D:\caches\pip`）、npm（已在 `D:\temp\npm-cache`）、impeccable skill 引擎（用户环境变量 `IMPECCABLE_HOME=D:\caches\impeccable`）、Playwright 浏览器（`PLAYWRIGHT_BROWSERS_PATH=D:\caches\ms-playwright`）。
  - 给新工具装东西 / 下载引擎前，**先查它有没有缓存目录配置项**（环境变量或 config），把它指到 D 盘再执行；默认会写 `~` 或 `%LOCALAPPDATA%` 的都要改道。
  - 尚在 C 盘的大头（迁移有风险，动前先问）：`~\.cache\codex-runtimes`（约 1.3GB，Agent CLI 自身运行时）、`~\.cargo`（约 600MB，迁移动 PATH）、系统 `%TEMP%`（约 4GB，只可清旧文件）。
- **密钥不打印**：`backend/.env`、`~\.openviking\ov.conf` 里的任何 key，一律不得输出到对话 / 日志 / 提交。

## 4. AI 配置（backend/.env，不入库）
| 变量 | 值（示意） | 用途 |
|---|---|---|
| `AI_API_KEY` | DeepSeek key | 文本模型 |
| `AI_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek 端点 |
| `AI_MODEL` | `deepseek-flash` | 文本模型名（`deepseek-chat` 已下线） |
| `AI_VISION_MODEL` | `glm-4.6v-flash` | 视觉兜底通道（智谱） |
| `AI_VISION_MODEL_FALLBACK` | `glm-4.6v-flashx` | 智谱视觉兜底 |
| `AI_VISION_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | 智谱视觉端点 |
| `AI_VISION_API_KEY` | 智谱 key | 智谱视觉 / 嵌入 |
| `AI_VISION_DS_MODEL` | `deepseek-flash` | **识图首选通道**（走 `AI_API_KEY`，不占智谱额度） |

> **2026-09-10 模型变更（重要）**：DeepSeek 现在只提供 `deepseek-flash` 与 `deepseek-v4-pro`（`GET /v1/models` 实测）。旧的 `deepseek-chat` 与 `deepseek-v4-flash-vision-exp` **都已下线**——后者曾是识图首选，模型名失效后 DS 通道会**静默失败并偷偷退到智谱**（症状：识图还能用，但更慢/不稳，且日志里只有一行异常）。
> 现在文本与识图统一用 `deepseek-flash`（同一把 `AI_API_KEY`）。实测：单图识图 18s、准确输出 LaTeX（`\sin x\sim x`、`1-\cos x\sim\frac{x^2}{2}`）；文本解析 26s、点词查义 6s；`/api/ai/ocr` 返回结构体里的 `vision_model` 字段会写明实际用的通道，排查识图问题先看它。
> **静默降级现在看得见账了**（2026-09-19 体检第 4 批）：`_chat` 按**通道**（模型 + 端点）把成功/失败/截断/耗时记进 `app/metrics.py`，`GET /api/health` 的 `metrics.ai.by_model` 直接写明每个通道调了几次、错了几次、最后一次错什么；失败通道另外打 WARN，成功响应的 `message` 还会带「（首选通道 X 失败，已降级）」，前端把它渲染成提醒条（见第 5 节第 12 条）。

### 4.1 运行参数（同样在 backend/.env）

| 变量 | 默认 | 用途 |
|---|---|---|
| `HOST` | `127.0.0.1` | 监听地址。改 `0.0.0.0` 可手机/局域网访问，**必须同时设 `API_TOKEN`**（否则同网段任何人可读写全部数据） |
| `PORT` | `8000` | 监听端口 |
| `API_TOKEN` | 空 | 设置后所有 `/api` **与 `/images/**`（含缩略图）** 都要带 token。来源四选一：`X-API-Token` 头 / `Authorization: Bearer` / cookie `km_token` / query `?api_token=`（`<img>` 发不了 header，所以 cookie/query 必须存在；`/images` 静态挂载走 `main.py` 的 `images_token_guard` 中间件，StaticFiles 挂不了依赖）。前端自动配合：localStorage 写入 `km-api-token` 后，axios 请求拦截器带头、boot 时同步写 cookie |
| `AI_RATE_LIMIT` | `30` | AI 端点每分钟限流 |
| `REVIEW_DAILY_LIMIT` | `50` | 每日复习配额（含新题）；`0` = 不限 |
| `SLOW_REQUEST_MS` | `3000` | 超过则日志 WARN，并计入 `/api/health` 的慢请求统计 |
| `PAPERS_DIR` | `D:\km-v2\真题` | 真题库扫描根目录 |
| `EXAM_DATE` | `2026-12-19` | 考研初试日期（统计页倒计时）；非法日期前端静默不显示 |

> 约定：视觉**首选 DeepSeek** `deepseek-v4-flash-vision-exp`（走 `AI_API_KEY` 同一把 DeepSeek key，已在 `GET /v1/models` 确认可用）。当前 `.env` 的 `AI_VISION_MODEL` 为智谱 `glm-4.6v-flash`。改视觉时以 `.env` 实际值为准，并遵循下方「先提文字再分析」。

超时：前端 axios 300s；后端 `AI_TIMEOUT=240`、`AI_OCR_TOTAL_TIMEOUT=290`、`AI_VISION_PRIMARY_TIMEOUT=240`。

## 5. 核心 AI 约定（修改 / 新增 AI 功能时务必遵守）
1. **图片一律「先看图提文字 → 再文本分析」**：`_vision_extract_text`（快、稳）→ `analyze_english` / `_analyze_standard_content`（文本）。**禁止单次超大视觉生成**（会 300s 超时 / 空返回）。单图 / 多图 / 带参考图都自动检测语言：英语 → 精读；数学 / 408 → 标准。
   **提不到文字就必须报错，不许继续分析**：`source_text` 为空时继续走 `_chat_json`，模型会凭空编一道题再编一份看着合理的解析（内容不减约定整条落空，且用户无从察觉）。`ai_english.analyze_english` 是第一道闸，`_analyze_standard_content` 是第二道闸。
2. **内容不能减少**：
   - 英语整篇 = 原文**左右对照** + 全文翻译 + 逐句拆解（结构 + 句型）+ 重点短语 + 生词 + **多题解析**。
   - 数学 / 408 = 「懂一题会三题」+「先讲透考点（当作读者不会）」+ 1.1 / 1.2 分步详细。
   - 英语解析**不用** 1.1/1.2，用【定位 / 来源 / 思路 / 总结】；【定位】必须点名具体句并引用关键词。
3. **自动识别科目 / 二级科目**：解析输出 `subject_hint`（数学 / 英语 / 408 / 政治），后端 `_auto_subject_ids` 映射填 `subject_id` / `sub_subject_id`（英语→阅读理解，数学→高等数学，408→计算机网络，政治→马原）。
4. **超大 JSON 健壮性**：`_extract_json` 自动修复「未转义反斜杠 / 缺失逗号 / 尾逗号 / 空内容」；`_chat_json` 对空 / 畸形**重试 3 次**、并按下面的推理预算给足 `max_tokens`；连接级错误重试。
   - ⚠️ **`deepseek-flash` 是推理模型**：它先产出 `reasoning_content` 再产出正文。若 `max_tokens` 只按"正文长度"估算，预算会被推理吃光 → `finish_reason=length` 且 `content` 为空（实测拆题调用 12000 预算里有 11998 是 `reasoning_tokens`、正文 0 字，导致整份试卷导入失败并报出误导性的"AI 返回内容为空"）。
   - 处理方式：`_json_chat_budget()` 给首轮加 1.5 倍余量；`_chat_json` 识别 `finish_reason=length` 后**翻倍预算重试**（上限 `MAX_TOKENS_CEILING`）。`_chat(..., with_meta=True)` 返回 `(content, meta)`，`meta` 含 `finish_reason` / `reasoning_tokens`，排查空返回先看它。
   - 新增 AI 调用时**不要**把 `max_tokens` 当成"正文长度"来设。
   - **机械性任务必须关推理（`thinking=False`）**：`_chat(..., thinking=False)` 会下发
     `thinking: {"type": "disabled"}`（该端点实测支持）并**同时取消 1.5 倍推理余量**
     （没有推理就不该按更大的上限定预算）。适用：**照抄转录 / 按固定 schema 抽取**——
     典型的四步是识图提字、题目清单、词汇短语抽提、（可选）逐题抽取；
     **分析类任务保持默认（开推理）**：阅读/翻译/逐句拆解、逐题解析（定位/思路/总结）。
     实测收益（同任务 A/B，项目真实函数）：识图 `14.3s/推理3167/输出3297` →
     `0.9s/推理0/输出131`（**快 16 倍、输出 token 省 25 倍，转录字数还更多**）；
     完整英语精读 `104.8s` → `38.8s`，其中词汇那一步 `83.3s` → `6.0s`——那 83 秒里
     **11514 个推理 token 吃光 12000 预算、正文一个字都没产出**（截断重试），
     所以关推理不只是提速，是修掉一个真实故障。`tests/test_ai_reasoning_budget.py`
     的 `MechanicalThinkingOffTest` 把"必须真的下发 disabled"与"不许再乘余量"钉住。
   - **逐题解析（`_qa_task`）实测过"关推理"并**否决**，不要再试**：同一题 A/B
     （`thinking` 开 vs 关，其余完全相同）—— 结构上两者都有【定位/来源/思路/总结】、
     答案都对，但**关推理那版在【定位】里引用了一句原文里根本不存在的话**
     （"Today, because of technological change, the economic downturn has highlighted
     the threat of machines to human jobs."），【思路】的排除理由也建立在这句编造的原文上。
     解析长度 `730 → 443 字`。**编造原文引用比"变短"严重得多**（学生会以为原文有那句），
     这正是第 5 节"内容不能减少"要防的东西。**判据不能只看"结构齐不齐、答案对不对"**。
   - **前缀缓存是可观测成本指标，别靠猜**：DeepSeek 自动前缀缓存（命中部分约 1/10 价）
     **一直在工作** —— 实测应用真实流程：逐题调用共享的 system prompt 命中量递增
     `128 → 256 → 384`，整体 **合计输入 2812 token、命中 1408（50%）**。
     消息结构"静态放 system、可变放 user"本来就是缓存友好的，**不需要改造**。
     此前的误判来自自己拼的原始 API 测试（不是应用遥测）。
     `/api/health` 的 `ai.by_model` 现在有 `prompt_avg` / `cache_hit_avg` / `cache_hit_pct`
     （`CacheHitMetricsTest` 钉住口径）。**真正的成本大头是输出（推理），不是输入**：
     同一轮实测输入共 2812 token，而两步分析调用就产出 4560 + 3663 = 8223 个推理 token。
5. **英语整篇 = 一条错题**：存一条错题（含 `english_questions` 全部题目，每题带 `wrong` 标记；错的题自动打「答题失误」标签 + 思路前缀）；详情用 `EnglishAnalysisPanel`（readonly）展示整篇；词汇只在智能录入显示，保存后只在生词本。
6. **多图全存**：长题多张截图**全部**保存到 `images`；错题列表卡片**只显示第 1 张**，点进详情显示全部。
7. **表格 / 图**：`RichText` 支持 Markdown 表格 + 十六进制等宽 `hex-dump`；AI 只会识别图不会重绘，正确表格 / 拓扑图看**原图**。
8. **生词本**：`vocab_items` 有 `kind`（word / phrase）+「全部 / 单词 / 短语」筛选 +「词语」标签；点词查义 `/api/ai/sense`；导入 `/vocab/import-english`（去重）。
9. **多图 = 一次分析**：`/ai/knowledge-from-image` 接受 `{images:[...]}`（≥2 张按 3 张一批、按序提文字后合并），**只产出一条知识点草稿**——不要把「粘一张分析一张」改回来。`AiOcrRequest` 的 `image_base64` 与 `images` 至少给一个。
10. **卡片点击**：知识点/公式卡片必须**整卡可点**打开详情。做法是给卡片本体加 `role="button" tabindex="0"` + `@click`（键盘 Enter/Space 同效），卡片内的显式控件（操作按钮、关联标签）各自加 `@click.stop`，装饰元素（色脊/水印）加 `pointer-events:none`。
   **不要用「铺满卡片的透明点击层（.k-hit/.f-hit）」**：一旦卡内子元素为了定位而带上 `position:relative; z-index`，它们就会盖住点击层，导致「只有某条窄缝可点、点标题/摘要都没反应」（已翻车过一次，用户实测点不动）。
   卡片 hover **不要做 `translateY` 位移**：鼠标停在卡片边缘时上浮会让指针落到卡外，触发 mouseleave→落回→再进入的抖动循环。
   卡片预览要用 `markdownToPlain()` 剥掉 `##`/`**`/表格竖线，详情才走 RichText。
11. **弹窗状态**：`KnowledgeEditModal` 打开时必须重置（新增清空、编辑载入）；监听器（如 Ctrl+V 粘贴）要用 `watchEffect` 按「是否打开」同步挂载，**不要**只在 `false→true` 的 watch 回调里挂——组件若以 `modelValue=true` 挂载会静默失效。多文件读取用 `Promise.all(accepted.map(...))`，**禁止** `for (const f of files) { await read(f) }`（`for...of` 复用绑定会导致只留下最后一张）。
12. **AI 调用只有一个出口，降级不许只留在日志里**：所有 `chat/completions` 请求都必须走 `ai_service._chat`（真正的请求在 `_chat_request`，`_chat` 是它的**记账外壳**）。它按**通道**（模型 + 端点）把成功/失败/截断/耗时/推理 token 记进 `app/metrics.py`，`/api/health` 的 `metrics.ai.by_model` 就是查"识图在偷偷走兜底"的地方——**新增 AI 能力不要再自己发 HTTP**，否则这本账就漏了一块。多通道按序回退时：失败的通道要 ① 打 WARN 日志，② 在**成功**响应的 `message` 里带 `（首选通道 X 失败，已降级）`（统一用 `routers/ai.py::_degrade_note`）；前端 `CaptureView` 靠 message 里的**"已降级"三个字**决定挂不挂提醒条，改措辞必须同步改前端与 `e2e/capture.spec.js`（那两条用例钉的就是"结果照常渲染 + 提醒同时出现"）。
    **一切会离开进程的错误文本先脱敏**：`metrics.mask_secret()`（`/api/health`、前端 toast、`exam_papers.status_note` 都是可读出口；上游 4xx 的响应体会原样进异常，个别网关把 `Authorization` 头回显在报错里）。`AiNotConfigured` 不计通道账（一个请求都没发出去，记进去只会掩盖真问题）；HTTP 200 但**正文为空**按失败计（`deepseek-flash` 推理吃光预算的可见症状）。

## 6. 关键文件
后端（`backend/app/`）：
- `services/ai_service.py`：英语 / 标准分析、OCR→文本、JSON 修复、自动科目。
- `routers/ai.py`：`/ai/english`、`/ai/ocr`、`/ai/analyze`、`/ai/sense`、`_auto_subject_ids`。
- `services/vocab_service.py`：`kind` 等。
- `models/tables.py` + `database.py`：DDL、迁移门控 v8、备份。
- 其它 services：`mistake / review / knowledge / formula / stats / answer / exam_paper`；routers：`mistakes / reviews / knowledge / formulas / vocab / subjects / stats / papers / transfer / ai / system`。

前端（`frontend/src/`）：
- `styles/tokens.css` + `styles/base.css`：墨韵 2.0 令牌与全局（见 6.5 节）。
- `views/AppLayout.vue` + `ui/AmbientLayer.vue` + `ui/DockNav.vue`：外壳三件套（氛围层/Dock/换肤）。
- `ui/`：基件库（GlassCard/MetricTile/RingProgress/AreaChart/BarRow/Heatmap/Skeleton/StageBadge + 全套表单反馈件）。
- `views/DesignView.vue`：/design 画廊（全组件双主题打磨场，不入导航）。
- `components/EnglishAnalysisPanel.vue`：整篇精读（核心）。
- `components/KnowledgeEditModal.vue`：知识点新增/编辑（多图暂存 → 一次分析、打开即重置）。
- `views/KnowledgeView.vue`：知识点卡片墙（整卡可点 + 只读详情弹窗）；`views/FormulaView.vue`：公式卡（同样整卡可点）。
- `utils/markdown.js`：`renderMarkdown`（详情排版）与 `markdownToPlain`（卡片纯文本预览）。
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
- **全局考研倒计时印**（`ui/ExamCountdown.vue`，挂在 AppLayout 外壳）：数据取 `GET /api/exam-countdown`（纯日期计算、不查库；外壳只在挂载时取一次 + 10 分钟刷一次）。桌面 = 右上角悬浮印（与正文右边缘对齐，`right: max(16px, calc(50vw - var(--content-max)/2 + 6px))`），窄屏 = `.mobile-bar` 里的紧凑 chip；三档语气 `days<=7` 冲刺（洒金) / `<=30` 紧迫 / 常态；`days` 为 null（日期非法）或 `passed` 时**整块不渲染**。**统计页 hero 里不再有倒计时**（已上移到外壳，别加回去，避免同屏两个）。

**ui/ 基件一览**（全部零依赖，API 与 v1 兼容）：
- `UiButton`（variant=primary|ghost|outline|danger|success|subtle；primary=印章渐变+涟漪）、`UiModal`（玻璃+渐变描边，zIndex 可叠）、`UiTabs/UiSelect/UiDropdown/UiCheckbox/UiPagination/UiProgress/UiStars/UiTag/UiEmpty/ToastHost/ConfirmHost/CommandPalette/Icon(icons.js 内联 SVG)`；
- v2 新增：`GlassCard`（渐变描边玻璃+流光，#badge 骑缝）、`MetricTile`（tone=accent|teal|gold|green|violet|blue，#spark 插槽）、`RingProgress`（渐变环+生长动画）、`AreaChart`（手写 SVG 面积图，颜色传 `var(--xxx)` 自动跟主题）、`BarRow`、`Heatmap`（data=[{date,count}]，级联入场）、`Skeleton`（variant=text|rect|circle）、`StageBadge`（骑缝徽章，top:-15px）、`UiLoadError`（加载失败态，与 `UiEmpty` 成对，见 6.5 硬规则）。
- 墨韵 3.x 新增：`InkRain`（完成页内容文字雨，chars prop，rAF 自停）、`YearRing`（数据年轮，total/wrong props）、`FlipCard`（**共享 3D 翻牌**：flipped prop + @flip 事件；生词闪卡与公式背诵共用。组件只管视觉与点击翻面，键盘归使用方的键盘流，避免双重切换）、`UiEmpty` 支持 `seal` 汉字印章空态。
- ⚠️ scoped CSS 教训：`:global(A) B` 会被错编译成「把 B 的样式套到 A」（Phase 1 曾把 Dock 的 transform 套到 body 导致整页左移）；组合选择器要写 `:global(A B)`。
- ⚠️ **换页动画只有 JS 一条路径**：`AppLayout.playPageEnter()` 用 rAF 写内联 `transform/opacity`，**没有** Vue `<Transition>`（连续四版实测不可靠，已放弃）。因此**绝不能再给 `.page` 或页面根节点加 CSS `animation`**：CSS 动画在层叠里压过内联样式、且它锁的是整个 `transform` 属性，会把 JS 写的水平位移整段吃掉 —— 「换页没动画/方向反了」连修五次（`4772524`→`c570ed0`）的真因就是这个，`base.css` 里那条 `animation: page-in .36s` 已删。首个路由靠 `watch(route.path, {immediate:true})` 补入场。
- ⚠️ **UI 动效**逐帧用 `requestAnimationFrame` + `performance.now()`（定时器不吃帧时钟，后台标签页会被推迟到动画早该结束后才补帧），`whenContentReady`/翻页/氛围层都按此收敛并带 `cancelAnimationFrame`。
- ⚠️ **但"时间线状态机"不许只靠 rAF**（`BootCalibration.runAnim` 翻过车）：无头环境与后台标签页里合成器不排帧，纯 rAF 的 await 永不返回 → 开机遮罩卡在 `spin` 阶段、`pointer-events:auto` 压住整页，且 `body.ready` 不会加上（表现为页面级联也不触发）。凡是**驱动流程推进**（不是纯装饰）的动画都要「wall-clock + setInterval 兜底」双驱动；`requestAnimationFrame(fn)` 的返回 id 也要赋回变量，否则下一轮的 `cancelAnimationFrame(0)` 是空操作，旧循环与新循环会同时写同一个 `transform`。
- ⚠️ 氛围层（`AmbientLayer`）的 rAF 循环必须①`visibilitychange` 时停、②鼠标追平（<0.4px）后自行收尾，靠 `mousemove` 再唤醒；否则整页每帧空转写 4 个 `style`。

**动效词汇表（`tokens.css`，新代码必须引用而不是手写数值）**：
- 时长档位 `--dur-1 120ms`（微反馈：按下/变色/离场）· `--dur-2 200ms`（hover、遮罩淡入）· `--dur-3 320ms`（面板/内容入场）· `--dur-4 460ms`（换页、卡片入场）· `--dur-5 720ms`（大段揭示）；
- 交错 `--stagger-1 45ms`（卡片墙）· `--stagger-2 70ms`（少量条目）· `--stagger-3 110ms`（分系列/分块揭示）；
- 缓动按**语义角色**取用而非一条走天下：`--ease-enter`（= 原 `--ease`）· `--ease-exit`（离场，先慢后快）· `--ease-move`（位移与尺寸同步）· `--ease-spring`（= 原 `--spring`，强调回弹）。`--ease`/`--spring` 保留为别名，老代码不动。
- **进场与离场必须分开配**：以前 `<Transition>` 的 enter/leave 共用一条 `transition`，关窗/收菜单也走完整个弹簧，鼠标已移开菜单还在飘。
- 交错间隔写在 CSS 里而非 JS 拼数字：`--enter-delay: calc(<序号> * var(--stagger-1))`（`MistakeCard`/`Knowledge`/`Formula`/`Vocab` 已统一为 45ms，`Practice`/`Subject` 为 70ms）。

**开场时间线（三条链已合流，不要再各走各的）**：内联 splash（`main.js` 收，最短 950ms）→ `BootCalibration` 四相放完时给 `body` 加 `.ready` 并 `emit('done')` → `App.onBootDone()` 广播 `km:boot-done` → `AppLayout` 才加 `body.app-ready`（Dock 落下 / 氛围显影的**唯一**开关）。`app-ready` 同时等字体就绪：字体 CSS 是异步 chunk，`main.js` 把它的 promise 挂在 `window.__kmFontsReady`，AppLayout 必须**串在它后面**再读 `document.fonts.ready`，否则 ready 会在字形还没开始下载时就兑现（表现为揭示瞬间是兜底字体）。看门狗一律 4500ms，刻意放在 BootCalibration 自身 4200ms 之后，不抢它的收尾。
- **字体不在关键 CSS 里**：`main.js` 用 `import('./styles/fonts.js')` 动态引入 4 个字重（404 条 `@font-face` = 486KB）。它们曾被 Vite 合进 render-blocking 的 `index-*.css`，首屏要先解析完才画得出启动屏。实测：阻塞 CSS 528.6KB→54.7KB（gzip 12.1KB），`renderBlockingStatus` 由 `blocking` 变 `non-blocking`。`vite.config.js` 另设 `assetsInlineLimit` 对 **所有字体格式**（woff / woff2 / ttf / otf / eot）返回 0（禁止内联成 base64，那等于把用不上的字形包一起下载）。这里曾只挡了 woff/woff2，KaTeX 的 20 个 `.ttf` 照样被内联，`katex-*.css` 涨到 **709KB**（源文件才 23.8KB）；修好后现代浏览器一个 ttf 请求都不会发（woff2 命中）。改构建配置后要用 `ls -la dist/assets/katex-*.css` 复验一次。
- **分包**：`manualChunks` 按 `katex` / `motion`(gsap+lenis) / `vendor`(vue·router·axios+vue 生态) 切分，入口 chunk 从 219.8KB 降到 62.4KB，并自动产出 `<link rel=modulepreload>`；KaTeX 由 `MathText` 的路由依赖图按需并行加载。
- **`prefers-reduced-motion`**：`base.css` 除压时长外还必须带 `animation-iteration-count: 1 !important`，否则光斑/骨架屏/加载圈会以 0.01ms 的节奏**无限空转**；`useCountUp` 在 `immediate` 路径上也要先看偏好再决定开滚。
- **`will-change` 不许常驻在列表项上**：一屏 20 张卡 = 20 个空转的 GPU 合成层。只在真正需要的那一刻开：`.tilt:hover`、`.reveal-pending:not(.reveal-in)`（`v-reveal` 显现完就关层，因为 `reveal-pending` 类不摘）。同理 `.tilt`/`.reveal-*` 的时长与缓动也已收进令牌，不再是手写的 `cubic-bezier(0.22,0.8,0.36,1)`。
- **`UiModal` 负责焦点与滚动锁**：打开时把焦点放进面板（`tabindex="-1"` + `aria-labelledby`，内容自己抢焦点如 `ConfirmHost` 的输入框则不抢回），Tab/Shift+Tab 圈在面板内，关闭时把焦点还给触发元素。滚动锁是**模块级计数**（普通 `<script>` 块里，`<script setup>` 里的 `let` 是每实例的）—— 弹窗可叠加，各实例各写 `body.overflow=''` 会让关内层解开外层。新增弹窗直接用 `UiModal`，不要在页面里自己锁滚动。
- **「加载失败」和「暂无数据」是两个状态，不许共用一条 `v-else-if="!items.length"`**：失败时数据有没有根本未知，却会掉进空态（拦截器只弹 3 秒 toast），用户以为库是空的。整屏数据集的页面用 `ui/UiLoadError.vue`（`text` + 可选 `hint` + `@retry`，与 `UiEmpty` 同尺寸同语言，只是朱砂色 + 重试按钮）：`MistakeListView` / `KnowledgeView` / `FormulaView` / `VocabView` / `ReviewView` / `PapersView` 已接。加载函数一律 `loading` + `loadError` 两个 ref 配对：开头 `loadError=false`，catch 里置 true。
  - **故意不接的三处**：`StatsView` 十几个面板各自取数，整屏错误态会盖掉已成功的面板；`SubjectView` 每个科目的指南单独兜底（缺指南≠加载失败）；`PracticeView` 的试卷下拉只是模考的一个数据源，失败时留空即可。**轮询型加载（`PapersView.loadPapers`）只在 `!papers.length` 时才报失败**，否则导入流水线每 2.5s 轮一次、一次网络抖动就把已显示的卷库换成错误态。
  - **踩过的坑**：`useMistakeFilters` 早就 return 了 `loadError`，模板也写了 `v-if="loadError"`，但视图的解构里漏了它 —— 错误 UI 永远渲染不出来。用 composable 的返回值前先在解构里核对一遍。
- **用了 `<Icon>` 却没 `import Icon` / 模板里引用了 setup 没导出的变量**：两类 bug **三道关卡全放过** —— `vite build` 不报错（编译成 `_ctx.xxx` 或 `resolveComponent("X")`，运行时只是 undefined）、ESLint 没有对应规则、单测不渲染那条分支就看不见。实际各踩一起（`FormulaView` 背诵完成页图标静默消失、`MistakeListView` 漏解构 `loadError` 导致错误 UI 永不渲染）。**现在由 `tests/templateBindings.test.js` 兜住**：拿 Vue 自己的编译器把 `src/**/*.vue` 全过一遍，断言没有 `_ctx.<标识符>`、没有非内置的 `resolveComponent("<X>")`，并自带"故意引用幽灵变量必须被抓到"的自检。新增全局组件/指令时要去那张内置名单里登记。
- **交互型基件必须键盘可达，只读展示不许带 role/tabindex**：`UiStars` 现在是 `role="radiogroup"` + 每颗星 `role="radio"`，**roving tabindex**（组内只有一个 Tab 落点：选中那颗，未选中则第 1 颗），方向键/Home/End 改分并把焦点跟过去。改之前它是 `role="img"` 的裸 span，录入页**必填项**「难度」对键盘用户完全不可达（`tests/uiStars.test.js` + E2E `keyboard-guard.spec.js` 各兜一半：单测验按键，E2E 验"Tab 真能落进来"——`trigger('keydown')` 直接派发事件，永远抓不到 tabindex 缺失）。同理题干配图 `figure` 补了 `role="button" tabindex="0"` + Enter/Space。体检第 8 批补齐 `UiSelect`（Esc 关/方向键进菜单移动焦点/Delete 清空——清空按钮嵌在 trigger 内部，键盘唯一路径）与 `UiDropdown`（Esc/方向键）；**`UiCheckbox`/`UiPagination` 本就是原生元素，别画蛇添足**。给这类"打开弹层"的基件写单测注意：①组件必须 `attachTo: document.body` 挂载，detached 元素 `.focus()` 不动 `activeElement`；②弹层是 `v-if` 异步渲染，打开后要 `await nextTick()` 才查得到内部元素。
- **全站致命错由 `utils/errorBoundary.js` 兜住**：`main.js` 里 `installWindowGuards()` + `installErrorBoundary(app)`，`app.mount()` 包了 try/catch；组件渲染抛错会收起启动屏并弹原生 `#km-fatal` 面板（role=alert，一次会话只弹一次，留「知道了」）。面板**必须**用原生 DOM 而不是 Vue（走到这里应用本身已经不可信）。新增的全站监听照此成对注册，别在页面里各自 `window.onerror`。资源 404 的 `error` 事件没有 `event.error`，已按此过滤，不要改成 capture 监听把 404 也变成弹窗。
- **模考（`mode=mock`）离开保护**：作答只暂存在内存，`ReviewView` 用 `beforeunload`（管刷新/关页）+ `onBeforeRouteLeave`（管站内导航）两道挽留，且**只在已作答 ≥1 题时**拦人（一题未答没有东西可丢，拦住就是骚扰）。给"未落库的输入"加保护时照这个分工：两条路缺一不可，且要有 dirty 判据。

**门面页**：`StatsView`=Bento 网格（英雄卡+进度环+速览徽章+AreaChart 趋势+复习负荷预报+AI 错因周报+模考成绩趋势+Heatmap+薄弱点直通+科目分析墨条）；`ReviewView`=沉浸舞台（流光进度线+StageBadge+巨型汉字数字背景+玻璃题卡+落章完成页+模考成绩单分支）；生词闪卡=真 3D 翻面（preserve-3d 双面卡）；公式背诵=翻卡 reveal 动效。四题型作答/全键盘流/判分反馈链（脉冲/抖动）逻辑层未动。

**硬规则补充（v2 后续批次踩过的坑）**：
- **backdrop-filter 创建层叠上下文**：玻璃筛选栏（`.list-toolbar`/`.filter-bar`）必须带 `position:relative; z-index:5`，否则内部 UiSelect 下拉会被后渲染的卡片盖住（三处已修；新增玻璃容器 Hosting 下拉时同样要加）；
- **Vue scoped `:global(A) B` 会错编译**（把 B 的样式套到 A 上），组合选择器一律写 `:global(A B)`；
- **后台标签页 transitionend/rAF 会被推迟**：换页由 rAF 自管并有显式收尾（见 6.5「换页动画只有 JS 一条路径」）；换肤遮罩有 1s 看门狗强制收尾；
- **监听器要成对，且解绑的必须是注册的那个**：`ShaderBackdrop` 曾把内层 `resize` 注册进去、却在卸载时移除另一个从未注册的 `resizeHandler`，`pointermove` 则根本没移除——每次挂载净漏两个。`AppLayout` 的 `km:show-shortcuts` 曾是匿名函数、清理块里无从移除（已改具名）。`App.vue` 的 `router.afterEach` 里绑磁吸前**必须先 dispose 上一批**，否则数组无限增长且跨路由留存的元素（Dock）会被叠第二份监听。`onUnmounted` 在同一个组件里声明两次是合法的，但正是这些泄漏躲过 review 的原因；
- **搜索高亮**用 CSS Custom Highlight API（`::highlight(km-search-hit)`，MistakeListView 注册 Range），不改 RichText 的 DOM——KaTeX 安全；
- **改含中文文件禁止 PowerShell Get-Content|Set-Content**（GBK/UTF-8 双重编码会吃掉标签，Phase 6 翻过车），用 Edit 工具或 `[System.IO.File]::ReadAllText/WriteAllText` 显式 UTF-8 无 BOM。

**字体**：`@fontsource/noto-serif-sc` 本地子集（按 unicode-range 分片按需加载，约 411 片 woff2），500/600/700/900 四字重由 `src/styles/fonts.js` 集中引入、`main.js` **动态** import（脱离 render-blocking，见 6.5）；**已移除 Google Fonts CDN**。更新字体 = `npm update @fontsource/noto-serif-sc`。`/design` 画廊页（不入导航）是全组件双主题打磨场，改基件先在画廊验证。

**PowerShell 教训**：改含中文的文件**禁止** `Get-Content | Set-Content`（GBK/UTF-8 双重编码会把 `</title>` 等吃掉导致整页空白——Phase 6 实际翻过车）；一律用 Edit 工具或 `[System.IO.File]::ReadAllText/WriteAllText` 显式 UTF-8 无 BOM。

## 7. 功能备忘（改功能时留意）
- **复习调度 = SM-2 简化版（迁移 v6/v7）**：`mistakes.ease_factor`（2.5 起，答对+0.1 上探封顶 2.8、答错-0.2 下限 1.3）+ `last_interval`（答对=上次间隔×系数四舍五入，首次 1 天，封顶 180；答错重置 1 天）。`INTERVALS` 常量仅迁移回填用。mastery 阶梯保留仅供统计展示。**mock_records 表（v7）**：模考成绩存档（`GET/POST /api/mocks`），统计页画趋势。
- **今日队列 = 新题优先 + 逾期轮转 + 每日配额（`review_service.get_today_queue`）**：旧排序「最旧的 next_review_at 最先」会让 8 月逾期 20 天的题永远霸占前排，新题（`next_review_at` 为空）排最后、之后转好的题再也轮不到（实测 98/99 到期、16 题从未复习）。现在的排序是：① `review_count = 0 OR next_review_at IS NULL`（新题）优先；② 其余按 `COALESCE(last_reviewed_at,'1970…')` 升序 —— 复习一次 `last_reviewed_at` 就刷新，该题自动退到队尾，整个积压被逐日轮过；③ `REVIEW_DAILY_LIMIT`（默认 50，0=不限）是"今天总共做多少"，会减去今日已复习数。
  - ⚠️ **配额必须在 `_expand_passage_items` 展开之后截断**：英语整篇会展开成多道小题，先按行数截断再展开会让实际题量超过配额（实测 50 行 → 59 题）。所以候选行取 `budget*3`（下限 budget+20，上限 300），展开后再 `[:budget]`。
  - **明确不做毕业机制**：题永远不会被移出队列（用户要求以后再说）。答错的题重置 1 天，所以明天仍会出现——这是设计而非 bug。
  - 响应是对象 `{items, dueTotal, returned, dailyLimit, reviewedToday, remaining}`（旧格式是纯数组，前端两种都兼容）。
- **今日复习分块（墨韵 3.5）**：`/api/reviews/today` 支持 `category=math|cs408|english|politics`（不传=全部，向后兼容），`GET /api/reviews/blocks` 返回四块的 `{key,name,due,total}` 汇总。归块在 `review_service.REVIEW_BLOCKS`，按**科目名包含关键词**（数学/408|计算机/英语/政治）匹配 `subjects.name` —— 兼容 数学二/英语二/计算机408 等命名；不入块的科目（杂项）只能走自主练习。**每日配额是全局共享的**（reviewedToday 跨块累计，换块不重置），`remaining` 语义是"该块积压"（dueTotal-本批），不要改成和配额取小。前端默认块=数学（`?block=` 同步 URL），完成页有跨块跳转；E2E 打桩必须含 `/reviews/blocks`，否则冒测假红。
- **真题库扫描（`exam_paper_service.scan_folder`）**：按 `(科目, 年份)` **去重合并**，每条候选带 `sources`（该年份涉及的真题/合卷/答案速查）。角色判定见 `classify_file`：
  - `mixed` = **题+答案合卷**（`真题解析`/`真题及参考答案`）——旧实现把它们当"纯答卷"，导致 150 份候选里 **52 份变成孤儿（既当不成试卷也配不到答案）**；
  - `answer_key` = 答案册（`答案速查`/`参考答案`/`选择题解析`）；`question` = 纯试卷；`other` = 答题卡等（不产生候选）。
  - 判定顺序：`答案速查` → `真题/试题/试卷 + 解析/答案`(=mixed) → `参考答案` → `解析/答案` → `真题/试题/试卷` → other。
  - **年份**：4 位优先，否则识别两位缩写 `26考研→2026`（旧实现 10 份年份为空）。**科目**：数学一/二/三 用全角与半角括号都覆盖的键分开（旧实现把 `2024年数学（一）` 判成数学二），且规则要包含 `数二/数一/数三` 简写（否则 `2011年数二真题答案速查.pdf` 识别为空）。
  - 实测效果：可导入候选 **1 份 → 59 份**、年份空 0 份、答案配 55/59、无重复。
- **知识点 ↔ 错题链接（`GET /api/knowledge/linked-mistakes?tag=`）**：按 `mistake_tag_map` 找该知识点下的错题 + 统计（几题/平均掌握/累计答错/今天到期/从未复习）。知识点名与错题标签只有 83/134 同名，所以支持 **`related_tags` 兜底**：名称没直接命中就用关联标签找，响应里 `matched_by`（tag_name/related_tags/none）标明命中方式、`hit_tags` 是真正挂有错题的标签。前端在知识点详情弹窗底部展示（含逐题「练这题」与「练这些题」）。
  - ⚠️ `knowledge_service` 里**不能顶层** `from app.database import mistake_to_dict`：`database.py` 反过来要 import 本模块的 `canonical_tags`，会循环导入。用局部导入（见 `_mistake_to_dict`）。
- **数据体检页（只读）**：`/integrity`（不进 Dock，命令面板 Ctrl+K「数据体检」可达）显示"没人引用的文件"与
  "记录指向的图不见了"两张清单，**页面上没有任何删除入口**；判定与巡检脚本同源（见第 3 节）。
- **数据备份与回滚页**：`/snapshots`（同样不进 Dock，Ctrl+K「数据备份与回滚」可达）列最近快照
  （时间 / 来源标记翻人话 / 大小），可「立刻备份一次」与**整库回滚到某一份**。回滚要手输 `RESTORE`
  才发请求（服务端另有 `confirm === name` 那道），覆盖前会先留 `before-restore` 反悔点并把
  前后各表条数留在页面上；图片文件不在快照内这句话在确认框、结果卡、页面副标题各出现一次。
  口径与红线见第 3 节"整库回滚只有一个入口"。
- **全站搜索 / 命令面板**：`GET /api/search?q=&limit=`（`search_service`）一次问错题/知识点/公式/生词/作文，
  空组不返回；`Ctrl+K` 面板的作用域 chips 是**对已取回结果做本地过滤**（不重新请求），
  列表一维（键盘）+ 分组渲染（`visibleSections()` 带扁平下标），落地页统一吃 `?search=`、知识点走 `?tag=`。
- **错题库**：题型按科目感知（数学 / 408：选择·填空·解答；政治：单选·多选·分析；英语：客观题·翻译·作文）；筛选 / 排序 / 分页 / 批量操作 / URL 同步筛选状态 / 导入导出 JSON / **Anki TSV 导出（`/api/export/anki?type=mistakes|vocab`）** / 打印（`window.print()` + 全局 print 样式）。列表首图走**缩略图**：`/images/thumb/{name}`（懒生成 WebP 到 `data/images/_thumbs/`，失败回退原图；删除错题同步清缩略图）。
- **今日复习**：间隔重复由 SM-2 驱动；选择 / 多选（全对判分，顺序无关，判分统一走 `utils/examScoring.js` 的 scoreLetters）/ 填空（别名 + 数值容差）/ 翻译（对照参考译文自评）/ 解答（AI 按步骤给分 0-100）；全键盘流（1-4 选答、Enter 下一题、Q/W 标记）；`?` 呼出快捷键速查。**单题直练**：practice 接口支持 `mistake_id` 参数（详情「练这道题」用）。
- **真题模考（mode=mock）**：练习页选年份+时长 → `mode=mock&duration=分钟&source_type=real_exam&source_year=年`；ReviewView mock 分支：倒计时（归零自动交卷）、作答暂存不判分、自由翻题、交卷统一判分（choice/multi 本地、fill 走 /judge）并逐题写入复习记录 + POST /mocks 存档；卷面客户端过滤为客观题。
- **真题库（v8，`/papers` 页）**：扫描 `PAPERS_DIR`（默认 `D:\km-v2\真题`，.env 可覆盖）→ 候选按 科目/年份/答案配对 识别（识别率 100%，配对率 90%+）→ 导入后**单工作线程后台流水线**：提取文本（docx=python-docx；pdf=pypdf 文本层，**空/过少/乱码即回退**：pypdfium2 渲染页为图 → **数学/408 优先 DeepSeek 视觉（输出 LaTeX，公式准）+ 本地 Windows OCR 兜底，文科目反之**；判定可读占比 `PDF_TEXT_RATIO`(0.6)/最小字符 `PDF_TEXT_MIN`(200)/最多页 `PDF_OCR_PAGES`(60) 可调，乱码文本层自动拒绝）→ **扫描/公式卷：扁平分块拆题（完整，避免逐页漏同页多个综合题）+ 按题号在逐页文本定位页码**（`_page_for_no`，可靠，供图示题取原图）；公式/上下标要求 `\(...\)` 包裹（MathText 渲染）→ 从配对答案文件文本匹配客观题答案（英语二实测 20/27 配上）。**表**：`exam_papers`（status: pending/extracting/structuring/done/error + status_note）+ `exam_questions`（含 `page_idx`/`diagram_image`，迁移 v9；**图示题存该页原图**到 `data/images/exam_papers/<pid>/p<n>.webp`，前端模考/详情可见）。**整卷模考**：`/review?mode=mock&paper_id=X&duration=分`——题目来自卷库（仅客观题进卷面），交卷判分后**「作答且错」的题自动入错题本**（subject 按 英语二→英语 等映射匹配；analysis/difficulty_points 有非空兜底文案，否则被必填校验 422），未作答不入本。
- **AI 错因周报**：`POST /api/ai/weekly-report`（force=1 强制重生成）——近 7 天答错记录聚类为错因，**按天缓存于 app_meta（key=weekly_report_YYYY-MM-DD，自动清旧）**；统计页渲染，标签可点击直通练习。
- **生词本**（英语）：闪卡快刷（认识→1/2/4/7/15/30/60 天阶梯，模糊→明天，不认识→留在队列）；批量导入词表；掌握度墨点；掌握度分布。
- **知识点库**：标签同义归一、AI 自动总结、贴图分析、服务端分页；知识笺卡片墙（科目色脊+摘要+关联标签）。
- **公式背诵**：分类 / 搜索 / 过卡循环背诵模式（没记住排队尾直到全会）；分类彩色印章。
- **英语作文批改**（迁移 v10，`essay_records` 表）：录入页第三个 Tab「英语作文批改」→ `POST /api/essays/grade`（手写稿照片**逐张** `_vision_extract_text` 转录后合并，再走文本批改；同样遵守第 5 节"先提文字再分析"，禁止单次超大视觉生成）→ 按考研四型（e1/e2 × 小/大作文）五档评分，`ai_essay.normalize_essay_grade` 钳制分数、按档位兜底 band、四维分和与总分偏差超 1 分时按权重（内容.4/结构.2/语言.3/格式.1）重算。`persist` 默认存档到 `essay_records`，档案页 `/essays`（整卡可点看详情、逐词 diff 用 `utils/essayDiff.js` 的 LCS）。"存入错题库"走普通错题（`question_type=solution`，科目自动匹配「英语」，**匹配不到就拒绝并 toast**，因为 `subject_id` 是必填 int）。
- **科目指南**：各科复习重点与方法建议（政治 / 英语已预置默认档案，可编辑）；首字印章+顶部色条。
- **统计**：Bento 网格——英雄卡（今日待复习+进度环+连续复习火苗章+正确率/掌握度徽章）、瓷砖、今日速览条、SVG 趋势、**复习负荷预报（`/api/reviews/forecast`）**、AI 错因周报、**模考成绩趋势**、热力图、薄弱知识点、题型/来源/科目分析（两张旧表已合并为科目分析墨条；**不再展示二级科目统计**）。
- **前端体验**：墨纸印/墨韵2.0 设计系统、启动动画、按钮涟漪、复习礼花、命令面板（Ctrl+K 全局搜索+快捷动作）、`?` 快捷键速查、图片灯箱、深色模式（墨漫纸面 rAF 圆形扩散换肤，未手动选择时跟随系统）、搜索高亮（Highlight API）、打印样式。

## 8. openviking 记忆库（已跑通，**勿动坏**）
详见 `docs/NEW_SESSION.md` 的 openviking 段。要点：
- **规范配置**：`~\\.openviking\\ov.conf`（JSON；工作区 `C:\\Users\\Administrator\\.openviking`，记忆库 `pending/vectordb/viking` 都在此），监听 127.0.0.1:1933。
- **embedding**：智谱 `provider=openai`、`api_base=https://open.bigmodel.cn/api/paas/v4`、`model=embedding-3`、`dimension=2048`、`api_key`=app `.env` 的 `AI_VISION_API_KEY`。
- **VLM**（生成式，用于**记忆抽取 + 查询扩展**）：`provider=openai`、`model=deepseek-flash`、`api_base=https://api.deepseek.com/v1`、`api_key`=app `.env` 的 `AI_API_KEY`。缺此块会报 `api_key client option must be set` 导致记忆抽取失败。旧的 `deepseek-v4-flash-vision-exp` 已下线。
- **自启脚本已修正**：`D:\dsh-home\scripts\start_openviking.py` 原先把 `CONF` 指向**已弃用**的 `D:\dsh-home\openviking\ov.conf`（那份还残留过期的 vlm 模型名 → 重启后会踩坑）。现已改为 `C:\Users\Administrator\.openviking\ov.conf`，并在启动日志里回显所用配置路径；两份配置的 vlm.model 也已同步为 `deepseek-flash`（两者 workspace 相同，切换不丢数据）。
- **自启**：启动文件夹唯一条目 `OpenViking自启.vbs`（幂等，先查 1933）→ `D:\\dsh-home\\scripts\\start_openviking.py`；该脚本 `CONF` 必须指向 `C:\\Users\\Administrator\\.openviking\\ov.conf`。
- **已弃用，勿再使用**：`start-server.cmd`、启动文件夹里 `openviking-server.cmd`、`D:\\dsh-home\\openviking\\ov.conf`（指向 D 盘另一工作区）。

## 9. 当前状态（快照）
> **历史批次记录（什么时候干了什么、批次明细、踩坑叙事）已迁至 `docs/WORKLOG.md`** —— 本文件只放约束与规定，新批次完成后在 WORKLOG.md 末尾追加一节，不要再往这里堆。

- 后端 8000 运行中（`HOST` 改 `0.0.0.0` 必须**同时设 `API_TOKEN`**，见第 4 节）；前端 dist 已构建；openviking 正常（第 8 节）。
- 数据库迁移已到 **v10**（v6=SM-2 调度 / v7=mock_records / v8=exam_papers / v9=exam_questions.page_idx+diagram_image / v10=essay_records）；启动前自动备份保留 20 份。**v11 只补索引**（见第 3 节"索引归 DDL 管"），`migration_version` 门控**仍是 10**。
- 测试基线：**后端 274、前端 Vitest 138、E2E 51**（workers 已在 `playwright.config.js` 钉成 2，见第 2 节），覆盖率按 CI 口径约 73%（门槛 55%）。
- 已上线：墨韵 3.x 前端（数字文房设计系统，演进史见 WORKLOG）、真题库（扫描 PDF 视觉提取 + 图示题存原图）、SM-2 复习队列、AI 错因周报、Anki 导出、快照备份。
- 视觉基准原型 `D:\temp\km-redesign\ink2-prototype.html`（仓库外）；架构与硬规则见第 6.5 节。
