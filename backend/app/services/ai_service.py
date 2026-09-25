"""AI 服务层：调用 OpenAI 兼容的 chat/completions 接口。"""

import http.client
import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import List

from app import metrics
from app.config import settings

logger = logging.getLogger("kaoyan.ai")


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
    with_meta: bool = False,
    thinking: bool = True,
):
    """调用对话补全。默认返回纯文本；with_meta=True 时返回 (文本, 元信息)。

    本函数是 `_chat_request` 的**记账外壳**：一次调用恰好一条通道统计（成功与失败
    都记），供 `/api/health` 的 `metrics.ai` 使用。放在这一层而不是 `_post_chat`，
    是因为统计口径要等于"这个通道交付一份结果花了多久"（含内部的重试与翻倍）。
    空正文也按失败计 —— 它正是 `deepseek-flash` 推理吃光预算后的可见症状。

    `thinking=False` 见 `_chat_request`：只给机械性任务（照抄/抽取）用。
    """
    model_name = model or settings.AI_MODEL
    endpoint = base_url or settings.AI_BASE_URL
    started = time.perf_counter()
    try:
        content, meta = _chat_request(
            messages,
            timeout=timeout,
            model=model,
            base_url=base_url,
            api_key=api_key,
            response_format=response_format,
            max_tokens=max_tokens,
            thinking=thinking,
        )
    except AiNotConfigured:
        # 一个请求都没发出去，不算通道故障，记进 by_model 只会掩盖真问题
        raise
    except Exception as exc:
        metrics.record_ai(
            model_name,
            endpoint,
            (time.perf_counter() - started) * 1000,
            ok=False,
            error=str(exc),
        )
        raise
    empty = not (content or "").strip()
    metrics.record_ai(
        model_name,
        endpoint,
        (time.perf_counter() - started) * 1000,
        ok=not empty,
        truncated=bool(meta.get("truncated")),
        reasoning_tokens=int(meta.get("reasoning_tokens") or 0),
        completion_tokens=int(meta.get("completion_tokens") or 0),
        prompt_tokens=int(meta.get("prompt_tokens") or 0),
        cache_hit_tokens=int(meta.get("cache_hit_tokens") or 0),
        error=""
        if not empty
        else f"输出为空（finish_reason={meta.get('finish_reason') or '未知'}）",
    )
    if with_meta:
        return content, meta
    return content


def _chat_request(
    messages: List[dict],
    timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    response_format: dict | None = None,
    max_tokens: int | None = None,
    thinking: bool = True,
) -> tuple[str, dict]:
    """真正的对话补全请求，恒定返回 `(文本, 元信息)`。

    **输出预算是"正文 + 推理"的总额**：`deepseek-flash` 是推理模型，会先花掉一段
    reasoning_tokens 再产出正文。若只按"正文长度"给 max_tokens，预算会被推理吃光
    → finish_reason=length、content 为空或**被静默截断**（识图提字最容易被截，
    表现为"原文只识出一两段"）。

    所以这里统一处理两件事：
    1. 实际下发 `max_tokens` 时乘上 1.5 倍推理余量；
    2. 一旦 finish_reason=length（被截断），**自动翻倍预算重试**，最多重试 3 轮。
    这样所有调用方（含 `_vision_extract_text`）都不必各自记得处理截断。

    `thinking=False` 时显式关闭推理（`thinking: {type: "disabled"}`，实测该端点支持）：
    **只给"机械性任务"用** —— 照抄转录、按固定 schema 抽取，这类任务推理不产生价值。
    实测同一任务：推理 0 / 输出 19 token（开着推理是 168 / 188），输出质量一致。
    关掉推理后**同时取消 1.5 倍推理余量** —— 没有推理就不需要为它留预算，
    否则会白白把 max_tokens 放大 1.5 倍（进而按更大的 max_tokens 计费）。
    """
    if not is_configured():
        raise AiNotConfigured()
    url = (base_url or settings.AI_BASE_URL).rstrip("/") + "/chat/completions"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    if thinking:
        budget = int(max_tokens * _REASONING_TOKEN_HEADROOM) if max_tokens else None
    else:
        # 没有推理，就不留推理余量
        budget = max_tokens
    attempts = 4
    last_meta: dict = {}

    for attempt in range(attempts):
        payload = {
            "model": model or settings.AI_MODEL,
            "messages": messages,
            "temperature": 0.2,
        }
        if not thinking:
            payload["thinking"] = {"type": "disabled"}
        if response_format is not None:
            payload["response_format"] = response_format
        if budget is not None:
            payload["max_tokens"] = min(MAX_TOKENS_CEILING, budget)

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key or settings.AI_API_KEY}",
            },
            method="POST",
        )
        data = _post_chat(opener, request, timeout)
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            raise AiRequestError("AI 服务响应格式异常") from exc

        message = choice.get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage") or {}
        last_meta = {
            "finish_reason": choice.get("finish_reason") or "",
            "reasoning_tokens": int(
                (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            ),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            # 前缀缓存：命中部分约 1/10 价。记下来才能在 /api/health 看到命中率，
            # 否则"缓存有没有生效"只能靠猜。
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "cache_hit_tokens": int(usage.get("prompt_cache_hit_tokens") or 0),
            "has_reasoning": bool(message.get("reasoning_content")),
            "requested_max_tokens": budget,
            "truncated": False,
        }

        # 被预算截断 → 加大预算重试（最后一轮就把截断结果交出去，由调用方决定）
        if last_meta["finish_reason"] == "length" and attempt < attempts - 1:
            last_meta["truncated"] = True
            logger.warning(
                "AI 输出被截断（finish_reason=length，推理 %s tokens，预算 %s）→ 翻倍重试",
                last_meta["reasoning_tokens"],
                budget,
            )
            budget = min(MAX_TOKENS_CEILING, (budget or 4000) * 2)
            continue

        last_meta["truncated"] = last_meta["finish_reason"] == "length"
        return content, last_meta

    return "", last_meta


def _post_chat(opener, request, timeout: int | None) -> dict:
    """单次 HTTP 调用（含网络层重试），返回解析后的响应体。"""
    last_message = ""
    for attempt in range(4):
        try:
            with opener.open(
                request,
                timeout=timeout or settings.AI_TIMEOUT,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
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
    raise AiRequestError(last_message or "AI 调用失败")


# 推理模型（deepseek-flash）会先花掉一段 reasoning_tokens 再产出正文。
# 若 max_tokens 只按"输出正文"估算，预算会被推理吃光 → finish_reason=length、
# content 为空或被静默截断（实测 12000 预算里有 11998 是 reasoning_tokens，正文 0 字）。
# 余量与"截断就翻倍重试"的逻辑统一放在 `_chat` 里，所有调用方自动受益。
_REASONING_TOKEN_HEADROOM = 1.5

# 单次调用的 max_tokens 上限
MAX_TOKENS_CEILING = 64000


def _json_chat_budget(max_tokens: int | None) -> int:
    """JSON 调用的基础预算（`_chat` 会再乘推理余量并处理截断重试）。"""
    return int(max_tokens or 8000)


def _chat_json(messages: List[dict], attempts: int = 3, **kwargs) -> dict:
    """调用 AI 并解析严格 JSON。空内容/畸形都算失败并重试（最多 3 次）。

    截断（finish_reason=length）已由 `_chat` 内部翻倍预算重试处理；这里再兜一层：
    若最终仍是被截断的 JSON（`_extract_json` 无法修复），当作失败重试。
    """
    last = None
    budget = _json_chat_budget(kwargs.pop("max_tokens", None))
    for i in range(max(1, attempts)):
        content, meta = _chat(messages, max_tokens=budget, with_meta=True, **kwargs)
        if content is None or not str(content).strip():
            reason = meta.get("finish_reason") or "未知"
            if reason == "length":
                last = ValueError(
                    f"输出预算被耗尽（finish_reason=length，推理用了 "
                    f"{meta.get('reasoning_tokens')} tokens）"
                )
                budget = min(MAX_TOKENS_CEILING, max(budget * 2, 8000))
            else:
                last = ValueError(f"AI 返回内容为空（finish_reason={reason}）")
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
        '"option_d": "...", "option_e": "...", "option_f": "...", "option_g": "...", '
        '"correct_answer": "选择题填 A/B/C/D/E/F/G 单个字母，其他题型填参考答案文本", "analysis": "详细解析", '
        '"difficulty": 1-5 的整数, "difficulty_points": "这道题的主要难点简析", '
        '"knowledge_tags": ["标签1", "标签2"], '
        '"approach": "解题思路", "source": "来源备注", '
        '"source_type": "real_exam/mock/other", '
        '"source_year": "如 2025", "source_name": "如 李林六套卷(一)", '
        '"subject_hint": "数学/英语/408/政治"}\n'
        "question_type 只能输出三个值之一：choice/fill/solution，根据题目形式判断："
        "有选项（A/B/C/D，英语七选五可能到 E/F/G）选 choice，只要求填数值或结果的选 fill，"
        "需要写完整过程或证明的选 solution。"
        "选择题的 correct_answer 只能填单个字母 A-G，不要填多个字母，"
        "也不要写“ABCD”或“A、B”；四个选项各自只填该选项自己的内容，"
        "不要把题干或全部选项重复填进每个选项；没有 E/F/G 选项时对应字段填空字符串。"
        "如果某个选项缺失，填空字符串即可；如果无法确定正确答案，"
        "给出最可能的答案并在解析中说明。source_type：真题填 real_exam 并填写年份，"
        "模拟题填 mock 并填写年份和卷名，其他填 other。\n"
        "**题干与选项必须原样照抄用户给的内容**（只允许做一件事：把数学表达式用 $...$ 或 $$...$$ 包起来）："
        "严禁改写、精简、润色、重新表述或自行编造题干与选项；"
        "看不清或缺失的部分保留原样，宁可留着也不要猜。"
        "用户给了几道题就输出几道，不要增减题目。\n"
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
            "不要新增近似叫法：" + "、".join(standard_tags[:40])
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
    raise last_error if last_error is not None else json.JSONDecodeError("无效 JSON", content, 0)


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
                out.append("$" + content + "$" if _looks_like_math(content) else content)
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
                    out.append("$" + content + "$" if _looks_like_math(content) else content)
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
                out.append("$" + content + "$" if _looks_like_math(content) else content)
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
        text = re.sub(r"^\s*[A-Ga-g]\s*[\.、．:：)]\s*", "", text)
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
            for key in (
                "option_a",
                "option_b",
                "option_c",
                "option_d",
                "option_e",
                "option_f",
                "option_g",
            )
        )
        question_type = "choice" if has_options else "fill"

    option_keys = (
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "option_e",
        "option_f",
        "option_g",
    )
    option_values = [as_option(parsed.get(key)) for key in option_keys]
    non_empty_options = [value for value in option_values if value]
    if len(non_empty_options) >= 2 and len(set(non_empty_options)) == 1:
        option_values = ["" for _ in option_keys]

    correct = as_text(parsed.get("correct_answer"))
    if question_type == "choice":
        letters = re.findall(r"[A-G]", correct.upper())
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
        source_type = "real_exam" if "真题" in source else "mock" if "模拟" in source else "other"
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
        "option_e": _wrap_math(option_values[4]),
        "option_f": _wrap_math(option_values[5]),
        "option_g": _wrap_math(option_values[6]),
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
        text = f"{text}\n\n【补充要求】{instruction.strip()}" if text else instruction.strip()
    if images:
        # 先看图提取文字（快、稳），再用文本做详细分析，避免超大视觉生成超时。
        # 提字失败时保留原 text（下面的 `or text` 已兜住，无需再自赋值）
        try:
            text = _vision_extract_text(images, instruction, timeout) or text
        except Exception as exc:
            logger.warning("视觉提字失败，回退已有文本：%s", exc)
    # 没有文字依据时不能往下走：user content 一旦为空，模型会凭空编一道题、
    # 再编一份看起来合理的解析（内容不减的第 5 节约定直接落空）。
    # 目前唯一调用方 ai_english.analyze_english 已先做过同样检查，这里是第二道闸。
    if not (text or "").strip():
        raise AiRequestError("未能从图片或文本中获取到内容，请重试或直接粘贴题目文本")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
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
        text = (
            _vision_extract_text(
                images,
                instruction,
                max(1, min(limit, vision_cap, whole)),
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
            or ""
        )
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
        label = f"第{start + 1}张" if len(batch) == 1 else f"第{start + 1}-{start + len(batch)}张"
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


# ─────────────────────────── 兼容再导出 ───────────────────────────
# 英语整篇链路已拆到 app/services/ai_english.py（本文件从 1402 行降到 ~950 行）。
# 这里把原有名字再导出一次，保证既有调用点（routers、exam_paper_service、tests）
# 完全不用改：`from app.services import ai_service; ai_service.analyze_english(...)` 照旧可用。
from app.services.ai_english import (  # noqa: E402,F401
    _clean_items,
    _guess_mime,
    _parse_english_prompt,
    _parse_english_questions_prompt,
    _parse_english_reading_prompt,
    _parse_english_vocab_prompt,
    _SECTION_MARK_RE,
    _split_ocr_sections,
    _strip_section_markers,
    _vision_extract_text,
    analyze_english,
    normalize_english_parsed,
)
