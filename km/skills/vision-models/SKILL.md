---
name: vision-models
description: Use the user's three vision model APIs (GLM-4.6V-Flash, Agnes-2.0-Flash, Agnes-2.5-Flash) for image recognition in any project. Use when a task needs to analyze an image, screenshot, OCR, or photo and the user has configured these APIs in km/backend/.env.
---

# 三视觉模型调用（Codex 全局复用）

## 说明

Codex 自身的推理内核不能直接替换成第三方视觉模型；本 Skill 让 Codex 通过工具脚本调用用户配置的三个视觉模型 API，用于识图、截图 OCR、图片内容提取等任务。

- 模型通道：GLM-4.6V-Flash → Agnes-2.0-Flash → Agnes-2.5-Flash（并发竞争，首个成功返回）。
- API 配置来源：`km/backend/.env` 中的 `AI_VISION_*` 变量，或同名环境变量。
- 视觉模型只负责识图/提取，不做解题推理；解题交给 DeepSeek 或文本模型。

## 调用方式

```powershell
python C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\scripts\vision_request.py --image "图片路径" --json
```

可选参数：

- `--prompt "自定义提示"`：改变识别要求。
- `--json`：输出 `{"ok": true, "provider": "...", "text": "..."}`。
- `--timeout 30`：单通道超时秒数。
- `--total-timeout 90`：整体超时秒数。

## 纪律

- 不在聊天或文件中输出 `AI_VISION_*_API_KEY`。
- 图片分析优先调用本脚本，不要只依赖本地 OCR。
- 识别结果只作草稿；涉及题目、答案、公式时必须人工复核。
