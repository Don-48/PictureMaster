from __future__ import annotations

import os
from typing import Tuple

from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from models.image_document import ImageDocument

MAX_PREVIEW_SIZE = 4000


def _calc_preview_size(width: int, height: int) -> Tuple[int, int, float]:
    if width <= MAX_PREVIEW_SIZE and height <= MAX_PREVIEW_SIZE:
        return width, height, 1.0

    ratio = min(MAX_PREVIEW_SIZE / width, MAX_PREVIEW_SIZE / height)
    preview_width = max(1, int(width * ratio))
    preview_height = max(1, int(height * ratio))
    return preview_width, preview_height, ratio


def load_image_document(path: str) -> ImageDocument:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with Image.open(path) as img:
        img.load()
        original_width, original_height = img.size

        preview_width, preview_height, ratio = _calc_preview_size(original_width, original_height)

        if ratio != 1.0:
            preview_img = img.resize((preview_width, preview_height), Image.LANCZOS)
        else:
            preview_img = img.copy()

        preview_qimage = _pil_image_to_qimage(preview_img)
        preview_pixmap = QPixmap.fromImage(preview_qimage)

    scale_x = original_width / preview_width
    scale_y = original_height / preview_height

    return ImageDocument(
        path=path,
        original_width=original_width,
        original_height=original_height,
        preview_width=preview_width,
        preview_height=preview_height,
        scale_x=scale_x,
        scale_y=scale_y,
        preview_pixmap=preview_pixmap,
    )


def _pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    if pil_image.mode == "RGB":
        data = pil_image.tobytes("raw", "RGB")
        return QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGB888)
    if pil_image.mode == "RGBA":
        data = pil_image.tobytes("raw", "RGBA")
        return QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGBA8888)

    converted = pil_image.convert("RGBA")
    data = converted.tobytes("raw", "RGBA")
    return QImage(data, converted.width, converted.height, QImage.Format.Format_RGBA8888)
