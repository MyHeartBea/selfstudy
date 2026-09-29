r"""LaTeX/数学定界符归一化（自 ai_service 拆出）。

DeepSeek 等模型常输出 \( \) / \[ \] 标准语法，而本项目 KaTeX 渲染约定
$...$ / $$...$$；`_wrap_math` 是所有 AI 产出文本（解析/总结/批改）的统一出口。
纯函数、零依赖，database.py 等外部引用经 ai_service re-export 保持不变。
"""

import re
from typing import List

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
