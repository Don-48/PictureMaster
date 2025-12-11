from __future__ import annotations

from typing import List, Tuple

from models.image_document import ImageDocument
from models.slice_layout import SliceLayout

"""图像相关的数学工具函数模块。

后续将放置：
- 预览坐标 <-> 原图坐标 映射
- 宫格线位置计算
- 边界裁剪与安全校验 等
"""


def preview_rect_to_original_box(
    doc: ImageDocument,
    x: float,
    y: float,
    w: float,
    h: float,
) -> Tuple[int, int, int, int]:
    """将预览图坐标系矩形映射到原图裁剪 box。"""

    if w <= 0 or h <= 0:
        raise ValueError("裁剪宽高必须为正数")

    x1_preview = x
    y1_preview = y
    x2_preview = x + w
    y2_preview = y + h

    x1 = int(round(x1_preview * doc.scale_x))
    y1 = int(round(y1_preview * doc.scale_y))
    x2 = int(round(x2_preview * doc.scale_x))
    y2 = int(round(y2_preview * doc.scale_y))

    x1 = max(0, min(x1, doc.original_width))
    x2 = max(0, min(x2, doc.original_width))
    y1 = max(0, min(y1, doc.original_height))
    y2 = max(0, min(y2, doc.original_height))

    if x2 <= x1 or y2 <= y1:
        raise ValueError("裁剪区域过小或无效")

    return x1, y1, x2, y2


def preview_lines_to_original_boundaries(
    doc: ImageDocument,
    layout: SliceLayout,
) -> Tuple[List[int], List[int]]:
    """将预览线布局转换为原图中的边界坐标。"""
    xs_preview, ys_preview = layout.get_boundaries(doc.preview_width, doc.preview_height)

    xs_original: List[int] = []
    for x in xs_preview:
        xo = int(round(x * doc.scale_x))
        xo = max(0, min(xo, doc.original_width))
        xs_original.append(xo)

    ys_original: List[int] = []
    for y in ys_preview:
        yo = int(round(y * doc.scale_y))
        yo = max(0, min(yo, doc.original_height))
        ys_original.append(yo)

    xs_original = sorted(set(xs_original))
    ys_original = sorted(set(ys_original))

    if len(xs_original) < 2 or len(ys_original) < 2:
        raise ValueError("切图边界不足，无法生成宫格")

    return xs_original, ys_original
