"""填空题答案判断：规范化、别名匹配与数值容差。"""

import re
import unicodedata
from typing import List, Optional


PUNCTUATION = set("，。；：、！？“”‘’（）()【】[]《》〈〉·…—")
NUMERIC_RE = re.compile(r"^[+-]?(\d+(\.\d+)?|\.\d+)([eE][+-]?\d+)?$")


def normalize_answer(value: str) -> str:
    """把答案统一为可比较形式：半角、小写、去空白和常见标点。"""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(ch for ch in text if ch not in PUNCTUATION)
    text = re.sub(r"\s+", "", text).lower()
    return text


def is_numeric(text: str) -> bool:
    return bool(NUMERIC_RE.match(text.strip()))


def answers_match(
    user_answer: str,
    expected: str,
    aliases: Optional[List[str]] = None,
    tolerance: float = 1e-3,
) -> bool:
    """判断用户答案是否与标准答案或其别名一致。"""
    user_text = normalize_answer(user_answer)
    if not user_text:
        return False

    if isinstance(aliases, str):
        aliases = [item.strip() for item in aliases.split(";;") if item.strip()]
    candidates = [expected or ""] + list(aliases or [])
    for candidate in candidates:
        if normalize_answer(candidate) == user_text:
            return True

    if is_numeric(user_text):
        try:
            user_value = float(user_text)
        except ValueError:
            return False
        for candidate in candidates:
            candidate_text = normalize_answer(candidate)
            if not is_numeric(candidate_text):
                continue
            try:
                if abs(user_value - float(candidate_text)) <= tolerance:
                    return True
            except ValueError:
                continue
    return False


def judge_fill(
    user_answer: str,
    expected: str,
    aliases: Optional[List[str]] = None,
) -> dict:
    """返回填空题判断结果。"""
    correct = answers_match(user_answer, expected, aliases)
    return {
        "correct": correct,
        "user_answer": user_answer,
        "expected": expected or "",
        "aliases": aliases or [],
        "normalized_user": normalize_answer(user_answer),
    }
