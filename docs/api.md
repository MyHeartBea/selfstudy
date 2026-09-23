# API 说明（km-v2）

所有接口前缀为 `/api`，统一响应格式：

```json
{"code": 200, "data": ..., "message": "success"}
```

错误时 `code` 为对应 HTTP 状态码，`data` 为 `null`。

**`data` 的两种信封（约定，新接口按此选）**：

- 有分页的集合 → `{"items": [...], "total": n, "page": p, "page_size": s}`；分页参数名全站统一为
  `page` + `page_size`（essay 档案曾用 `per_page`，已统一）。
- 无分页的全量集合 → **直接是数组**（`/api/subjects`、`/api/formulas`、`/api/papers`、`/api/mocks`、
  `/api/reviews/calendar`…）。数组不是"没做完"，别为了统一把它们再包一层。
- 例外：`GET /api/mistakes` 与 `GET /api/vocab` 在不传 `page` 时退化为纯数组（供导出/脚本一次取全量），
  传了 `page` 才返回对象。前端两种都兼容。

## 系统

- `GET /api/health`：健康检查（status/database/version/time）+ **进程内监控摘要**
  （`metrics`：请求数/错误数/慢请求数/最慢端点/最近错误）+ 当前 `host`/`reviewDailyLimit`
- `GET /api/exam-countdown`：全局考研倒计时印数据 `{date, days, passed}`，纯日期计算**不查库**
  （`EXAM_DATE` 非法时 `days` 为 null，前端整块不渲染）
- `GET /api/sprint/plan`：冲刺计划（按考试日倒推）。回 `{days_left, due_now, never_started,
  reviewed_today, daily_target, quota_note, subjects[], weeks[]}`；口径与今日复习队列一致
  （新题 = `review_count=0 AND next_review_at IS NULL`）。`EXAM_DATE` 非法/已考时只回
  `date_invalid`/`passed` 标志，`daily_target` 为 null，前端降级说明不瞎算。零 AI。
- `GET /api/dashboard`：仪表盘聚合（stats + reviews/stats 一次返回）
- `GET /api/search?q=&limit=5`：**全站统一搜索**（命令面板 Ctrl+K 的后端）。一次问完
  错题 / 知识点 / 公式 / 生词 / 作文，返回
  `{q, limit, total, groups:[{key, label, total, items:[{id, title, subtitle, meta}]}]}`
  - `key` ∈ `mistakes|knowledge|formulas|vocab|essays`（顺序固定，常搜的在前）；**空组不返回**，
    所以前端不需要知道有几种实体
  - `limit` 是**每组**条数（1~20，默认 5），`total` 是各组命中之和（不是返回条数）
  - `items` 只给跳转与预览需要的字段（`title`/`subtitle` 是**以命中位置为中心**截的一段摘要，
    换行折叠成一行），不给整条记录 —— 面板不该拉解析全文
  - `q` 里的 `%` `_` 按**字面量**匹配（`search_service.like_pattern` + `ESCAPE '\'`，全站搜的单一口径）
- `GET /api/system/integrity?limit=200&keep_days=1`：**只读数据体检**（图片文件 <-> 库里引用），
  **这个接口不删任何东西**。返回 `{referenced, files, bytes_total, orphans:[{rel,size,mtime,kind}],
  orphan_total, orphan_bytes, orphan_truncated, protected_recent, missing:[{name,refs}], missing_total,
  unparseable_refs, keep_days, images_dir_exists}`
  - 两类问题分开报：`orphans` = 文件没人引用（内容仍可被 `/images/<name>` 直接访问）、
    `missing` = 记录指向一张不存在的图（页面上是破图）
  - `refs` 是 `["mistakes#12", ...]` 这样的定位串；`kind` ∈ `image|thumb|exam_page`
  - 判定口径与 `scripts/clean_orphan_images.py` **共用** `integrity_service`（见 AGENTS 第 3 节）
- `GET /api/snapshots?limit=20`：数据快照列表（启动备份 + 导入前快照 + 回滚前现场）
  - 每项 `{name, label, size_kb, created_at}`；`label` 是**来源标记**（文件名最后一段），
    `""` = 启动自动备份、`manual` = 手动、`before-import-<条数>`、`before-batch-delete-<条数>`、
    `before-restore` = 某次回滚前的现场。前端按这个翻成人话，别显示成空白
- `POST /api/snapshots?label=manual`：手动打一份快照（批量操作前建议先点）
  - `POST /api/mistakes/batch`（`action=delete`）与 `POST /api/import` 会**自动先打快照**，
    响应里带 `snapshot` 文件名；为 null 表示快照失败（`message` 会明说本次无法一键回滚）
- `POST /api/snapshots/restore`：`{"name", "confirm"}` —— **整库回滚**到某一份快照
  - `confirm` 必须与 `name` 逐字相等，否则 400 且**一个字节都不改**（前端另有一道"手输 RESTORE"）
  - 顺序：验快照可读(`quick_check` + 必须有 `mistakes` 表) -> 给当前现场打 `before-restore`
    （**打不出来就中止**，409）-> 复查目标没被保留份数清理掉 -> 就地 `backup` 覆盖 -> 重套 DDL 与迁移
  - 成功返回 `{name, safety_snapshot, tables_before, tables_after}`，各表行数是"选对没选对"的凭据；
    老快照里没有的表记 `null`（不是 0）
  - **快照只含数据库，不含图片文件**：回滚不会删图，也回不回已删的图（响应 message 与页面都要明说）
  - 失败码：400 文件名不合法 / 404 找不到 / 409 快照不可用、缺反悔点、被保留份数清理

## 错题

- `GET /api/mistakes`
  - 参数：`subject_id`、`sub_subject_id`、`question_type`、`difficulty`（可多值）、`tag`、
    `approach`、`search`、`source_type`、`source_year`、`sort`、`page`、`page_size`
  - 不传 `page` 返回数组；传 `page` 返回 `{"items", "total", "page", "page_size"}`
- `GET /api/mistakes/{id}`：详情（含 knowledge_extra / related_knowledge / related_mistakes / last_grade）
- `GET /api/mistakes/approaches`：已有解题思路联想（limit 默认 200）
- `GET /api/mistakes/{id}/reviews`：该题复习记录（倒序）
- `POST /api/mistakes/{id}/judge`：`{"user_answer"}` 自动判分
  - choice：归一化比对（全半角/大小写）
  - **multi（政治多选）**：提取 A-D 字母排序比对，全对才得分
  - fill：规范化 + 别名 + 数值容差
- `POST /api/mistakes/{id}/grade`：AI 按过程批改解答题（分数/错因/标准解答/其他解法）
- `POST /api/mistakes`：新建（question_type 支持 choice/multi/fill/translation/solution）
- `POST /api/mistakes/batch`：`{"ids", "action": "pause|resume|delete|source_type", ...}`
  删除会连带删掉配图文件；响应 `{"count", "snapshot"}`，`snapshot` 为 null 表示快照失败（`message` 会明说本次无法一键回滚）
- `PUT /api/mistakes/{id}`：全量更新。**例外**：`images` 与 `passage_text / passage_translation / english_*`
  这组"附加内容"键**不带键**时按库里原值保留（显式传 `""` / `[]` 才是清空），见 `mistake_service.ATTACHMENT_KEYS`
- `POST /api/mistakes/{id}/pause|resume|source-type`
- `POST /api/mistakes/{id}/star`：收藏/取消收藏（只影响筛选展示，不参与复习调度）
  - 不传 body 或 `{"starred": null}` = 按当前状态取反；显式 `{"starred": true|false}` 设定
  - 返回 `{id, starred}`；`GET /api/mistakes` 加 `starred=true` 只看收藏
- `DELETE /api/mistakes/{id}`

## 复习

- `GET /api/reviews/today`：今日复习队列，返回**对象**（旧版是纯数组）：
  `{items, dueTotal, returned, dailyLimit, reviewedToday, remaining}`
  - 排序 = 新题优先（`review_count=0` 或 `next_review_at` 为空）→ 其余按"最久没碰过"（`last_reviewed_at` 升序）轮转
  - `dailyLimit` 来自 `REVIEW_DAILY_LIMIT`（默认 50，`0`=不限），是"今天总共做多少"，已减去今日已复习数
  - 查询参数：`limit`（单批上限，默认 50）、`daily_limit`（覆盖配置，`0`=不限）、
    `category=math|cs408|english|politics`（复习分块，不传 = 全部；**每日配额是全局共享的**，
    换块不重置，`remaining` 的语义是"该块积压"）
- `GET /api/reviews/blocks`：四个分块的徽标数据 `[{key, name, due, total}]`
- `GET /api/reviews/practice`：练习队列
  （`mode=curve|wrong_time|random|real_exam|mock` + `count` + `subject_id`/`sub_subject_id`/
  `question_type`/`difficulty`/`tag`/`search`/`source_type`/`source_year`）
  - `mistake_id=<id>`：**单题直练**（详情页「练这道题」），只返回这一题
  - 整卷模考**不走这个接口**：前端 `/review?mode=mock&paper_id=X&duration=分` 直接取
    `GET /api/papers/{id}` 的题目在客户端组卷（只把客观题放进卷面），交卷时逐题
    `POST /api/mistakes/{id}/review` + `POST /api/mocks` 存档
- `GET /api/reviews/stats`：复习统计、正确率、连续天数、掌握度分布、薄弱知识点、7 天趋势
- `GET /api/reviews/calendar?days=140`：按天聚合 `[{day, total, correct}]`（热力图）
- `GET /api/reviews/forecast?days=30`：未来 N 天复习负荷 `{overdue, items:[{day, count}]}`（含今日）。
  边界按**本地日**算，`next_review_at`（UTC ISO 文本）用定宽日期串的范围比较去撞
  `idx_mistakes_next_review_at`（`date(col)` 会退化成整表 SCAN）—— 改动理由与等价性用例见
  `tests/test_index_coverage.py`
- `POST /api/mistakes/{id}/review`：`{"result": bool, "note", "user_answer"}`
  - choice / multi / fill 且 `user_answer` 非空时，**服务端按 `answer_service.judge_letters` / `judge_fill` 重新判分并覆盖 `result`**（前端自己判的那次只用于即时反馈）；
  - 没传 `user_answer`（翻译 / 解答的 Q/W 自评）时尊重前端给的 `result`。
- `GET|PUT /api/reviews/quota`：每日配额的运行时覆盖（存 `app_meta`，**优先于** `.env` 的
  `REVIEW_DAILY_LIMIT`）。PUT `{"daily_limit": 0..1000}`，`0`=今天不限；非法值 400。
  改这里不用重启后端；`GET /api/sprint/plan` 的每日目标同源
- `GET /api/reviews/snooze`：今天的「稍后再看」剩余次数 `{remaining}`（每天 3 次，按本地日计）
- `POST /api/reviews/snooze`：`{"mistake_id"}` 推到明天再看（`next_review_at` = 明天同一时刻）。
  **不写复习记录、不动 mastery/SM-2 计数**；超限 400，题不存在 404

## 生词本（英语）

- `GET /api/vocab`：列表（`search` / `mastery` / `kind=word|phrase` / `sort` / `page` + `page_size`）
- `GET /api/vocab/stats`：总数/今日到期/已掌握/掌握度分布
- `GET /api/vocab/due?limit=30`：到期闪卡队列（低掌握度优先，随机排序）
- `GET /api/vocab/{id}/context`：真题语境回链——在错题 `passage_text` 里按词边界找该词出现位置，
  返回 `[{mistake_id, source_name, source_year, snippet}]`（最多 3 条；零 AI，纯检索）
- `POST /api/vocab`：新增（单词重复则幂等返回已有）
- `POST /api/vocab/import`：`{"lines": ["abandon v. 放弃", ...], "source"}` 批量导入
- `POST /api/vocab/import-english`：`{"items": [{word, meaning, phonetic, example, note}], "source"}`
  —— 英语精读选词批量入本（≤1000 条）。**已有单词只在字段缺失时补齐，不覆盖用户已填内容**
- `PUT|DELETE /api/vocab/{id}`
- `POST /api/vocab/{id}/review`：`{"result": "known|fuzzy|unknown"}`，
  排期 known→1/2/4/7/15/30/60 天阶梯、fuzzy→明天、unknown→留在队列

## 知识点

- `GET /api/knowledge`：subject_id/sub_subject_id/tag 筛选 + 分页
- `GET /api/knowledge/tags?limit=50`：热门标签（按关联错题数，供录入联想）
- `GET /api/knowledge/by-tag?tag=`：精确查询
- `GET /api/knowledge/linked-mistakes?tag=&limit=`：**知识点 ↔ 错题链接**
  - 返回 `{tag_name, matched_by, matched_tags, hit_tags, total, items, stats}`
  - `matched_by`：`tag_name`（知识点名与错题标签同名）/ `related_tags`（用关联标签兜底命中）/ `none`
  - `stats`：`avg_mastery / wrong_total / review_total / due_now / never_reviewed / shown`
- `POST /api/knowledge` / `PATCH|DELETE /api/knowledge/{id}`
- `POST /api/knowledge/{id}/auto-summarize`：AI 总结

## 公式背诵库

- `GET /api/formulas`（category/search）/ `POST /api/formulas`
- `PUT|DELETE /api/formulas/{id}`

## 科目与档案

- `GET /api/subjects`（含 kind: math/english/politics/cs）、`GET /api/sub_subjects`
- `GET|PATCH /api/subjects/{id}/profile`：复习重点与方法建议

## 统计与导入导出

- `GET /api/stats`：总数/今日新增/题型/来源/科目分布
- `GET /api/export` / `POST /api/import`（≤5000 条）
  - 导入响应 `{"created", "duplicates", "failed", "snapshot"}`：**按题干指纹去重**
    （`mistake_service.question_fingerprint` —— 剥掉 HTML 标签/实体、大小写、全部空白与 Markdown 强调符，
    图片只取**张数**参与），`duplicates` 逐条给 `{index, existing_id}`，`message` 里带"重复跳过 N 条"。
    **题干不足 8 字（纯图片题）一律照常入库** —— 判重的假阳性代价是"静默丢题"，比翻倍严重
- `GET /api/export/anki?type=mistakes|vocab`：Anki 可导入的 TSV（正面 TAB 背面 TAB 标签，字段为 HTML，
  带 UTF-8 BOM）；无数据时返回 400 而不是空文件

## 真题库与模考存档

- `GET /api/papers/scan`：扫描 `PAPERS_DIR` 返回候选清单（按 科目/年份 去重合并，每条带 `rel_path`、
  `answer_path`/`answer_kind`、`mixed`（题+答案合卷）、`sources`（该年份涉及的文件与角色）与 `imported` 标记）
- `GET /api/papers?status=|pending|extracting|structuring|done|error`：卷库列表（按年份倒序，含
  `question_count` 与 `answered_count`）
- `POST /api/papers`：`{"subject","year","title","source_path","answer_path"}` 登记并启动后台拆题。
  **两个路径都必须是 `PAPERS_DIR` 内的相对路径**（绝对路径 / `..` / 越界一律 400）；
  同 `(source_path, year)` 已登记则幂等返回已有记录，不重复导入
- `GET /api/papers/{id}`：试卷信息 + 全部题目（含 `page_idx` / `diagram_image` 题图）
- `DELETE /api/papers/{id}`
- `GET /api/mocks?limit=20`：模考成绩存档（`created_at` 倒序）；`POST /api/mocks`：
  `{"exam_year","total","correct","score","duration_min","used_seconds"}`，返回 `{"id"}`

## AI

- `POST /api/ai/analyze`：`{"text", "instruction"}` 文本解析
- `POST /api/ai/ocr`：`{"image_base64", "instruction", "reference_image_base64"}` 三视觉通道**按序**轮询，
  全败退回本地 OCR
  - **降级会在 `message` 里留痕**：`（首选通道 X 失败，已降级）` 拼在"视觉模型识别完成"后
    —— 首选通道挂掉时识别**照样成功**，只是更慢更抖，不留痕就只能靠手感察觉。
    **前端 `CaptureView` 按 `message` 里是否含"已降级"决定要不要出黄色提示条**，后端改措辞要同步改那里；
    `POST /api/ai/english` 同此约定。`POST /api/ai/analyze` 是纯文本通道，没有降级一说。
- `POST /api/ai/knowledge-from-image`：图片生成知识点草稿。支持一次提交**多张图**（知识点截图常分多张）：
  - `{"images": [b64, b64, ...], "instruction"}` —— 按顺序分批（每批 3 张）提文字后合并，**只生成一条草稿**；
  - 兼容旧调用 `{"image_base64": b64}`；`image_base64` 与 `images` 至少给一个（否则 422）。
  - 逐批失败不整体中断，未识别的批次会在文本里标注「未能识别」。

- `POST /api/ai/english`：英语整篇精读（`{"images":[...], "text", "instruction"}`，先提文字再文本分析）
- `GET /api/ai/sense?word=`：点词查义（多词性释义，≤60 字符）
- `POST /api/ai/weekly-report?force=0|1`：近 7 天答错记录聚类成错因的 AI 周报。
  **按天缓存在 `app_meta`**（key=`weekly_report_YYYY-MM-DD`，自动清旧），同一天重复调用直接命中缓存；
  `force=1` 才重新生成

## 英语作文批改

- `POST /api/essays/grade`：`{"kind": "e1_short|e1_long|e2_short|e2_long", "text" | "images"[, "prompt_text", "instruction", "persist": true]}`
  手写稿**逐张**转录后再走文本批改。响应 `data` 除评分体外还带：
  `record_id`（存档成功时）、`persisted`（`persist:true` 时才有）、`persist_error`、`transcript_warning`。
  **存档失败仍是 200**：已花掉的 AI 结果不该被一次 INSERT 带走，前端据 `persisted:false` 提示"未进档案页"。
- `GET /api/essays?kind=&search=&page=&page_size=`：档案列表 `{items,total}`；
  `search` 按题干/正文 LIKE 过滤（命令面板跳回来用 `?search=`）；`GET /api/essays/{id}` 含 `essay_text` + 完整 `result`；
  `DELETE /api/essays/{id}`。

AI 端点需在 `backend/.env` 配置密钥；有每分钟限流（默认 30，**点词查义 `/api/ai/sense` 也在内**）。
设置 `API_TOKEN` 后所有 `/api` **与 `/images/**`（含缩略图）** 都要带 token，来源四选一：
`X-API-Token` 头 / `Authorization: Bearer` / cookie `km_token` / query `?api_token=`。
cookie 与 query 是给 `<img>` 标签用的（发不了自定义头）；前端约定在 localStorage 写
`km-api-token`，axios 拦截器自动带头、启动时同步写 cookie。

- `DELETE /api/mocks/{id}`：删除一条模考存档（记错成绩用；404=没有这条记录）。
