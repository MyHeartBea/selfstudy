"""英语整篇精读链路（从 ai_service 拆出，降低单文件复杂度）。

拆分原则：
- 这里只放"英语整篇"相关的 prompt 与分析流程（含 MIME 推测、OCR 分段、逐句拆解）；
- 底层能力（_chat/_chat_json/settings/logger/normalize_parsed）仍在 ai_service，
  通过 `_svc()` **在调用时**惰性取模块对象 —— 这样测试里
  `patch.object(ai_service, "_chat", ...)` 依然生效（模块属性运行时可改，
  而 `from ... import _chat` 会把名字固化，patch 就失效了）。
- 本模块自带 _clean_items / normalize_english_parsed（原就在英语链路里）；
  ai_service 会再导出它们，保持既有调用点不变。
"""

import logging
import re
import time
from typing import List

# 本模块自己持有 logger，但与 ai_service 归到同一个 logger 名下（"kaoyan.ai"），
# 日志格式与级别统一。
logger = logging.getLogger("kaoyan.ai")


def _svc():
    """惰性拿到 ai_service 模块对象（避免循环导入，且让 patch 生效）。"""
    from app.services import ai_service

    return ai_service


def _err():
    """惰性取 AiRequestError（定义在 ai_service，避免顶层循环导入）。"""
    return _svc().AiRequestError


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


def _strip_section_markers(text: str) -> str:
    """去掉识图阶段留下的【原文】/【题目】小标题行，避免存进数据库。"""
    lines = [ln for ln in str(text or "").split("\n") if not _SECTION_MARK_RE.match(ln.strip())]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def normalize_english_parsed(parsed: dict, fallback_text: str = "") -> dict:
    """规整英语整篇解析结果：保留标准错题字段，并挂上英语附加内容与多题。"""
    if not isinstance(parsed, dict):
        parsed = {}
    is_english = bool(parsed.get("is_english"))
    base = _svc().normalize_parsed(parsed, fallback_text)
    base["is_english"] = is_english
    base["passage_text"] = _strip_section_markers(parsed.get("passage") or "")
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
            qq = _svc().normalize_parsed(q)
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
    head = (
        "请把这几张图片里的文字**原样、完整**提取出来（保留段落与换行），只输出文字本身，不要解释、不要翻译、不要总结。\n"
        "重要：\n"
        "1. 标题、正文、题目、选项都要提取，**一个字都不能漏**；\n"
        "2. 不要改写、不要润色、不要补全你没看清的内容；看不清就按原样输出你能看到的字符；\n"
        "3. 如果是试卷/文章，请用 `【原文】` 和 `【题目】` 两个小标题把「文章正文」与「题目+选项」分开；\n"
        "4. 数学公式用 LaTeX（$...$）表示；\n"
        "5. **不要输出水印、页码、机构名、公众号/小红书号、二维码说明等无关文字**"
        "（例如“小红书号：xxx”“扫码关注”“第 3 页 共 10 页”这类都不要）。"
    )
    if instruction and instruction.strip():
        head += "\n\n【补充要求】" + instruction.strip()
    content.append({"type": "text", "text": head})
    for img in images:
        data_url = img.strip()
        if not data_url.startswith("data:"):
            data_url = f"data:{_guess_mime(data_url)};base64," + data_url
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    result, meta = _svc()._chat(
        [{"role": "user", "content": content}],
        model=model or _svc().settings.AI_VISION_DS_MODEL,
        base_url=base_url,
        api_key=api_key,
        # 识图必须给足预算：deepseek-flash 是推理模型，实测单次识图会先花掉
        # ~12000 reasoning tokens，若只给 4000/8000，正文会在中途被静默截断，
        # 表现为"英语原文只识出一两段"。这里给 16000（_chat 还会再乘推理余量，
        # 并在真被截断时翻倍重试）。
        max_tokens=16000,
        timeout=timeout,
        with_meta=True,
    )
    text = str(result or "").strip()
    if meta.get("truncated"):
        # _chat 已翻倍重试过仍被截断：必须让上层知道，否则会拿残缺原文去做分析
        # ——表现就是"英语原文只识出一两段、题目和原文错位"。
        logger.warning(
            "识图结果疑似被截断（已提取 %d 字，finish_reason=%s）",
            len(text),
            meta.get("finish_reason"),
        )
    return text


_SECTION_MARK_RE = re.compile(
    r"^\s*[【\[]\s*(原文|文章|正文|passage|text)\s*[】\]]\s*$"
    r"|^\s*[【\[]\s*(题目|问题|试题|选项|questions?)\s*[】\]]\s*$",
    re.I,
)


def _split_ocr_sections(text: str) -> tuple:
    """把识图文本按【原文】/【题目】小标题拆成 (文章正文, 题目与选项)。

    为什么必须拆：不拆的话整页（文章＋题干＋选项）会被当成"原文"送进精读，
    阅读模型会去翻译题目、题目环节再靠 AI 重写题干 —— 实测表现就是
    "题目与给出的题目完全不一致、原文里混着选项"。
    拆开之后：阅读/翻译/逐句只看文章，题目清单只看题目部分，题干原样保留。

    识别不到小标题时退化为 (全文, 全文)，保持旧行为不倒退。
    """
    raw = str(text or "")
    lines = raw.split("\n")
    passage: List[str] = []
    questions: List[str] = []
    mode = "passage"
    seen_mark = False
    for line in lines:
        m = _SECTION_MARK_RE.match(line.strip())
        if m:
            seen_mark = True
            # 命中【原文】类标题 → 之后进文章；命中【题目】类标题 → 之后进题目
            mode = "passage" if m.group(1) else "questions"
            continue
        (passage if mode == "passage" else questions).append(line)

    if not seen_mark:
        return raw.strip(), raw.strip()
    body = "\n".join(passage).strip()
    quiz = "\n".join(questions).strip()
    if not body:
        # 只有题目没有正文（例如只截了题目页）→ 两边都用题目，保证不丢内容
        return quiz, quiz
    return body, (quiz or body)


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
        "【定位】要指明原文具体句（如“第二段第二句”）并引用关键词，禁止只写“全文”；"
        "【来源】写明哪年真题/哪篇哪题；"
        "【思路】用通顺自然语言详细讲清推理与排除过程（可自然分段或“第一/第二”，但不要用 1.1/1.2 编号）；"
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
        "题干与选项里的数学/LaTeX 表达式用 $...$ 包裹。\n"
        "**题干与选项必须原样照抄用户给出的文字**：严禁改写、精简、翻译或自行编造题目；"
        "用户给了几道题就输出几道，不要增减。只有解析（analysis）需要你自己撰写。"
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
    deadline = time.monotonic() + (timeout or _svc().settings.AI_TIMEOUT)

    def _remaining(minimum: int = 5) -> int:
        return max(minimum, int(deadline - time.monotonic()))

    images = [img for img in (image_base64_list or []) if img and img.strip()]
    source_text = text.strip()
    if images:
        whole = max(1, int(deadline - time.monotonic()))
        limit = vision_timeout or _svc().settings.AI_VISION_PRIMARY_TIMEOUT
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
        raise _err()("未能从图片或文本中获取到内容")

    # 把「文章正文」与「题目+选项」拆开：混在一起会让阅读模型去翻译题目、
    # 题目环节再靠 AI 重写题干（实测就是"题目与给的不一致、原文里混着选项"）。
    passage_text, quiz_text = _split_ocr_sections(source_text)

    # ① 阅读/翻译/句子拆解 + 是否英语（只看文章正文，不带题目与选项）
    reading = _svc()._chat_json(
        [
            {"role": "system", "content": _parse_english_reading_prompt(standard_tags)},
            {"role": "user", "content": passage_text},
        ],
        max_tokens=8000,
        timeout=_remaining(),
    )
    if not reading.get("is_english"):
        return _svc()._analyze_standard_content(
            [], source_text, standard_tags, instruction, timeout=_remaining()
        )

    # ②+③清单 并行波次：重点短语/生词 与 题目清单互不依赖，同时请求。
    # 每步输出规格（prompt/max_tokens）与串行版一致；失败各自兜底，不互相阻塞。
    def _vocab_task() -> dict:
        try:
            return _svc()._chat_json(
                [
                    {"role": "system", "content": _parse_english_vocab_prompt()},
                    {"role": "user", "content": passage_text},
                ],
                max_tokens=8000,
                timeout=_remaining(),
            )
        except Exception:
            return {}

    # 题目环节只喂题目与选项；原文仅供参考定位
    user_req = f"【原文】\n{passage_text}\n\n【题目与选项】\n{quiz_text}"
    if instruction and instruction.strip():
        user_req += f"\n\n【要求】{instruction.strip()}"

    def _titles_task() -> list:
        # 先列题目清单（小、稳），逐题解析放下一波并发
        try:
            titles = _svc()._chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是考研英语阅读助手。用户会给你【题目与选项】原文，请**逐题照抄**成严格 JSON（不要 Markdown）：\n"
                            '{"questions": [{"question": "题干", "option_a": "...", "option_b": "...", '
                            '"option_c": "...", "option_d": "...", "correct_answer": "单字母或参考答案文本"}]}\n'
                            "**必须遵守**：\n"
                            "1. question 与 option_* 要**原样照抄**用户给的文字，禁止改写、翻译、润色或自行编题；\n"
                            "2. 用户给了几道题就输出几道，不要多也不要少；选项缺失就留空串；\n"
                            "3. 只列题目与答案，不要写解析；选择题 correct_answer 只能填单个字母；\n"
                            "4. 用户没给答案时，correct_answer 留空串，**不要猜**。"
                        ),
                    },
                    {"role": "user", "content": user_req},
                ],
                max_tokens=2500,
                timeout=_remaining(),
            )
            return titles.get("questions") or []
        except Exception:
            return []

    # ② 词汇与题目清单：两件事互不依赖，**真正并发**执行。
    #    注意不能写成 `executor.submit(fn).result()` —— 那等于"提交后立刻阻塞等结果"，
    #    第二个任务要等第一个跑完才提交，实际完全串行（原实现即如此，与注释不符）。
    _executor = _svc()._ANALYSIS_EXECUTOR
    future_vocab = _executor.submit(_vocab_task)
    future_titles = _executor.submit(_titles_task)
    vocab = future_vocab.result()
    questions_items = future_titles.result()

    # ③ 逐题完整分析：并发执行（单题输出小，不易漏逗号；结果按清单顺序归位）
    todo = [q for q in questions_items if isinstance(q, dict) and q.get("question")]

    def _qa_task(q: dict) -> dict:
        opts = " ".join(
            str(q.get(k) or "") for k in ("option_a", "option_b", "option_c", "option_d")
        )
        try:
            return _svc()._chat_json(
                [
                    {"role": "system", "content": _parse_english_questions_prompt(standard_tags)},
                    {
                        "role": "user",
                        "content": (
                            "题目："
                            + str(q.get("question"))
                            + "\n选项："
                            + opts
                            + "\n答案："
                            + str(q.get("correct_answer") or "")
                            + "\n\n请按 JSON 输出（仅这一题，含题干/选项/答案/解析/难度/标签）。"
                        ),
                    },
                ],
                max_tokens=3000,
                timeout=_remaining(),
            )
        except Exception:
            # 单题分析失败时保留该题清单信息兜底，不影响其它题
            return q

    # 逐题并发：同样先全部提交、再统一收集，才是真并发
    _q_futures = [_executor.submit(_qa_task, q) for q in todo]
    full_questions = [f.result() for f in _q_futures]

    if not full_questions:
        # 兜底：整篇一次性出题。这里返回的 qa 自身可能带 questions 数组，
        # **只在兜底分支**并入后续列表 —— 正常路径下模型按系统提示也可能回带
        # questions（第 2 题起），若无条件并入就会让第 2..N 题重复出两次。
        qa = _svc()._chat_json(
            [
                {"role": "system", "content": _parse_english_questions_prompt(standard_tags)},
                {"role": "user", "content": user_req},
            ],
            max_tokens=6000,
            timeout=_remaining(),
        )
        nested = [q for q in (qa.get("questions") or []) if isinstance(q, dict)]
        full_questions = [qa] + nested

    qa = full_questions[0] if full_questions else {}
    # 顶层保留第一题，其余题目进 english_questions。
    # 顶层自身残留的 questions 用已并入的列表覆盖，避免重复。
    qa["questions"] = full_questions[1:] if full_questions else []

    # 组装完整结构
    qa["is_english"] = True
    qa["subject_hint"] = "英语"
    qa["passage"] = passage_text
    qa["passage_translation"] = reading.get("passage_translation", "")
    qa["sentences"] = reading.get("sentences", [])
    qa["phrases"] = vocab.get("phrases", [])
    qa["words"] = vocab.get("words", [])
    return normalize_english_parsed(qa, fallback_text=source_text)
