"""AI 服务层：调用 OpenAI 兼容的 chat/completions 接口。"""

import base64
import http.client
import json
import re
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import List

from app.config import settings


class AiNotConfigured(Exception):
    pass


class AiRequestError(Exception):
    pass


# 解析步骤并发执行器：词汇‖题目清单、逐题解析并行。各步的 prompt / max_tokens 与
# 串行版完全一致，质量不减，只是把互不依赖的调用改为并发以缩短墙钟时间；
# _chat 每次调用自建 opener、无共享可变状态，线程安全。
_ANALYSIS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="km-analysis")


def is_configured() -> bool:
    return bool(settings.AI_API_KEY or settings.AI_VISION_API_KEY)


def _chat(
    messages: List[dict],
    timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    response_format: dict | None = None,
    max_tokens: int | None = None,
) -> str:
    if not is_configured():
        raise AiNotConfigured()
    url = (base_url or settings.AI_BASE_URL).rstrip("/") + "/chat/completions"
    payload = {
        "model": model or settings.AI_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
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
        for attempt in range(4):
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
                # 429 与服务端临时错误都值得重试
                if exc.code in (429, 500, 502, 503) and attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise AiRequestError(last_message) from exc
            except (
                http.client.IncompleteRead,
                http.client.RemoteDisconnected,
                ConnectionError,
                TimeoutError,
                socket.timeout,
                urllib.error.URLError,
            ) as exc:
                # 上游断连/超时：0 bytes 等偶发，重试更稳
                last_message = f"AI 连接中断：{exc}"
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise AiRequestError(last_message) from exc
            except OSError as exc:
                last_message = f"AI 网络错误：{exc}"
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
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


def _chat_json(messages: List[dict], attempts: int = 3, **kwargs) -> dict:
    """调用 AI 并解析严格 JSON。空内容/畸形/截断都算失败并重试（最多 3 次）。"""
    last = None
    for i in range(max(1, attempts)):
        content = _chat(messages, **kwargs)
        if content is None or not str(content).strip():
            last = ValueError("AI 返回内容为空")
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
                continue
            break
        try:
            return _extract_json(content)
        except (json.JSONDecodeError, ValueError) as exc:
            last = exc
            if i < attempts - 1:
                time.sleep(1.2)
                continue
    raise AiRequestError(f"AI 返回内容不是有效 JSON：{last}") from last


def analyze_weekly_report(items: List[dict]) -> dict:
    """近 7 天错题的错因聚类周报。items 由路由层从 review_records 组装。"""
    prompt = (
        "你是考研错题分析教练。下面是这位学生最近 7 天答错的题目清单（JSON）。"
        "请按错因聚类分析（如：概念不清 / 计算失误 / 审题偏差 / 方法不会 / 记忆遗忘，"
        "可自拟但不超过 5 类，按数量降序），并给出针对性训练建议。"
        "输出严格 JSON（不要 Markdown）：\n"
        '{"summary": "本周错题总体诊断，2-3 句，点出最危险的趋势", '
        '"clusters": [{"cause": "错因名", "count": 该类题数, '
        '"tags": ["涉及知识点", 最多 4 个], "advice": "针对性建议 1-2 句", '
        '"mistake_ids": [命中的题目 id]}]}\n\n'
        "题目清单：\n" + json.dumps(items, ensure_ascii=False)
    )
    parsed = _chat_json(
        [{"role": "user", "content": prompt}],
        max_tokens=2000,
    )
    if not isinstance(parsed, dict):
        raise AiRequestError("AI 返回的周报格式异常")
    return parsed


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
        '"source_year": "如 2025", "source_name": "如 李林六套卷(一)", '
        '"subject_hint": "数学/英语/408/政治"}\n'
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
        "9. JSON 字符串中的换行使用真实换行符，不要把 \\n 当作字面量文本输出；$ 只能包裹同一行内的单个公式。\n"
        "10. 解析必须做到「懂一题、会三题」，明显比参考答案更细致更精细：\n"
        "a) 【深入讲透考点】先把题中涉及的概念、公式、原理用大白话讲清楚（是什么、为什么这样、怎么用、容易错在哪），不能一带而过；\n"
        "b) 【联想拓展/举一反三】主动联想相关的知识点、同类题型、变式与常见陷阱，并补充 1-3 个关联方法或扩展知识点；\n"
        "c) 分步推导要每一步写清依据与细节（如 1.1、1.2、2.1），展示完整推理过程，而不只是给出结论。\n"
        "11. 讲题要「当作读者没学过」：对题中出现的每个关键知识点（如 ARP、子网掩码、数据结构、等价无穷小、长难句结构等），"
        "先独立、完整地介绍它在考研里的考法、原理、常见题型、常与哪些知识点组合出现，再解题；"
        "不要默认读者已深刻掌握而直接讲题。\n"
        "整段解析要有启发性与深度，让读者不仅会这一题，还能迁移到同类题。"
    )
    if standard_tags:
        prompt += (
            "\n以下是系统里已有的标准知识点标签，若适用请直接使用，"
            "不要新增近似叫法："
            + "、".join(standard_tags[:40])
        )
    return prompt


def _repair_backslashes(content: str) -> str:
    """把 JSON 字符串值里未转义的反斜杠修复为 \\\\（修 LaTeX 的 \\alpha 等导致 Invalid \\escape）。"""
    out = []
    in_str = False
    i = 0
    n = len(content)
    while i < n:
        ch = content[i]
        if ch == '"':
            out.append(ch)
            in_str = not in_str
            i += 1
            continue
        if ch == "\\" and in_str and i + 1 < n:
            nxt = content[i + 1]
            if nxt in ('"', "\\", "/", "b", "f", "n", "r", "t", "u"):
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            # 非法转义（如 \alpha 的 \a）→ 变成 \\a
            out.append("\\\\")
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _repair_json(content: str) -> str:
    """修复 AI 常见 JSON 问题：未转义反斜杠、缺失逗号、尾逗号。"""
    repaired = _repair_backslashes(content)
    # 数组里两个对象 / 数组元素之间缺逗号：} { 或 } [ 或 ] [
    repaired = re.sub(r"\}\s*(?=\{)", "},", repaired)
    repaired = re.sub(r"\}\s*(?=\[)", "},", repaired)
    # 对象内：字符串值/数字/数组/对象后紧接下一个键而缺逗号
    repaired = re.sub(
        r'(?<![{,\s])(["\d\]\}])\s*(?="[a-zA-Z_][a-zA-Z0-9_]*"\s*:)',
        r"\1,",
        repaired,
    )
    # 去掉尾逗号
    return re.sub(r",(\s*[}\]])", r"\1", repaired)


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    last_error: json.JSONDecodeError | None = None
    for candidate in (content, None):
        # 先试原始、再试 {..} 提取、再试修复
        if candidate is None:
            break
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError as exc:
                last_error = exc
        repaired = _repair_json(candidate)
        if repaired != candidate:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError as exc:
                last_error = exc
    raise last_error if last_error is not None else json.JSONDecodeError(
        "无效 JSON", content, 0
    )


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
        "subject_hint": as_text(parsed.get("subject_hint")),
    }


def _parse_english_prompt(standard_tags: List[str] | None = None) -> str:
    prompt = (
        "你是考研英语阅读精读助手。请根据用户提供的英语原文（可从多张图片识别，或直接粘贴文本），"
        "自动判断是否为英语篇章/阅读内容，并输出严格的 JSON（不要 Markdown），字段如下：\n"
        '{"is_english": true/false, '
        '"passage": "识别出的英语原文全文，段落之间用 \\n\\n 分隔，明确分段", '
        '"passage_translation": "全文通顺的中文翻译，段落与原文一一对应，段落间用 \\n\\n 分隔", '
        '"sentences": [{"text": "单个句子", "structure": "句子结构（主谓宾/主从复合句/并列句等）", '
        '"pattern": "句型分析（定语从句/同位语从句/非谓语/插入语/倒装等，具体到知识点）", '
        '"translation": "该句中文翻译"}], '
        '"phrases": [{"phrase": "考研重要短语", "meaning": "短语含义", "pos": "短语/固定搭配", "example": "选自原文的例句"}], '
        '"words": [{"word": "生词/重点词", '
        '"meaning": "词义（含多个词性与义项，如 v. 放弃；n. 放纵；adj. 放任的）", '
        '"pos": "词性（动词/名词/形容词/副词/动名词/介词/连词/代词/数词等）", '
        '"phonetic": "音标（如 /əˈbændən/）", "example": "选自原文的例句"}], '
        '"question_type": "choice/fill/solution", '
        '"question": "题目题干", '
        '"option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", '
        '"correct_answer": "选择题填 A/B/C/D，其他填参考答案文本", '
        '"analysis": "解析：先写【定位】原文第几句/哪一段；再写【来源】哪年真题或篇目出处；再写【思路】如何理解与作答；最后【总结】该题考点与答题要点", '
        '"difficulty": 1-5 的整数, "difficulty_points": "主要难点简析", '
        '"knowledge_tags": ["标签1", "标签2"], "approach": "解题思路", '
        '"source": "来源备注", "source_type": "real_exam/mock/other", '
        '"source_year": "如 2017", "source_name": "如 2017 英语二 阅读 Text 2", '
        '"questions": [{"question": "第2题题干", "option_a": "...", "option_b": "...", '
        '"option_c": "...", "option_d": "...", "correct_answer": "另一题的答案", '
        '"analysis": "该题解析（含定位/来源/思路/总结）", "difficulty": 3, '
        '"difficulty_points": "该题难点", "approach": "该题思路"}]}\n'
        "判断规则：若图片/文本是英语篇章（多为句英文、阅读/完形/翻译段落），is_english=true，"
        "完整填写 passage/translation/sentences/phrases/words；"
        "段落含多道题目时，把第 2 道及以后的题目逐一放进 questions 数组（每题含 question/option_a~d/"
        "correct_answer/analysis/difficulty 等标准字段，解析同样要写【定位/来源/思路/总结】）；"
        "顶层 question/option_a~d/answer/analysis 填第一道题，避免与 questions 重复；"
        "若只有一道题，questions 填空数组。"
        "若不是英语篇章（如数学、政治、计算机等），is_english=false，passage 填空字符串，"
        "只按通用错题字段输出（question/options/answer/analysis 等）。\n"
        "选择题的 correct_answer 只能填单个字母 A/B/C/D。question_type：有 A/B/C/D 选项选 choice，"
        "只填数值/结果选 fill，写完整过程选 solution。\n"
        "题干与选项中的数学/LaTeX 表达式用 $...$ 或 $$...$$ 包裹；但英语原文 passage 与翻译不要用 $ 包裹。\n"
        "sentences 必须覆盖原文的每一个句子（包括引号内的对话、破折号后的分句），逐句给出 "
        "text/structure/pattern/translation，不要合并、不要省略；words 尽量完整收录原文里的考研重点词与生词、高频词，"
        "每个词给出多词性与完整义项；phrases 尽量完整收录考研重要短语与固定搭配，不要人为减少数量。\n"
        "解析用【定位】【来源】【思路】【总结】四段，不要用 1.1/1.2 这类编号（那是数学/408 的格式）。\n"
        "【定位】必须指明原文具体位置（如“第二段第二句”），并引用定位到的那句话或关键词；"
        "禁止只写“全文”或笼统描述。\n"
        "【来源】写明哪年真题/哪篇哪题。\n"
        "【思路】用通顺自然语言详细讲清推理与排除过程（可自然分段或“第一/第二/第三”，但不用硬编号），"
        "像给同学讲题一样通俗、有依据，不能只给结论。\n"
        "【总结】点明该题考点与易错点。"
    )
    if standard_tags:
        prompt += (
            "\n以下是系统里已有的标准知识点标签，若适用请直接使用，不要新增近似叫法："
            + "、".join(standard_tags[:40])
        )
    return prompt


def _clean_items(raw) -> List[dict]:
    """把 AI 返回的句子/短语/单词列表规整为字典数组；兜底按行拆分。"""
    items: List[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            cleaned = {k: str(v or "").strip() for k, v in item.items()}
            if any(cleaned.values()):
                items.append(cleaned)
        return items
    if isinstance(raw, str) and raw.strip():
        for line in raw.splitlines():
            line = line.strip()
            if line:
                items.append({"text": line})
    return items


def normalize_english_parsed(parsed: dict, fallback_text: str = "") -> dict:
    """规整英语整篇解析结果：保留标准错题字段，并挂上英语附加内容与多题。"""
    if not isinstance(parsed, dict):
        parsed = {}
    is_english = bool(parsed.get("is_english"))
    base = normalize_parsed(parsed, fallback_text)
    base["is_english"] = is_english
    base["passage_text"] = str(parsed.get("passage") or "").strip()
    base["passage_translation"] = str(parsed.get("passage_translation") or "").strip()
    base["english_sentences"] = _clean_items(parsed.get("sentences"))
    base["english_phrases"] = _clean_items(parsed.get("phrases"))
    base["english_words"] = _clean_items(parsed.get("words"))
    # 多道题目：第 2 题起的完整题目数组；顶层已填第一题
    questions = parsed.get("questions")
    base["english_questions"] = []
    if isinstance(questions, list):
        for q in questions:
            if not isinstance(q, dict):
                continue
            qq = normalize_parsed(q)
            # 题目来自同一篇，继承来源信息
            for key in ("source", "source_type", "source_year", "source_name"):
                if not qq.get(key) and base.get(key):
                    qq[key] = base[key]
            qq["is_english"] = True
            base["english_questions"].append(qq)
    return base


def _guess_mime(data_url: str) -> str:
    """从图片 base64 推测 MIME（避免一律当 PNG 被视觉模型拒识返回空）。"""
    payload = data_url.partition("base64,")[2]
    if payload.startswith("iVBOR"):
        return "image/png"
    if payload.startswith("/9j/"):
        return "image/jpeg"
    if payload.startswith("R0lGOD"):
        return "image/gif"
    if payload.startswith("UklGR"):
        return "image/webp"
    return "image/png"


def _vision_extract_text(
    images: List[str],
    instruction: str = "",
    timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """用视觉模型把图片里的文字提取成纯文本（小输出、快、稳，供后续文本分析）。

    未指定通道时默认走 DeepSeek 视觉首选；指定 model/base_url/api_key 时使用
    调用方通道（多通道回退由路由层逐个尝试），保证回退链真正生效。
    """
    content = []
    head = "请识别这几张图片中的文字，原样完整输出（保留段落与换行）；只输出文字本身，不要解释。"
    if instruction and instruction.strip():
        head += "\n" + instruction
    content.append({"type": "text", "text": head})
    for img in images:
        data_url = img.strip()
        if not data_url.startswith("data:"):
            data_url = f"data:{_guess_mime(data_url)};base64," + data_url
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    result = _chat(
        [{"role": "user", "content": content}],
        model=model or settings.AI_VISION_DS_MODEL,
        base_url=base_url,
        api_key=api_key,
        max_tokens=4000,
        timeout=timeout,
    )
    return str(result or "").strip()


def _parse_english_reading_prompt(standard_tags: List[str] | None = None) -> str:
    return (
        "你是考研英语阅读精读助手。根据用户提供的英语原文，输出严格的 JSON（不要 Markdown）：\n"
        '{"is_english": true/false, '
        '"passage_translation": "全文通顺中文翻译，段落与原文一一对应，段落间用 \\n\\n 分隔", '
        '"sentences": [{"text": "单个句子", "structure": "句子结构", '
        '"pattern": "句型分析（定语从句/同位语/非谓语/插入语/倒装等，具体到知识点）", "translation": "该句中文翻译"}]}\n'
        "判断：原文是英语篇章则 is_english=true；sentences 必须覆盖原文每一个句子（含引号内对话、破折号分句），"
        "逐句给出 text/structure/pattern/translation，不要合并、不要省略；否则 is_english=false。"
    )


def _parse_english_vocab_prompt() -> str:
    return (
        "你是考研英语词汇助手。根据用户提供的英语原文，提取重点短语与生词，输出严格的 JSON（不要 Markdown）：\n"
        '{"phrases": [{"phrase": "考研重要短语", "meaning": "短语含义", "pos": "短语/固定搭配", "example": "原文例句"}], '
        '"words": [{"word": "生词/重点词", '
        '"meaning": "词义（含多个词性与义项，如 v. 放弃；n. 放纵；adj. 放任的）", '
        '"pos": "词性（动词/名词/形容词/副词/动名词/介词/连词等）", "phonetic": "音标", "example": "原文例句"}]}\n'
        "words 与 phrases 尽量完整收录原文里的考研重点词、生词与重要短语/固定搭配，不要人为减少数量。"
    )


def _parse_english_questions_prompt(standard_tags: List[str] | None = None) -> str:
    prompt = (
        "你是考研英语阅读精读助手。根据用户提供的英语原文与题目要求，输出严格的 JSON（不要 Markdown），字段如下：\n"
        '{"question_type": "choice/fill/solution", "question": "题目题干", '
        '"option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", '
        '"correct_answer": "选择题填 A/B/C/D，其他填参考答案文本", '
        '"analysis": "解析：用【定位】【来源】【思路】【总结】四段。'
        '【定位】要指明原文具体句（如“第二段第二句”）并引用关键词，禁止只写“全文”；'
        '【来源】写明哪年真题/哪篇哪题；'
        '【思路】用通顺自然语言详细讲清推理与排除过程（可自然分段或“第一/第二”，但不要用 1.1/1.2 编号）；'
        '【总结】点明考点与易错点。", '
        '"difficulty": 1-5 的整数, "difficulty_points": "主要难点简析", '
        '"knowledge_tags": ["标签1", "标签2"], "approach": "解题思路", '
        '"source": "来源备注", "source_type": "real_exam/mock/other", "source_year": "如 2010", '
        '"source_name": "如 2010 英语一 阅读 Text 4", '
        '"questions": [{"question": "下一题题干", "option_a": "...", "option_b": "...", '
        '"option_c": "...", "option_d": "...", "correct_answer": "另一题答案", '
        '"analysis": "该题解析（含定位/来源/思路/总结）", "difficulty": 3, '
        '"difficulty_points": "该题难点", "approach": "该题思路"}]}\n'
        "顶层填第 1 题，第 2 题起的题目逐一放进 questions 数组。选择题 correct_answer 只能填单个字母 A/B/C/D。"
        "题干与选项里的数学/LaTeX 表达式用 $...$ 包裹。"
    )
    if standard_tags:
        prompt += (
            "\n以下是系统里已有的标准知识点标签，若适用请直接使用，不要新增近似叫法："
            + "、".join(standard_tags[:40])
        )
    return prompt


def analyze_english(
    image_base64_list: List[str],
    text: str = "",
    standard_tags: List[str] | None = None,
    instruction: str = "",
    timeout: int | None = None,
    vision_timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict:
    """英语整篇精读（分段式+并行波次，内容不减）：看图提字 → 阅读/翻译/拆解 → （词汇‖题目清单）→ 逐题解析并发。

    timeout 是整条链的总预算，内部逐步扣减，避免串行调用各自持有一份完整超时；
    各步的 prompt / max_tokens 与输出规格不受预算影响（不为提速降低生成质量），
    并发只用于缩短互不依赖调用（词汇‖清单、逐题）的墙钟时间；
    仅当预算真的耗尽时，失败步骤才退化为兜底结果（词汇空/该题仅题干清单）。
    model/base_url/api_key 指定视觉通道（未指定时用 DeepSeek 首选通道）。
    """
    deadline = time.monotonic() + (timeout or settings.AI_TIMEOUT)

    def _remaining(minimum: int = 5) -> int:
        return max(minimum, int(deadline - time.monotonic()))

    images = [img for img in (image_base64_list or []) if img and img.strip()]
    source_text = text.strip()
    if images:
        whole = max(1, int(deadline - time.monotonic()))
        limit = vision_timeout or settings.AI_VISION_PRIMARY_TIMEOUT
        vision_cap = max(10, whole - 60)
        try:
            source_text = (
                _vision_extract_text(
                    images,
                    instruction,
                    max(1, min(limit, vision_cap, whole)),
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                )
                or source_text
            )
        except Exception:
            source_text = text.strip()
    if not source_text.strip():
        raise AiRequestError("未能从图片或文本中获取到内容")

    # ① 阅读/翻译/句子拆解 + 是否英语
    reading = _chat_json(
        [
            {"role": "system", "content": _parse_english_reading_prompt(standard_tags)},
            {"role": "user", "content": source_text},
        ],
        max_tokens=4000,
        timeout=_remaining(),
    )
    if not reading.get("is_english"):
        return _analyze_standard_content(
            [], source_text, standard_tags, instruction, timeout=_remaining()
        )

    # ②+③清单 并行波次：重点短语/生词 与 题目清单互不依赖，同时请求。
    # 每步输出规格（prompt/max_tokens）与串行版一致；失败各自兜底，不互相阻塞。
    def _vocab_task() -> dict:
        try:
            return _chat_json(
                [
                    {"role": "system", "content": _parse_english_vocab_prompt()},
                    {"role": "user", "content": source_text},
                ],
                max_tokens=4000,
                timeout=_remaining(),
            )
        except Exception:
            return {}

    user_req = source_text
    if instruction and instruction.strip():
        user_req = f"{source_text}\n\n【要求】{instruction.strip()}"

    def _titles_task() -> list:
        # 先列题目清单（小、稳），逐题解析放下一波并发
        try:
            titles = _chat_json(
                [
                    {"role": "system", "content": (
                        "你是考研英语阅读助手。根据用户提供的原文与题目，输出严格的 JSON（不要 Markdown）：\n"
                        '{"questions": [{"question": "题干", "option_a": "...", "option_b": "...", '
                        '"option_c": "...", "option_d": "...", "correct_answer": "单字母或参考答案文本"}]}\n'
                        "只列出题目（含选项与答案），不要写解析；选择题 correct_answer 只能单个字母。"
                    )},
                    {"role": "user", "content": user_req},
                ],
                max_tokens=2500,
                timeout=_remaining(),
            )
            return titles.get("questions") or []
        except Exception:
            return []

    vocab = _ANALYSIS_EXECUTOR.submit(_vocab_task).result()
    questions_items = _ANALYSIS_EXECUTOR.submit(_titles_task).result()

    # ③ 逐题完整分析：并发执行（单题输出小，不易漏逗号；结果按清单顺序归位）
    todo = [q for q in questions_items if isinstance(q, dict) and q.get("question")]

    def _qa_task(q: dict) -> dict:
        opts = " ".join(str(q.get(k) or "") for k in ("option_a", "option_b", "option_c", "option_d"))
        try:
            return _chat_json(
                [
                    {"role": "system", "content": _parse_english_questions_prompt(standard_tags)},
                    {"role": "user", "content": (
                        "题目：" + str(q.get("question"))
                        + "\n选项：" + opts + "\n答案：" + str(q.get("correct_answer") or "")
                        + "\n\n请按 JSON 输出（仅这一题，含题干/选项/答案/解析/难度/标签）。"
                    )},
                ],
                max_tokens=3000,
                timeout=_remaining(),
            )
        except Exception:
            # 单题分析失败时保留该题清单信息兜底，不影响其它题
            return q

    full_questions = [_ANALYSIS_EXECUTOR.submit(_qa_task, q).result() for q in todo]

    if not full_questions:
        qa = _chat_json(
            [
                {"role": "system", "content": _parse_english_questions_prompt(standard_tags)},
                {"role": "user", "content": user_req},
            ],
            max_tokens=6000,
            timeout=_remaining(),
        )
        full_questions = [qa]

    qa = full_questions[0] if full_questions else {}
    qa["questions"] = full_questions[1:] if full_questions else []

    # 组装完整结构
    qa["is_english"] = True
    qa["subject_hint"] = "英语"
    qa["passage"] = source_text
    qa["passage_translation"] = reading.get("passage_translation", "")
    qa["sentences"] = reading.get("sentences", [])
    qa["phrases"] = vocab.get("phrases", [])
    qa["words"] = vocab.get("words", [])
    return normalize_english_parsed(qa, fallback_text=source_text)


def _analyze_standard_content(
    images: List[str],
    text: str,
    standard_tags: List[str] | None = None,
    instruction: str = "",
    timeout: int | None = None,
) -> dict:
    """对非英语内容用标准错题 prompt 分析（数学/408 等，含 1.1/1.2 详细分步、更细致）。"""
    prompt = _parse_prompt(standard_tags)
    if instruction and instruction.strip():
        text = (f"{text}\n\n【补充要求】{instruction.strip()}" if text else instruction.strip())
    if images:
        # 先看图提取文字（快、稳），再用文本做详细分析，避免超大视觉生成超时
        try:
            text = _vision_extract_text(images, instruction, timeout) or text
        except Exception:
            text = text
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text or "请分析这道题。"},
    ]
    parsed = _chat_json(messages, max_tokens=8000, timeout=timeout)
    return normalize_parsed(parsed, fallback_text=text)


_WORD_PROMPT = (
    "你是考研英语词汇助手。请用中文解释英语单词，输出严格的 JSON（不要 Markdown）：\n"
    '{"word": "原词", "phonetic": "音标（如 /əˈbændən/）", '
    '"meanings": [{"pos": "词性（动词/名词/形容词/副词/动名词/介词/连词等）", "meaning": "该词性下的中文释义"}], '
    '"example": "一个含该词的例句（尽量贴考研语境）"}\n'
    "要求：meanings 完整列出所有常见词性与义项（含动词/名词/形容词/动名词等），"
    "不要只给一个意思；释义准确通俗。"
)


def lookup_word(word: str, timeout: int | None = None) -> dict:
    """点词查义：用 AI 解释任意英语单词，返回多词性释义（供点击未收录单词时调用）。"""
    word = (word or "").strip()
    parsed = _extract_json(
        _chat(
            [
                {"role": "system", "content": _WORD_PROMPT},
                {"role": "user", "content": f"请解释单词：{word}"},
            ],
            timeout=timeout,
        )
    )
    if not isinstance(parsed, dict):
        parsed = {}
    meanings = parsed.get("meanings")
    if not isinstance(meanings, list):
        meanings = []
    return {
        "word": str(parsed.get("word") or word).strip(),
        "phonetic": str(parsed.get("phonetic") or "").strip(),
        "meanings": [
            {"pos": str(m.get("pos") or "").strip(), "meaning": str(m.get("meaning") or "").strip()}
            for m in meanings
            if isinstance(m, dict) and (m.get("pos") or m.get("meaning"))
        ],
        "example": str(parsed.get("example") or "").strip(),
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
        _chat_json(messages, max_tokens=8000, timeout=timeout),
        fallback_text=text.strip(),
    )


def ocr_image(
    image_base64: str,
    standard_tags: List[str] | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
    vision_timeout: int | None = None,
    instruction: str = "",
    reference_image_base64: str = "",
) -> dict:
    """识别图片中的题目并生成结构化错题数据。

    先看图提取文字（主图 + 可选参考图，走 model/base_url/api_key 指定的视觉通道，
    未指定时用 DeepSeek 首选），再用文本做详细分析；timeout 覆盖全程预算，
    避免视觉提取与文本分析各自持有一份完整超时导致总时长翻倍。
    """
    deadline = time.monotonic() + (timeout or settings.AI_TIMEOUT)
    images = [img for img in (image_base64, reference_image_base64) if img and img.strip()]
    text = ""
    if images:
        whole = max(1, int(deadline - time.monotonic()))
        limit = vision_timeout or settings.AI_VISION_PRIMARY_TIMEOUT
        # 给文本分析链至少预留一小段预算，避免视觉提取吃满整个超时
        vision_cap = max(10, whole - 60)
        # 视觉只做简单识图提字（小输出、快、稳）
        text = _vision_extract_text(
            images,
            instruction,
            max(1, min(limit, vision_cap, whole)),
            model=model,
            base_url=base_url,
            api_key=api_key,
        ) or ""
    left = max(5, int(deadline - time.monotonic()))
    # 自动检测：英语→整篇精读；数学/408→标准详细解析
    return analyze_english(
        [], text or "", standard_tags=standard_tags, instruction=instruction, timeout=left
    )


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


# 多图提文字：每批张数。批太大会拖慢单次响应并降低逐图识别精度，故分批串行。
VISION_BATCH_SIZE = 3


def vision_extract_text_multi(
    images: List[str],
    instruction: str = "",
    timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """多图按顺序提取文字并合并为一段文本（供「先提文字 → 再文本分析」链路）。

    按 VISION_BATCH_SIZE 分批串行调用：既不会把小图拼成超大请求（避免超时/空返回），
    又保留图片顺序，便于后续 AI 按原顺序理解材料。逐批失败不整体中断，
    只记录哪几张没识别出来，尽量保住已识别内容。
    """
    cleaned = [str(img or "").strip() for img in (images or []) if str(img or "").strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return _vision_extract_text(
            cleaned,
            instruction=instruction,
            timeout=timeout,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )

    chunks: List[str] = []
    failures: List[str] = []
    total = len(cleaned)
    for start in range(0, total, VISION_BATCH_SIZE):
        batch = cleaned[start : start + VISION_BATCH_SIZE]
        label = (
            f"第{start + 1}张"
            if len(batch) == 1
            else f"第{start + 1}-{start + len(batch)}张"
        )
        try:
            text = _vision_extract_text(
                batch,
                instruction=instruction,
                timeout=timeout,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
        except Exception:
            text = ""
        if text and text.strip():
            chunks.append(f"【{label}】\n{text.strip()}")
        else:
            failures.append(label)

    if failures:
        chunks.append("（以下图片未能识别出文字：" + "、".join(failures) + "）")
    return "\n\n".join(chunks).strip()


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
    return normalize_grade(_chat_json(messages, max_tokens=6000))
