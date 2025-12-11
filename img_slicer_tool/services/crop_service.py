from __future__ import annotations

import os
from typing import Tuple

from PIL import Image

from models.image_document import ImageDocument
from services.image_loader import load_image_document
from utils.image_math import preview_rect_to_original_box


def crop_document_to_new_image(
    doc: ImageDocument,
    preview_rect: Tuple[float, float, float, float],
    target_path: str,
) -> ImageDocument:
    """基于预览矩形执行裁剪并返回新的 ImageDocument。"""

    if not doc.path or not os.path.exists(doc.path):
        raise FileNotFoundError(f"原始图片路径不存在：{doc.path}")

    x, y, w, h = preview_rect
    crop_box = preview_rect_to_original_box(doc, x, y, w, h)

    with Image.open(doc.path) as img:
        img.load()
        cropped = img.crop(crop_box)
        save_kwargs = {}
        ext = os.path.splitext(target_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            save_kwargs["quality"] = 95
            save_kwargs["subsampling"] = 0
        cropped.save(target_path, **save_kwargs)

    new_doc = load_image_document(target_path)
    return new_doc
