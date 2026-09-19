"""考研英语作文：手写稿视觉提字 + 按考研评分档 AI 批改。

链路遵循全项目约定「先看图提文字 → 再文本分析」：
视觉通道只做原样转录（手写稿，禁止润色），批改由文本模型完成。
"""

import json
import re
from typing import List

from app.services import ai_service

# 考研英语写作评分标准（大纲）：档位给分区间 + 一句话档描。
# key 命名：e1=英语一 e2=英语二；short=小作文(Part A) long=大作文(Part B)
ESSAY_KINDS = {
    "e1_short": {"name": "英语一 小作文（应用文）", "max": 10},
    "e1_long": {"name": "英语一 大作文（图画作文）", "max": 20},
    "e2_short": {"name": "英语二 小作文（应用文）", "max": 10},
    "e2_long": {"name": "英语二 大作文（图表作文）", "max": 15},
}

_BANDS = {
    10: [
        (9, 10, "第五档", "完全完成试题规定任务；涵盖所有要点，表达清楚、语法几乎无误"),
        (7, 8, "第四档", "覆盖所有要点，仅个别细节未展开；语言基本准确，错得不影响理解"),
        (5, 6, "第三档", "未完全完成任务，遗漏一些要点或含无关内容；有一些影响理解的语法错误"),
        (3, 4, "第二档", "未按要求写作，遗漏主要内容或含无关内容；语法错误较多，影响理解"),
        (1, 2, "第一档", "内容太少或无关，未完成任务；语法错误很多，难以理解"),
        (0, 0, "零分档", "白卷 / 完全无关 / 无法判读"),
    ],
    15: [
        (
            13,
            15,
            "第五档",
            "包含所有内容要点；运用多种语法结构与词汇，准确或偶错不影响理解；结构清晰、衔接自然",
        ),
        (
            10,
            12,
            "第四档",
            "涵盖所有要点，仅个别细节未充分展开；应用了较丰富的语法与词汇，少量错误",
        ),
        (7, 9, "第三档", "未完全完成任务，遗漏一些要点或含无关内容；有一些语法与词汇错误"),
        (4, 6, "第二档", "遗漏主要内容或未按要求写作；语法词汇错误较多，影响理解"),
        (1, 3, "第一档", "内容太少或无关，无法传达信息；语法词汇错误极多"),
        (0, 0, "零分档", "白卷 / 完全无关 / 无法判读"),
    ],
    20: [
        (
            17,
            20,
            "第五档",
            "包含所有内容要点；语法结构与词汇丰富，错误不影响理解；结构清晰、衔接自然、完全达到交际目的",
        ),
        (13, 16, "第四档", "涵盖所有要点，个别细节欠佳；语法与词汇量满足要求，偶有小错"),
        (9, 12, "第三档", "未完全完成任务，遗漏一些要点或含无关内容；有一些语法与词汇错误"),
        (5, 8, "第二档", "遗漏主要内容或未按要求写作；语法词汇错误较多，明显影响理解"),
        (1, 4, "第一档", "内容太少或基本无关，无法传达信息；语法错误极多"),
        (0, 0, "零分档", "白卷 / 完全无关 / 无法判读"),
    ],
}

_ESSAY_VISION_INSTRUCTION = (
    "图片是考生手写的英语作文答题卡（可能含题目要求印刷体）。"
    "第 1 行先输出【题目】：把试卷的作文题目/要求原样转录；找不到则写【题目】无。"
    "第 2 行起输出【正文】：**逐字原样转录考生写的每一个词**，保留原有分段与涂改痕迹（涂改后内容以最终版本为准），"
    "严禁纠正拼写、美化字迹、补全没写的内容或替你认为「本该写的」句子；看不清的单词用 [?] 占位。"
)


def _essay_prompt(max_score: int, name: str) -> str:
    band_rows = "\n".join(
        f"- {lo}-{hi} 分（{label}）：{desc}" for lo, hi, label, desc in _BANDS[max_score]
    )
    return (
        f"你是一名严格的考研英语阅卷老师，现在批改「{name}」（满分 {max_score} 分）。"
        f"该题型官方评分档如下，score 必须落在某个档的区间内：\n{band_rows}\n\n"
        "批改要求：\n"
        f"1. score 为 0-{max_score} 的整数。按下档原则：先定内容完整度与语言准确性整体印象定档，再看硬伤降档。"
        f"拼写/时态/主谓一致类小错不单独压档；出现「未覆盖题目所有要点」「字数明显不达标（小作文 <80 或大作文 <150 词）」"
        f"「chinglish 导致误解」时必须降档。满分只给几乎没有错误的卷子，不要轻易给。\n"
        "2. dimensions 四项分数之和必须等于 score。\n"
        "3. corrections 逐条列出真实错误的句子：original 必须是学生原文中的句子（可截短），不能编造；"
        "corrected 为改后句子；type 取值 语法/拼写/用词/搭配/时态/主谓一致/冠词/句式/逻辑衔接/格式；note 用中文一句话解释。\n"
        "4. overall、weakness_advice、upgrade_tips 一律中文；例句保留英文原文。\n"
        "5. model_version 按学生原作文的立意与要点，改写一篇同题范文（不是另写一题），"
        f"小作文约 100 词 / 大作文约 {160 if max_score == 20 else 150} 词，水平定为第五档上沿，可直接背诵模仿。\n"
        "6. estimated_word_count 按转录正文统计的英文词数。\n\n"
        "输出严格的 JSON（不要 Markdown）：\n"
        '{"score": 整数, "band": "第X档", "dimensions": '
        '{"content": 分数, "structure": 分数, "language": 分数, "format": 分数}, '
        '"estimated_word_count": 整数, '
        '"corrections": [{"original": "原句", "corrected": "改句", "type": "类型", "note": "中文解释"}], '
        '"highlights": ["写得好的句子或用法，中文点评"], '
        '"overall": "总评 3-4 句：定档理由 + 最大提分点", '
        '"top_errors": ["按出现次数排列的高频错误类别，最多 4 个"], '
        '"weakness_advice": "针对最薄弱两项的练法建议，2-3 句", '
        '"upgrade_tips": ["原句 + 升级后写法，格式为字符串，最多 4 条"], '
        '"model_version": "同题第五档范文"}'
    )


def _fallback_band(max_score: int, score: int) -> str:
    for lo, hi, label, _desc in _BANDS[max_score]:
        if lo <= score <= hi:
            return label
    return ""


def normalize_essay_grade(parsed: dict, kind: str) -> dict:
    """规整 AI 批改结果：分数钳制到满分、档位兜底、维度配额校验、字段类型收敛。"""
    if not isinstance(parsed, dict):
        parsed = {}
    meta = ESSAY_KINDS.get(kind) or ESSAY_KINDS["e2_long"]
    max_score = meta["max"]
    try:
        score = int(round(float(parsed.get("score") or 0)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(max_score, score))

    dims_in = parsed.get("dimensions") if isinstance(parsed.get("dimensions"), dict) else {}
    quota = {"content": 0.4, "structure": 0.2, "language": 0.3, "format": 0.1}
    dimensions = {}
    for key in quota:
        try:
            val = int(round(float(dims_in.get(key) or 0)))
        except (TypeError, ValueError):
            val = 0
        dimensions[key] = max(0, min(max_score, val))
    # AI 常把维度分给得对不上总分：偏差超过 1 分就按配额从 score 重算
    if max_score and abs(sum(dimensions.values()) - score) > 1:
        allocated = 0
        keys = list(quota)
        for i, key in enumerate(keys):
            if i < len(keys) - 1:
                dimensions[key] = int(round(score * quota[key]))
                allocated += dimensions[key]
            else:
                dimensions[key] = max(0, score - allocated)

    band = str(parsed.get("band") or "").strip()
    if not re.search(r"[一二三四五]档|零分档", band):
        band = _fallback_band(max_score, score)

    def _str_list(val):
        if isinstance(val, str):
            val = re.split(r"\n+", val)
        return [str(item).strip() for item in (val or []) if str(item or "").strip()]

    corrections = []
    for item in parsed.get("corrections") or []:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original") or "").strip()
        corrected = str(item.get("corrected") or "").strip()
        if not original:
            continue
        corrections.append(
            {
                "original": original,
                "corrected": corrected,
                "type": str(item.get("type") or "").strip(),
                "note": str(item.get("note") or "").strip(),
            }
        )

    try:
        word_count = int(parsed.get("estimated_word_count") or 0)
    except (TypeError, ValueError):
        word_count = 0

    return {
        "kind": kind,
        "kind_name": meta["name"],
        "max_score": max_score,
        "score": score,
        "band": band,
        "dimensions": dimensions,
        "estimated_word_count": max(0, word_count),
        "corrections": corrections[:30],
        "highlights": _str_list(parsed.get("highlights"))[:8],
        "overall": str(parsed.get("overall") or "").strip(),
        "top_errors": _str_list(parsed.get("top_errors"))[:4],
        "weakness_advice": str(parsed.get("weakness_advice") or "").strip(),
        "upgrade_tips": _str_list(parsed.get("upgrade_tips"))[:4],
        "model_version": str(parsed.get("model_version") or "").strip(),
    }


def extract_essay_text(
    images: List[str],
    timeout: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """手写稿图片 → 原样转录文本（走「先提文字」通道，多张按序合并）。"""
    parts: List[str] = []
    for idx, img in enumerate([i for i in (images or []) if str(i or "").strip()]):
        text = ai_service._vision_extract_text(
            [img],
            instruction=_ESSAY_VISION_INSTRUCTION,
            timeout=timeout,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
        text = str(text or "").strip()
        if text:
            parts.append(text if len(images) == 1 else f"【第{idx + 1}张】\n{text}")
    return "\n\n".join(parts).strip()


def grade_essay(
    essay_text: str,
    kind: str,
    prompt_text: str = "",
    instruction: str = "",
    timeout: int | None = None,
) -> dict:
    """按考研评分档批改作文，返回规整后的批改结构。"""
    meta = ESSAY_KINDS.get(kind)
    if not meta:
        raise ValueError(f"未知作文类型：{kind}")
    user = (
        f"作文题目：\n{prompt_text.strip() or '（未提供，按学生转录内容推断要点）'}\n\n"
        f"学生作文转录：\n{essay_text.strip()}"
    )
    if instruction and instruction.strip():
        user += f"\n\n【学生补充说明】{instruction.strip()}"
    messages = [
        {"role": "system", "content": _essay_prompt(meta["max"], meta["name"])},
        {"role": "user", "content": user},
    ]
    # 经模块属性调用：测试对 ai_service._chat_json 的打桩才能生效
    parsed = ai_service._chat_json(messages, max_tokens=6000, timeout=timeout)
    result = normalize_essay_grade(parsed, kind)
    result["raw_transcript"] = essay_text.strip()
    return result


def essay_result_json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)
