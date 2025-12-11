from __future__ import annotations

import os

from PIL import Image

from models.image_document import ImageDocument
from models.slice_layout import SliceLayout
from utils.image_math import preview_lines_to_original_boundaries


def slice_document_to_tiles(
    doc: ImageDocument,
    layout: SliceLayout,
    output_root_dir: str,
) -> str:
    """执行宫格切图并返回输出目录。"""

    if not os.path.exists(doc.path):
        raise FileNotFoundError(f"原始图片不存在：{doc.path}")

    if not output_root_dir:
        raise ValueError("输出根路径不能为空")

    os.makedirs(output_root_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(doc.path))[0]
    ext = os.path.splitext(doc.path)[1].lower() or ".png"

    output_dir = os.path.join(output_root_dir, base_name)
    os.makedirs(output_dir, exist_ok=True)

    xs, ys = preview_lines_to_original_boundaries(doc, layout)

    with Image.open(doc.path) as img:
        img.load()

        tile_count = 0
        for row in range(len(ys) - 1):
            y1, y2 = ys[row], ys[row + 1]
            if y2 <= y1:
                continue

            for col in range(len(xs) - 1):
                x1, x2 = xs[col], xs[col + 1]
                if x2 <= x1:
                    continue

                tile = img.crop((x1, y1, x2, y2))
                tile_count += 1
                filename = f"{base_name}_r{row+1:02d}_c{col+1:02d}{ext}"
                save_path = os.path.join(output_dir, filename)

                save_kwargs = {}
                if ext in [".jpg", ".jpeg"]:
                    save_kwargs["quality"] = 95
                    save_kwargs["subsampling"] = 0

                tile.save(save_path, **save_kwargs)

    return output_dir
