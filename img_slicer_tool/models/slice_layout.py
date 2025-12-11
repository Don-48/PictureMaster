from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class SliceLayout:
    """保存预览坐标系下的切图线布局。"""

    horizontal_lines: List[float] = field(default_factory=list)
    vertical_lines: List[float] = field(default_factory=list)

    def normalize(self, preview_width: int, preview_height: int) -> None:
        """去重并过滤无效线条。"""
        self.horizontal_lines = sorted({y for y in self.horizontal_lines if 0 < y < preview_height})
        self.vertical_lines = sorted({x for x in self.vertical_lines if 0 < x < preview_width})

    def get_boundaries(
        self,
        preview_width: int,
        preview_height: int,
    ) -> Tuple[List[float], List[float]]:
        """返回含边界的坐标列表。"""
        self.normalize(preview_width, preview_height)

        xs = [0.0] + self.vertical_lines + [float(preview_width)]
        ys = [0.0] + self.horizontal_lines + [float(preview_height)]
        return xs, ys
