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
        "question_type 只能输出三个值之一：choice/fill/solution，根据题目形式判断："
        "有 A/B/C/D 选项选 choice，只要求填数值或结果的选 fill，"
        "需要写完整过程或证明的选 solution。"
        "选择题的 correct_answer 只能填单个字母 A/B/C/D，不要填多个字母，"
        "也不要写“ABCD”或“A、B”；四个选项各自只填该选项自己的内容，"
        "不要把题干或全部选项重复填进每个选项。"
        "如果某个选项缺失，填空字符串即可；如果无法确定正确答案，"
        "给出最可能的答案并在解析中说明。source_type：真题填 real_exam 并填写年份，"
        "模拟题填 mock 并填写年份和卷名，其他填 other。\n"
        "题干（question）和选项（option_a~d）中的数学表达式必须全部用 $...$ 或 $$...$$ 包裹，"
        "禁止出现裸露的 ^、_、\\alpha、A^2β 等未渲染文本；例如 $A^2\\beta=\\beta$、$\\alpha^T\\beta=0$、$E-k\\alpha\\alpha^T$。\n"
        "解析（analysis）必须符合以下风格：\n"
        "1. 先写“思路”：用一两句大白话说明这道题要做什么、用什么方法。\n"
        "2. 再分小步推导：步骤用 1.1、1.2、2.1 编号，每一步只做一个小动作。\n"
        "3. 每步必须写出公式并代入具体数值演算，例如 $1+1+4=6$、$\\dfrac{1\\times1+2\\times1+3\\times4}{6}=\\dfrac{15}{6}=2.5$，不能只写结论不写过程。\n"
        "4. 像给同学讲题一样通俗：遇到“代数重数”“几何重数”“特征子空间”“正交补”等概念，第一次出现时先用一句话解释清楚，再使用。\n"
        "5. 不要堆砌术语或做大段绕口的综合论证，把大结论拆成几个能看懂的小结论逐步推出。\n"
        "6. 解析控制在 200-500 字左右，除非推导确实需要更长。\n"
        "7. 最后单独一行写明“结论：”或“答案：”。\n"
        "8. 解析和题干中的所有公式统一用 $...$ 行内、$$...$$ 独立行的 LaTeX 写法。\n"
        "9. JSON 字符串中的换行使用真实换行符，不要把 \\n 当作字面量文本输出；$ 只能包裹同一行内的单个公式。"
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
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            return json.loads(content[start : end + 1])
        raise


_MATH_RUN_RE = re.compile(
    r"[A-Za-z\u0370-\u03ff\\(][A-Za-z0-9\u0370-\u03ff\\^_{}+\-*/=<>()\[\].,·'|&:;!~#%]*"
)


def _looks_like_math(content: str) -> bool:
    content = content.strip()
    if not content or "\n" in content:
        return False
    if "\\" in content or "^" in content or "_" in content:
        return True
    if re.search(r"[\u0370-\u03ff]", content):
        return True
    if re.search(r"[A-Za-z0-9]", content) and re.search(r"[=+\-*/<>]", content):
        return True
    return False


def _normalize_math_delimiters(text: str) -> str:
    """成对保留合法 $...$ / $$...$$，删除 AI 生成的孤立或错位 $。"""
    def at_line_start(index: int) -> bool:
        if index == 0:
            return True
        newline = text.rfind("\n", 0, index)
        prefix = text[:index] if newline == -1 else text[newline + 1 : index]
        return prefix.strip() == ""

    out: List[str] = []
    index = 0
    length = len(text)
    display_open = False
    inline_open = False
    display_chars: List[str] = []
    inline_chars: List[str] = []

    while index < length:
        if text.startswith("$$", index):
            if display_open:
                content = "".join(display_chars)
                if "\n" in content:
                    out.append("$$" + content + "$$")
                else:
                    out.append("$" + content + "$")
                display_open = False
                display_chars = []
            elif inline_open:
                content = "".join(inline_chars)
                out.append(
                    "$" + content + "$"
                    if _looks_like_math(content)
                    else content
                )
                inline_open = False
                inline_chars = []
                continue
            else:
                next_display = text.find("$$", index + 2)
                if next_display == -1:
                    index += 2
                    continue
                content = text[index + 2 : next_display]
                if at_line_start(index) and "\n" in content:
                    display_open = True
                else:
                    content = content.replace("$", "")
                    out.append(
                        "$" + content + "$"
                        if _looks_like_math(content)
                        else content
                    )
                    index = next_display + 2
                    continue
            index += 2
            continue
        if text[index] == "$":
            if display_open:
                index += 1
                continue
            if not inline_open:
                inline_open = True
                inline_chars = []
            else:
                content = "".join(inline_chars)
                out.append(
                    "$" + content + "$"
                    if _looks_like_math(content)
                    else content
                )
                inline_open = False
                inline_chars = []
            index += 1
            continue
        if display_open:
            display_chars.append(text[index])
        elif inline_open:
            inline_chars.append(text[index])
        else:
            out.append(text[index])
        index += 1

    if display_open:
        out.append("".join(display_chars))
    elif inline_open:
        out.append("".join(inline_chars))
    return "".join(out)


def _normalize_latex_delimiters(text: str) -> str:
    """把 AI 常见的 \\(...\\) 与 \\[...\\] 数学定界符统一为 $...$ / $$...$$。

    DeepSeek 等模型常输出标准 LaTeX 显示语法 \\( \\), 而本项目 KaTeX 渲染
    约定使用 $...$ / $$...$$；此转换在 _wrap_math 之前执行，保证所有
    AI 文本（错题解析、知识点总结、批改解答）公式都能渲染。
    """
    if not text:
        return text
    text = text.replace("\\[", "$$").replace("\\]", "$$")
    text = text.replace("\\(", "$").replace("\\)", "$")
    return text


def _wrap_math(text: str) -> str:
    """把裸露的公式片段包成 $...$，已存在的 $...$ / $$...$$ 保持不变。"""
    if not text:
        return text
    # 先统一 AI 输出的 \\(...\\) / \\[...\\] 定界符为 $...$ / $$...$$
    text = _normalize_latex_delimiters(text)
    # 修复模型偶尔输出的字面 \n。
    text = text.replace("\\n", "\n")
    # 修复 $' 这类被 AI 拆坏的撇号写法。
    text = re.sub(r"\$'([^$]*?)\$", lambda m: "'" + m.group(1), text)
    text = re.sub(r"\$'", "'", text)
    text = re.sub(r"'\$", "'", text)
    text = _normalize_math_delimiters(text)
    protected: List[str] = []

    def stash(match):
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = re.sub(r"\$\$[\s\S]+?\$\$", stash, text)
    text = re.sub(r"\$[^$\n]+?\$", stash, text)
    # 归一化后仍残留的 $ 全部是杂质，直接删除。
    text = text.replace("$", "")

    def repl(match):
        token = match.group(0)
        if re.search(r"[\^_\\\u0370-\u03ff]", token):
            return "$" + token + "$"
        return token

    text = _MATH_RUN_RE.sub(repl, text)

    def restore(match):
        return protected[int(match.group(1))]

    return re.sub(r"\x00(\d+)\x00", restore, text)


def normalize_parsed(parsed: dict, fallback_text: str = "") -> dict:
    """把 AI 返回的 JSON 规整为前端表单可直接使用的结构。"""
    if not isinstance(parsed, dict):
        parsed = {}

    def as_text(value) -> str:
        return str(value or "").strip()

    def as_option(value) -> str:
        text = as_text(value)
        text = re.sub(r"^\s*[A-Da-d]\s*[\.、．:：)]\s*", "", text)
        return text.strip()

    question_type = as_text(parsed.get("question_type")).lower()
    if "choice" in question_type:
        question_type = "choice"
    elif "fill" in question_type:
        question_type = "fill"
    elif "solution" in question_type:
        question_type = "solution"
    else:
        has_options = any(
            as_option(parsed.get(key))
            for key in ("option_a", "option_b", "option_c", "option_d")
        )
        question_type = "choice" if has_options else "fill"

    option_keys = ("option_a", "option_b", "option_c", "option_d")
    option_values = [as_option(parsed.get(key)) for key in option_keys]
    non_empty_options = [value for value in option_values if value]
    if len(non_empty_options) >= 2 and len(set(non_empty_options)) == 1:
        option_values = ["", "", "", ""]

    correct = as_text(parsed.get("correct_answer"))
    if question_type == "choice":
        letters = re.findall(r"[ABCD]", correct.upper())
        unique_letters = list(dict.fromkeys(letters))
        correct = unique_letters[0] if len(unique_letters) == 1 else ""

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
        "question": _wrap_math(question),
        "option_a": _wrap_math(option_values[0]),
        "option_b": _wrap_math(option_values[1]),
        "option_c": _wrap_math(option_values[2]),
        "option_d": _wrap_math(option_values[3]),
        "correct_answer": _wrap_math(correct),
        "analysis": _wrap_math(as_text(parsed.get("analysis"))),
        "difficulty": difficulty,
        "difficulty_points": _wrap_math(difficulty_points),
        "knowledge_tags": tags,
        "approach": _wrap_math(as_text(parsed.get("approach"))),
        "source": source,
        "source_type": source_type,
        "source_year": source_year,
        "source_name": source_name,
    }


def analyze_text(
    text: str,
    standard_tags: List[str] | None = None,
    timeout: int | None = None,
    instruction: str = "",
) -> dict:
    """根据粘贴的题干文本生成结构化错题数据；instruction 为可选补充解题要求。"""
    user_text = text.strip()
    if instruction and instruction.strip():
        user_text += (
            "\n\n【补充要求】"
            + instruction.strip()
            + "（请严格遵循该思路/方向解题，要求写详细的部分展开写，其余按正常规范）"
        )
    messages = [
        {"role": "system", "content": _parse_prompt(standard_tags)},
        {"role": "user", "content": user_text},
    ]
    return normalize_parsed(
        _extract_json(_chat(messages, timeout=timeout)),
        fallback_text=text.strip(),
    )


def ocr_image(
    image_base64: str,
    standard_tags: List[str] | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
    instruction: str = "",
    reference_image_base64: str = "",
) -> dict:
    """识别图片中的题目并生成结构化错题数据。

    instruction 为可选文字要求（如按某思路解题、某步骤写详细）；
    reference_image_base64 为可选参考图片（要求按图中思路/方法解题）。
    """
    image_base64 = image_base64.strip()
    if image_base64.startswith("data:"):
        data_url = image_base64
    else:
        data_url = "data:image/png;base64," + image_base64

    text_part = "请识别图片中的题目，并按要求输出 JSON。"
    if instruction and instruction.strip():
        text_part += (
            "\n\n【补充要求】"
            + instruction.strip()
            + "（请严格遵循该思路/方向解题，要求写详细的部分展开写）"
        )
    content = [
        {"type": "text", "text": text_part},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    if reference_image_base64 and reference_image_base64.strip():
        ref = reference_image_base64.strip()
        if ref.startswith("data:"):
            ref_data_url = ref
        else:
            ref_data_url = "data:image/png;base64," + ref
        content.append(
            {"type": "text", "text": "【参考图片】请按此图中的思路/方法解题。"}
        )
        content.append(
            {"type": "image_url", "image_url": {"url": ref_data_url}}
        )

    messages = [
        {"role": "system", "content": _parse_prompt(standard_tags)},
        {"role": "user", "content": content},
    ]
    if model:
        return normalize_parsed(
            _extract_json(
                _chat(
                    messages,
                    model=model,
                    base_url=base_url or settings.AI_VISION_BASE_URL or None,
                    api_key=api_key or settings.AI_VISION_API_KEY or None,
                    timeout=timeout,
                )
            )
        )
    return normalize_parsed(_extract_json(_chat(messages, timeout=timeout)))


def vision_extract_text(
    image_base64: str,
    timeout: int | None = None,
    instruction: str = "",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """视觉模型直接提取图片中的文字内容（不解析为错题结构），返回原始文本。"""
    image_base64 = image_base64.strip()
    if image_base64.startswith("data:"):
        data_url = image_base64
    else:
        data_url = "data:image/png;base64," + image_base64

    text_part = (
        "请完整、准确地提取图片中的文字内容，包括题干、选项、公式、图表标注等。"
        "数学公式用 LaTeX 表示。只输出提取到的文字本身，不要解释或补充。"
    )
    if instruction and instruction.strip():
        text_part += "\n\n【重点关注】" + instruction.strip()

    content = [
        {"type": "text", "text": text_part},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    messages = [{"role": "user", "content": content}]
    return _chat(
        messages,
        model=model,
        base_url=base_url or settings.AI_VISION_BASE_URL or None,
        api_key=api_key or settings.AI_VISION_API_KEY or None,
        timeout=timeout,
    )


_KNOWLEDGE_PROMPT = """你是一名知识点整理助手。请根据用户提供的学习材料，提炼为一个结构化的知识点，输出严格的 JSON（不要 Markdown），字段如下：
{"tag_name": "知识点标准名称（简短，3-12 字，如：等价无穷小、地址转换、长难句结构）",
"summary": "知识点总结：讲清核心概念、关键公式（数学公式用 $...$ LaTeX）、怎么用、常见易错点，300-500 字，可用 Markdown 列表/表格",
"related_tags": ["关联知识点标签", "最多5个"]}
要求：tag_name 用学习材料中出现的关键概念命名；summary 让学习者看完就能懂并会用；related_tags 尽量用常见标准标签，不要生造。"""


def analyze_knowledge(
    text: str,
    instruction: str = "",
) -> dict:
    """把学习材料文本解析为知识点草稿（tag_name/summary/related_tags）。"""
    user_text = text.strip()
    if instruction and instruction.strip():
        user_text += "\n\n【重点关注/分析要求】" + instruction.strip()
    parsed = _extract_json(
        _chat(
            [
                {"role": "system", "content": _KNOWLEDGE_PROMPT},
                {"role": "user", "content": user_text},
            ]
        )
    )
    if not isinstance(parsed, dict):
        parsed = {}

    raw_tags = parsed.get("related_tags") or []
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split(",")
    tags: List[str] = []
    for tag in raw_tags:
        tag = str(tag or "").strip()
        if tag and tag not in tags:
            tags.append(tag)

    return {
        "tag_name": str(parsed.get("tag_name") or "").strip(),
        "summary": _wrap_math(str(parsed.get("summary") or "").strip()),
        "related_tags": tags[:5],
        "source_text": user_text[:2000],
    }


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
        "包含核心概念、常见易错点、记忆要点，300 字以内，直接输出正文，不要 Markdown。"
        "数学公式一律用 $...$ 包裹（行内）或 $$...$$（独立行），不要用 \\(...\\) 或 \\[...\\] 写法。\n\n"
        + material
    )
    return _wrap_math(_chat([{"role": "user", "content": prompt}]).strip())


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
