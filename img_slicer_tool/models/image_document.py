from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QPixmap


@dataclass(slots=True)
class ImageDocument:
    path: str
    original_width: int
    original_height: int
    preview_width: int
    preview_height: int
    scale_x: float
    scale_y: float
    preview_pixmap: QPixmap
