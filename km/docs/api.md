# API 说明

所有接口前缀为 `/api`，统一响应格式：

```json
{"code": 200, "data": ..., "message": "success"}
```

错误时 `code` 为对应 HTTP 状态码，`data` 为 `null`。

## 错题

- `GET /api/mistakes`
  - 参数：`subject_id`、`sub_subject_id`、`question_type`、`difficulty`、`tag`、
    `approach`、`search`、`source_type`、`source_year`、`sort`、`page`、`page_size`
  - 不传 `page` 返回错题数组；传 `page` 返回
    `{"items": [...], "total": n, "page": p, "page_size": s}`
- `GET /api/mistakes/{id}`：错题详情，含 `knowledge_extra` 与 `related_mistakes`
- `GET /api/mistakes/approaches`：已有解题思路列表（表单联想，`limit` 默认 200）
- `GET /api/mistakes/{id}/reviews`：该错题的复习记录（按时间倒序）
- `POST /api/mistakes/{id}/judge`：body 为 `{"user_answer": "..."}`，自动判断
  选择题（比对选项）或填空题（规范化 + 别名 + 数值容差）
- `POST /api/mistakes/{id}/grade`：body 为 `{"user_answer": "..."}`，AI 按过程
  批改解答题，返回分数、错因、标准解答与其他解法
- `POST /api/mistakes`：新建错题，自动补全知识点标签
- `POST /api/mistakes/batch`：批量操作，
  body 为 `{"ids": [1,2], "action": "pause|resume|delete|source_type", "source_type": "...", "source_year": "...", "source_name": "..."}`
- `PUT /api/mistakes/{id}`：更新错题
- `POST /api/mistakes/{id}/pause`：暂停该错题的复习推送
- `POST /api/mistakes/{id}/resume`：恢复该错题的复习推送
- `POST /api/mistakes/{id}/source-type`：快速修改来源分类，
  body 为 `{"source_type": "real_exam|mock|other", "source_year": "2025", "source_name": "李林六套卷(一)"}`
- `DELETE /api/mistakes/{id}`：删除错题

## 知识点

- `GET /api/knowledge`：按 `subject_id`、`sub_subject_id`、`tag` 筛选；
  传 `page`、`page_size` 时返回 `{"items": [...], "total": n, "page": p, "page_size": s}`，
  不传 `page` 时返回完整数组
- `GET /api/knowledge/by-tag?tag=xxx`：按标签精确查询
- `PATCH /api/knowledge/{id}`：更新摘要与科目归属（PATCH 语义，`None` 字段保持不变），
  body 为 `{"summary": "...", "subject_id": 3, "sub_subject_id": 5}`
- `DELETE /api/knowledge/{id}`：删除词条，不影响错题
- `POST /api/knowledge/{id}/auto-summarize`：根据关联错题自动生成知识点总结

## 公式背诵库

- `GET /api/formulas`：按 `category`、`search` 筛选公式条目
- `POST /api/formulas`：新增条目，body 为 `{"category": "...", "title": "...", "content": "..."}`
- `PUT /api/formulas/{id}`：更新条目
- `DELETE /api/formulas/{id}`：删除条目

## 统计与基础数据

- `GET /api/stats`：总错题数、今日新增、题型分布、题目来源分布、
  各科目数量与平均难度、各二级科目数量与平均难度
- `GET /api/subjects`：科目列表
- `GET /api/sub_subjects?subject_id=3`：二级科目列表（数学/408 等均可筛选）

## 导入导出

- `GET /api/export`：导出错题与知识点
- `POST /api/import`：body 为 `{"mistakes": [...]}`，返回成功/失败明细

## 复习

- `GET /api/reviews/today`：今日待复习错题
- `GET /api/reviews/practice`：自主练习队列
  - 参数：`mode=curve|wrong_time|random|real_exam`、`count`、`subject_id`、
    `sub_subject_id`、`question_type`、`difficulty`、`tag`、`search`、
    `source_type`、`source_year`
  - 返回错题并附带 `last_wrong_at`、`days_since_wrong`、`days_since_review`
- `POST /api/mistakes/{id}/review`：body 为 `{"result": true/false, "note": "", "user_answer": ""}`
- `GET /api/reviews/stats`：复习统计、今日/累计正确率、连续复习天数、
  掌握度分布、近 7 天趋势、薄弱知识点、各科目复习情况

## 科目档案

- `GET /api/subjects/{subject_id}/profile`：科目的复习重点与方法建议
- `PATCH /api/subjects/{subject_id}/profile`：更新科目档案（PATCH 语义，`None` 字段保持不变），
  body 为 `{"focus_areas": ["..."], "review_tips": "..."}`

## AI

- `POST /api/ai/analyze`：body 为 `{"text": "题干文本", "instruction": "可选解题要求"}`，
  返回结构化错题
- `POST /api/ai/ocr`：body 为 `{"image_base64": "...", "instruction": "...",
  "reference_image_base64": "..."}`，识别图片题目（三视觉通道轮询，全失败退回本地 OCR）
- `POST /api/knowledge/{id}/auto-summarize`：根据关联错题自动生成知识点总结

AI 接口需要先在 `backend/.env` 中配置 `AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL`。
AI 端点有每分钟限流（默认 30 次，可用 `AI_RATE_LIMIT` 调整）；设置 `API_TOKEN` 后
所有 `/api` 请求需携带 `X-API-Token` 头或 `Authorization: Bearer <token>`。
