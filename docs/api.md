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
- `GET /api/dashboard`：仪表盘聚合（stats + reviews/stats 一次返回）
- `GET /api/snapshots?limit=20`：数据快照列表（启动备份 + 导入前快照）
- `POST /api/snapshots?label=manual`：手动打一份快照（批量操作前建议先点）
  - `POST /api/mistakes/batch`（`action=delete`）与 `POST /api/import` 会**自动先打快照**，
    响应里带 `snapshot` 文件名；为 null 表示快照失败（`message` 会明说本次无法一键回滚）

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
- `GET /api/reviews/forecast?days=30`：未来 N 天复习负荷 `{overdue, items:[{day, count}]}`（含今日）
- `POST /api/mistakes/{id}/review`：`{"result": bool, "note", "user_answer"}`
  - choice / multi / fill 且 `user_answer` 非空时，**服务端按 `answer_service.judge_letters` / `judge_fill` 重新判分并覆盖 `result`**（前端自己判的那次只用于即时反馈）；
  - 没传 `user_answer`（翻译 / 解答的 Q/W 自评）时尊重前端给的 `result`。

## 生词本（英语）

- `GET /api/vocab`：列表（`search` / `mastery` / `kind=word|phrase` / `sort` / `page` + `page_size`）
- `GET /api/vocab/stats`：总数/今日到期/已掌握/掌握度分布
- `GET /api/vocab/due?limit=30`：到期闪卡队列（低掌握度优先，随机排序）
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
- `GET /api/essays?kind=&page=&page_size=`：档案列表 `{items,total}`；`GET /api/essays/{id}` 含 `essay_text` + 完整 `result`；
  `DELETE /api/essays/{id}`。

AI 端点需在 `backend/.env` 配置密钥；有每分钟限流（默认 30）。设置 `API_TOKEN` 后所有 `/api`
请求需携带 `X-API-Token` 或 `Authorization: Bearer`。
