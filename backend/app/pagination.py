"""全站统一的分页参数钳制。

历史上 mistakes / knowledge / vocab / essay / papers 各写一份"只传 page 不传
page_size"的兜底，返回形状也各不相同（AGENTS 第 3 节"分页/搜索口径漂移"）。
这里只收敛**参数层**；响应形状维持既有约定：page 可选的端点不传 page 返回裸数组，
传了返回 `{items, total, page, page_size}` —— 前端与 docs/api.md 按这个约定写死，
不要在这里改形状。
"""

from typing import Optional, Tuple

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def resolve_pagination(
    page: Optional[int],
    page_size: Optional[int] = None,
    default_size: int = DEFAULT_PAGE_SIZE,
) -> Tuple[Optional[int], int]:
    """返回 (page, page_size)。page 为 None 表示不分页（裸数组约定）。

    page 非法（<1）时钳到 1 而不是报错：分页是浏览行为，翻过界返回空页比 422 更友好。
    """
    if page is None:
        return None, default_size
    resolved_size = page_size or default_size
    resolved_size = max(1, min(int(resolved_size), MAX_PAGE_SIZE))
    return max(1, int(page)), resolved_size
