"""AI 服务层：调用 OpenAI 兼容的 chat/completions 接口。"""

import base64
import json
import re
import time
import urllib.error
import urllib.request
from typing import List

from app.config import settings


class AiNotConfigured(Exception):
    pass


class AiRequestError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.AI_API_KEY or settings.AI_VISION_API_KEY)


def _chat(
    messages: List[dict],
    timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    if not is_configured():
        raise AiNotConfigured()
    url = (base_url or settings.AI_BASE_URL).rstrip("/") + "/chat/completions"
    payload = {
        "model": model or settings.AI_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or settings.AI_API_KEY}",
        },
        method="POST",
    )
    # 直连 AI 服务，绕开环境变量注入的占位代理（例如 http://127.0.0.1:9）。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        last_message = ""
        for attempt in range(3):
            try:
                with opener.open(
                    request,
                    timeout=timeout or settings.AI_TIMEOUT,
                ) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_message = f"AI 服务返回 {exc.code}: {detail[:300]}"
                if exc.code == 429 and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise AiRequestError(last_message) from exc
        else:
            raise AiRequestError(last_message)
    except Exception as exc:
        raise AiRequestError(str(exc)) from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AiRequestError("AI 服务响应格式异常") from exc


def _parse_prompt(standard_tags: List[str] | None = None) -> str:
    prompt = (
        "你是一个考研错题整理助手。请根据用户提供的题目内容，输出严格的 JSON（不要 Markdown），字段如下：\n"
        '{"question": "...", "question_type": "choice/fill/solution", '
        '"option_a": "...", "option_b": "...", "option_c": "...", '
        '"option_d": "...", "correct_answer": "选择题填 A/B/C/D，其他题型填参考答案文本", "analysis": "详细解析", '
        '"difficulty": 1-5 的整数, "difficulty_points": "这道题的主要难点简析", '
        '"knowledge_tags": ["标签1", "标签2"], '
        '"approach": "解题思路", "source": "来源备注", '
        '"source_type": "real_exam/mock/other", '
        '"source_year": "如 2025", "source_name": "如 李林六套卷(一)"}\n'
        "question_type 根据题目形式判断：有 A/B/C/D 选项选 choice，"
        "只要求填数值或结果的选 fill，需要写完整过程或证明的选 solution。"
        "如果某个选项缺失，填空字符串即可；如果无法确定正确答案，"
        "给出最可能的答案并在解析中说明。source_type：真题填 real_exam 并填写年份，"
        "模拟题填 mock 并填写年份和卷名，其他填 other。\n"
        "解析（analysis）必须符合以下风格：\n"
        "1. 先写“思路”：用一两句大白话说明这道题要做什么、用什么方法。\n"
        "2. 再分小步推导：步骤用 1.1、1.2、2.1 编号，每一步只做一个小动作，并写明依据或公式。\n"
        "3. 像给同学讲题一样通俗：遇到“代数重数”“几何重数”“特征子空间”“正交补”等概念，第一次出现时先用一句话解释清楚，再使用。\n"
        "4. 不要堆砌术语或做大段绕口的综合论证，把大结论拆成几个能看懂的小结论逐步推出。\n"
        "5. 解析控制在 200-400 字左右，除非推导确实需要更长。\n"
        "6. 最后单独一行写明“结论：”或“答案：”。\n"
        "7. 数学公式统一用 $...$ 行内、$$...$$ 独立行的 LaTeX 写法。"
    )
    if standard_tags:
        prompt += (
            "\n以下是系统里已有的标准知识点标签，若适用请直接使用，"
            "不要新增近似叫法："
            + "、".join(standard_tags[:40])
        )
    return prompt


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def normalize_parsed(parsed: dict, fallback_text: str = "") -> dict:
    """把 AI 返回的 JSON 规整为前端表单可直接使用的结构。"""
    if not isinstance(parsed, dict):
        parsed = {}

    def as_text(value) -> str:
        return str(value or "").strip()

    def as_option(value) -> str:
        return as_text(value)

    question_type = as_text(parsed.get("question_type")).lower()
    if question_type not in ("choice", "fill", "solution"):
        has_options = any(
            as_option(parsed.get(key))
            for key in ("option_a", "option_b", "option_c", "option_d")
        )
        question_type = "choice" if has_options else "fill"

    correct = as_text(parsed.get("correct_answer"))
    if question_type == "choice":
        correct = correct.upper()
        if correct not in ("A", "B", "C", "D"):
            correct = "A"

    try:
        difficulty = int(parsed.get("difficulty") or 3)
    except (TypeError, ValueError):
        difficulty = 3
    difficulty = max(1, min(5, difficulty))
    difficulty_points = as_text(parsed.get("difficulty_points"))

    raw_tags = parsed.get("knowledge_tags") or []
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split(",")
    tags: List[str] = []
    for tag in raw_tags:
        tag = as_text(tag)
        if tag and tag not in tags:
            tags.append(tag)

    question = as_text(parsed.get("question")) or fallback_text
    source = as_text(parsed.get("source"))
    source_type = as_text(parsed.get("source_type")).lower()
    if source_type == "self":
        source_type = "other"
    if source_type not in ("real_exam", "mock", "other"):
        source_type = (
            "real_exam"
            if "真题" in source
            else "mock"
            if "模拟" in source
            else "other"
        )
    source_year = as_text(parsed.get("source_year"))
    if not source_year:
        year_match = re.search(r"(19|20)\d{2}", source)
        source_year = year_match.group(0) if year_match else ""
    source_name = as_text(parsed.get("source_name"))
    return {
        "question_type": question_type,
        "question": question,
        "option_a": as_option(parsed.get("option_a")),
        "option_b": as_option(parsed.get("option_b")),
        "option_c": as_option(parsed.get("option_c")),
        "option_d": as_option(parsed.get("option_d")),
        "correct_answer": correct,
        "analysis": as_text(parsed.get("analysis")),
        "difficulty": difficulty,
        "difficulty_points": difficulty_points,
        "knowledge_tags": tags,
        "approach": as_text(parsed.get("approach")),
        "source": source,
        "source_type": source_type,
        "source_year": source_year,
        "source_name": source_name,
    }


def analyze_text(text: str, standard_tags: List[str] | None = None) -> dict:
    """根据粘贴的题干文本生成结构化错题数据。"""
    messages = [
        {"role": "system", "content": _parse_prompt(standard_tags)},
        {"role": "user", "content": text},
    ]
    return normalize_parsed(_extract_json(_chat(messages)), fallback_text=text.strip())


def ocr_image(
    image_base64: str,
    standard_tags: List[str] | None = None,
    model: str | None = None,
) -> dict:
    """识别图片中的题目并生成结构化错题数据。"""
    image_base64 = image_base64.strip()
    if image_base64.startswith("data:"):
        data_url = image_base64
    else:
        data_url = "data:image/png;base64," + image_base64
    messages = [
        {"role": "system", "content": _parse_prompt(standard_tags)},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "请识别图片中的题目，并按要求输出 JSON。"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    if model:
        return normalize_parsed(
            _extract_json(
                _chat(
                    messages,
                    model=model,
                    base_url=settings.AI_VISION_BASE_URL or None,
                    api_key=settings.AI_VISION_API_KEY or None,
                )
            )
        )
    return normalize_parsed(_extract_json(_chat(messages)))


def summarize_knowledge(tag_name: str, mistakes: List[dict]) -> str:
    """根据同知识点错题生成复习总结。"""
    material = "\n\n".join(
        f"题目：{item.get('question', '')}\n"
        f"答案：{item.get('correct_answer', '')}\n"
        f"解析：{item.get('analysis') or '无'}"
        for item in mistakes[:8]
    )
    prompt = (
        f"请根据以下与知识点“{tag_name}”相关的错题材料，写一段适合复习的知识点总结，"
        "包含核心概念、常见易错点、记忆要点，300 字以内，直接输出正文，不要 Markdown。\n\n"
        + material
    )
    return _chat([{"role": "user", "content": prompt}]).strip()


def _grade_prompt() -> str:
    return (
        "你是一名严谨的考研阅卷老师。请根据题目、参考答案要点和标准解析，"
        "对学生的解答进行批改。输出严格的 JSON（不要 Markdown）：\n"
        '{"score": 0-100 的整数（按过程给分，步骤对就给步骤分）, '
        '"verdict": "correct/partial/wrong", '
        '"errors": ["错因1", "错因2"], '
        '"strengths": ["做对的步骤或思路"], '
        '"feedback": "总体评价，指出对在哪、错在哪、丢分在哪", '
        '"solution": "标准详细解答：先写思路，再逐步推导，直到得到正确答案", '
        '"alternate_methods": ["其他解法1", "其他解法2"]}\n'
        "要求：只看数学/学科逻辑，不因格式扣分；学生没写过程只有答案时，"
        "按答案给结论分；有过程但结果错误时按步骤给分并说明错在哪一步。"
    )


def normalize_grade(parsed: dict) -> dict:
    """规整 AI 批改结果，保证前端字段可用。"""
    if not isinstance(parsed, dict):
        parsed = {}
    try:
        score = int(parsed.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    verdict = str(parsed.get("verdict") or "").strip().lower()
    if verdict not in ("correct", "partial", "wrong"):
        verdict = "wrong" if score < 60 else ("partial" if score < 100 else "correct")
    return {
        "score": score,
        "verdict": verdict,
        "errors": [str(item) for item in (parsed.get("errors") or [])],
        "strengths": [str(item) for item in (parsed.get("strengths") or [])],
        "feedback": str(parsed.get("feedback") or "").strip(),
        "solution": str(parsed.get("solution") or "").strip(),
        "alternate_methods": [str(item) for item in (parsed.get("alternate_methods") or [])],
    }


def grade_solution(
    question: str,
    correct_answer: str,
    analysis: str,
    user_answer: str,
) -> dict:
    """AI 批改解答题：按过程给分，返回得分、错因与标准解答。"""
    material = (
        f"题目：{question}\n"
        f"参考答案要点：{correct_answer or '未提供'}\n"
        f"标准解析：{analysis or '未提供'}\n"
        f"学生解答：\n{user_answer}"
    )
    messages = [
        {"role": "system", "content": _grade_prompt()},
        {"role": "user", "content": material},
    ]
    return normalize_grade(_extract_json(_chat(messages)))
