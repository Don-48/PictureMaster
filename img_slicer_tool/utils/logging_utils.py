from __future__ import annotations

from loguru import logger

logger.add("img_slicer.log", rotation="5 MB", encoding="utf-8", enqueue=True)
