# API 说明（km-v2）

所有接口前缀为 `/api`，统一响应格式：

```json
{"code": 200, "data": ..., "message": "success"}
```

错误时 `code` 为对应 HTTP 状态码，`data` 为 `null`。

## 系统

- `GET /api/health`：健康检查（status/database/version/time）
- `GET /api/dashboard`：仪表盘聚合（stats + reviews/stats 一次返回）

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
- `PUT /api/mistakes/{id}`：全量更新
- `POST /api/mistakes/{id}/pause|resume|source-type`
- `DELETE /api/mistakes/{id}`

## 复习

- `GET /api/reviews/today`：今日到期错题
- `GET /api/reviews/practice`：练习队列（mode=curve|wrong_time|random|real_exam + count + 筛选）
- `GET /api/reviews/stats`：复习统计、正确率、连续天数、掌握度分布、薄弱知识点、7 天趋势
- `GET /api/reviews/calendar?days=140`：按天聚合 `[{day, total, correct}]`（热力图）
- `POST /api/mistakes/{id}/review`：`{"result": bool, "note", "user_answer"}`

## 生词本（英语）

- `GET /api/vocab`：列表（search/mastery/sort/page）
- `GET /api/vocab/stats`：总数/今日到期/已掌握/掌握度分布
- `GET /api/vocab/due?limit=30`：到期闪卡队列（低掌握度优先，随机排序）
- `POST /api/vocab`：新增（单词重复则幂等返回已有）
- `POST /api/vocab/import`：`{"lines": ["abandon v. 放弃", ...], "source"}` 批量导入
- `PUT|DELETE /api/vocab/{id}`
- `POST /api/vocab/{id}/review`：`{"result": "known|fuzzy|unknown"}`，
  排期 known→1/2/4/7/15/30/60 天阶梯、fuzzy→明天、unknown→留在队列

## 知识点

- `GET /api/knowledge`：subject_id/sub_subject_id/tag 筛选 + 分页
- `GET /api/knowledge/tags?limit=50`：热门标签（按关联错题数，供录入联想）
- `GET /api/knowledge/by-tag?tag=`：精确查询
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

## AI

- `POST /api/ai/analyze`：`{"text", "instruction"}` 文本解析
- `POST /api/ai/ocr`：`{"image_base64", "instruction", "reference_image_base64"}` 三视觉通道轮询，
  全败退回本地 OCR
- `POST /api/ai/knowledge-from-image`：图片生成知识点草稿

AI 端点需在 `backend/.env` 配置密钥；有每分钟限流（默认 30）。设置 `API_TOKEN` 后所有 `/api`
请求需携带 `X-API-Token` 或 `Authorization: Bearer`。
