from __future__ import annotations

import os
from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, Qt, QRectF, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from models.image_document import ImageDocument
from models.slice_layout import SliceLayout
from views.overlay_items import CropRectItem, GuideLineItem

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
LINE_SELECTION_TOLERANCE = 6.0


class ImageView(QGraphicsView):
    MODE_CROP = "crop"
    MODE_SLICE = "slice"

    cropRequested = Signal(float, float, float, float)
    imageDropped = Signal(str)
    invalidFileDropped = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = None
        self._document: Optional[ImageDocument] = None
        self._current_scale = 1.0
        self._is_space_pressed = False
        self._mode: str = self.MODE_CROP
        self._crop_rect_item: Optional[CropRectItem] = None
        self._is_dragging_crop = False
        self._drag_start_pos_scene: Optional[QPointF] = None
        self.sliceMode: str = "manual"
        self.lineTool: str = "cross"
        self.cutLines: List[Dict[str, object]] = []
        self._line_items: List[GuideLineItem] = []
        self._selected_line_index: Optional[int] = None
        self._grid_rows = 2
        self._grid_cols = 2
        self._last_scene_pos: Optional[QPointF] = None
        self._dragged_line_index: Optional[int] = None

        self._init_view()
        self.setAcceptDrops(True)

    def _init_view(self) -> None:
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)

    def set_document(self, document: ImageDocument) -> None:
        self._document = document
        self.clear_cut_lines()
        self._scene.clear()
        self.resetTransform()
        self._current_scale = 1.0
        self._crop_rect_item = None
        self._is_dragging_crop = False
        self._drag_start_pos_scene = None
        self._last_scene_pos = None

        pixmap = document.preview_pixmap
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._current_scale = 1.0

        if self._mode == self.MODE_SLICE and self.sliceMode == "grid":
            self._regenerate_grid_lines()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.1 if event.angleDelta().y() > 0 else 0.9
            self._current_scale *= factor
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key_Space and not self._is_space_pressed:
            self._is_space_pressed = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif event.key() == Qt.Key_Delete:
            if self._mode == self.MODE_SLICE and self.sliceMode == "manual":
                if self._selected_line_index is not None:
                    self._remove_line_at(self._selected_line_index)
                    return
        elif event.key() == Qt.Key_H:
            if self._handle_hotkey_line(GuideLineItem.HORIZONTAL):
                return
        elif event.key() == Qt.Key_V:
            if self._handle_hotkey_line(GuideLineItem.VERTICAL):
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key_Space:
            self._is_space_pressed = False
            self.setDragMode(QGraphicsView.NoDrag)
        super().keyReleaseEvent(event)

    def set_mode(self, mode: str) -> None:
        if mode not in (self.MODE_CROP, self.MODE_SLICE):
            return
        self._mode = mode
        if self._crop_rect_item is not None:
            self._scene.removeItem(self._crop_rect_item)
            self._crop_rect_item = None
        self._is_dragging_crop = False
        self._drag_start_pos_scene = None
        self._dragged_line_index = None
        self._update_cursor()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._drag_contains_local_file(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._drag_contains_local_file(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        file_path = self._extract_local_file(event)
        if not file_path:
            event.ignore()
            return

        if self._is_supported_image(file_path):
            event.acceptProposedAction()
            self.imageDropped.emit(file_path)
        else:
            event.accept()
            self.invalidFileDropped.emit(file_path)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if self._is_space_pressed:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton and self._pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
            self._last_scene_pos = QPointF(scene_pos)
            pixmap_rect = self._pixmap_item.boundingRect()
            if not pixmap_rect.contains(scene_pos):
                super().mousePressEvent(event)
                return

            if self._mode == self.MODE_CROP:
                self._is_dragging_crop = True
                self._drag_start_pos_scene = QPointF(scene_pos)

                if self._crop_rect_item is not None:
                    self._scene.removeItem(self._crop_rect_item)
                    self._crop_rect_item = None

                rect = QRectF(scene_pos, scene_pos)
                self._crop_rect_item = CropRectItem(rect)
                self._scene.addItem(self._crop_rect_item)
                return

            if self._mode == self.MODE_SLICE:
                if self._handle_slice_mouse_press(scene_pos):
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        self._update_last_scene_pos(event)
        if self._mode == self.MODE_SLICE and self._dragged_line_index is not None:
            scene_pos = self.mapToScene(event.pos())
            self._drag_selected_line(scene_pos)
            return

        if (
            self._mode == self.MODE_CROP
            and self._is_dragging_crop
            and self._crop_rect_item is not None
            and self._drag_start_pos_scene is not None
        ):
            scene_pos = self.mapToScene(event.pos())
            if self._pixmap_item is not None:
                pixmap_rect = self._pixmap_item.boundingRect()
                scene_pos.setX(max(pixmap_rect.left(), min(scene_pos.x(), pixmap_rect.right())))
                scene_pos.setY(max(pixmap_rect.top(), min(scene_pos.y(), pixmap_rect.bottom())))

            rect = QRectF(self._drag_start_pos_scene, scene_pos).normalized()
            self._crop_rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if self._mode == self.MODE_SLICE and self._dragged_line_index is not None:
            if event.button() == Qt.LeftButton:
                self._dragged_line_index = None
                self._update_cursor()
            return

        if (
            self._mode == self.MODE_CROP
            and self._is_dragging_crop
            and event.button() == Qt.LeftButton
        ):
            self._is_dragging_crop = False

            if self._crop_rect_item is not None:
                rect = self._crop_rect_item.rect()
                min_size = 5.0
                if rect.width() >= min_size and rect.height() >= min_size:
                    self.cropRequested.emit(rect.x(), rect.y(), rect.width(), rect.height())

                self._scene.removeItem(self._crop_rect_item)
                self._crop_rect_item = None

            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def get_slice_layout(self) -> SliceLayout:
        """Gather cutLines[] into a SliceLayout."""
        layout = SliceLayout()
        if self._pixmap_item is None:
            return layout

        pixmap_rect = self._pixmap_item.boundingRect()
        for line in self.cutLines:
            value = float(line["pos"])
            if line["type"] == GuideLineItem.HORIZONTAL:
                if pixmap_rect.top() <= value <= pixmap_rect.bottom():
                    layout.horizontal_lines.append(value)
            else:
                if pixmap_rect.left() <= value <= pixmap_rect.right():
                    layout.vertical_lines.append(value)

        layout.normalize(int(pixmap_rect.width()), int(pixmap_rect.height()))
        return layout

    def get_pixmap_rect(self) -> Optional[QRectF]:
        """返回当前预览图的场景矩形。"""
        if self._pixmap_item is None:
            return None
        return self._pixmap_item.boundingRect()

    def add_slice_line(self, orientation: str, position: float) -> None:
        """保留旧接口：仅在手动模式添加一条切图线。"""
        self._add_manual_line(orientation, position)

    def set_slice_work_mode(self, mode: str) -> None:
        """切换切图方式（grid/manual）。"""
        if mode not in {"grid", "manual"}:
            return
        if self.sliceMode == mode:
            if mode == "grid":
                self._regenerate_grid_lines()
            return

        self.sliceMode = mode
        self.clear_cut_lines()
        if mode == "grid":
            self.set_line_tool("select")
            self._regenerate_grid_lines()
        else:
            self._set_selected_line(None)
        self._update_cursor()

    def set_line_tool(self, tool: str) -> None:
        if tool not in {"horizontal", "vertical", "cross", "select"}:
            return
        self.lineTool = tool
        self._update_cursor()

    def set_grid_size(self, rows: int, cols: int) -> None:
        self._grid_rows = max(1, rows)
        self._grid_cols = max(1, cols)
        if self.sliceMode == "grid":
            self._regenerate_grid_lines()

    def clear_cut_lines(self) -> None:
        """清空当前切割线。"""
        for item in self._line_items:
            if item.scene() is not None:
                self._scene.removeItem(item)
        self.cutLines.clear()
        self._line_items.clear()
        self._selected_line_index = None
        self._dragged_line_index = None
        self._update_cursor()

    def has_cut_lines(self) -> bool:
        return bool(self.cutLines)

    def _handle_hotkey_line(self, orientation: str) -> bool:
        if self._mode != self.MODE_SLICE or self.sliceMode != "manual":
            return False
        scene_pos = self._default_scene_pos()
        if scene_pos is None:
            return False
        position = scene_pos.y() if orientation == GuideLineItem.HORIZONTAL else scene_pos.x()
        self._add_manual_line(orientation, position)
        return True

    def _handle_slice_mouse_press(self, scene_pos: QPointF) -> bool:
        if self._try_begin_line_drag(scene_pos):
            return True

        if self.sliceMode == "grid":
            return True

        if self.lineTool == "select":
            self._select_line_near(scene_pos)
            return True

        self._handle_manual_line_tool_click(scene_pos)
        return True

    def _handle_manual_line_tool_click(self, scene_pos: QPointF) -> None:
        if self.sliceMode != "manual":
            return

        if self.lineTool in ("horizontal", "cross"):
            self._add_manual_line(GuideLineItem.HORIZONTAL, scene_pos.y())

        if self.lineTool in ("vertical", "cross"):
            self._add_manual_line(GuideLineItem.VERTICAL, scene_pos.x())

    def _add_manual_line(self, orientation: str, position: float) -> None:
        if self._pixmap_item is None or self.sliceMode != "manual":
            return
        if orientation not in (GuideLineItem.HORIZONTAL, GuideLineItem.VERTICAL):
            return

        line_value = self._clamp_position(orientation, position)
        data = {"type": orientation, "pos": line_value, "selected": False}
        item = GuideLineItem(orientation)
        self.cutLines.append(data)
        self._line_items.append(item)
        self._scene.addItem(item)
        self._update_line_geometry(len(self.cutLines) - 1)
        self._set_selected_line(None)

    def _remove_line_at(self, index: int) -> None:
        if not (0 <= index < len(self.cutLines)):
            return
        item = self._line_items.pop(index)
        if item.scene() is not None:
            self._scene.removeItem(item)
        self.cutLines.pop(index)
        self._set_selected_line(None)

    def _update_line_geometry(self, index: int) -> None:
        if self._pixmap_item is None or not (0 <= index < len(self.cutLines)):
            return
        pixmap_rect = self._pixmap_item.boundingRect()
        data = self.cutLines[index]
        value = float(data["pos"])
        value = self._clamp_position(data["type"], value)
        data["pos"] = value
        item = self._line_items[index]

        if data["type"] == GuideLineItem.HORIZONTAL:
            item.setLine(pixmap_rect.left(), value, pixmap_rect.right(), value)
        else:
            item.setLine(value, pixmap_rect.top(), value, pixmap_rect.bottom())

        self._update_line_highlight(index)

    def _update_line_highlight(self, index: int) -> None:
        if not (0 <= index < len(self.cutLines)):
            return
        highlight = bool(self.cutLines[index].get("selected"))
        self._line_items[index].set_highlighted(highlight)

    def _set_selected_line(self, index: Optional[int]) -> None:
        self._selected_line_index = index
        for idx, line in enumerate(self.cutLines):
            line["selected"] = idx == index
            self._update_line_highlight(idx)
        self._update_cursor()

    def _select_line_near(self, scene_pos: QPointF) -> bool:
        if self._pixmap_item is None:
            return False
        pixmap_rect = self._pixmap_item.boundingRect()
        best_index: Optional[int] = None
        best_distance = LINE_SELECTION_TOLERANCE

        for idx, line in enumerate(self.cutLines):
            if line["type"] == GuideLineItem.HORIZONTAL and pixmap_rect.left() <= scene_pos.x() <= pixmap_rect.right():
                distance = abs(scene_pos.y() - float(line["pos"]))
            elif line["type"] == GuideLineItem.VERTICAL and pixmap_rect.top() <= scene_pos.y() <= pixmap_rect.bottom():
                distance = abs(scene_pos.x() - float(line["pos"]))
            else:
                continue

            if distance <= best_distance:
                best_distance = distance
                best_index = idx

        self._set_selected_line(best_index)
        return best_index is not None

    def _default_scene_pos(self) -> Optional[QPointF]:
        if self._last_scene_pos is not None:
            return QPointF(self._last_scene_pos)
        if self._pixmap_item is None:
            return None
        rect = self._pixmap_item.boundingRect()
        return QPointF(rect.center())

    def _update_last_scene_pos(self, event: QMouseEvent) -> None:
        if self._pixmap_item is None:
            self._last_scene_pos = None
            return
        self._last_scene_pos = self.mapToScene(event.pos())

    def _clamp_position(self, orientation: str, value: float) -> float:
        if self._pixmap_item is None:
            return value
        rect = self._pixmap_item.boundingRect()
        if orientation == GuideLineItem.HORIZONTAL:
            return max(rect.top(), min(value, rect.bottom()))
        return max(rect.left(), min(value, rect.right()))

    def _regenerate_grid_lines(self) -> None:
        self.clear_cut_lines()
        if self._pixmap_item is None or self.sliceMode != "grid":
            return

        rect = self._pixmap_item.boundingRect()
        if self._grid_rows > 1:
            step = rect.height() / self._grid_rows
            for i in range(1, self._grid_rows):
                pos = rect.top() + step * i
                self.cutLines.append({"type": GuideLineItem.HORIZONTAL, "pos": pos, "selected": False})
                item = GuideLineItem(GuideLineItem.HORIZONTAL)
                self._line_items.append(item)
                self._scene.addItem(item)
                self._update_line_geometry(len(self.cutLines) - 1)

        if self._grid_cols > 1:
            step = rect.width() / self._grid_cols
            for j in range(1, self._grid_cols):
                pos = rect.left() + step * j
                self.cutLines.append({"type": GuideLineItem.VERTICAL, "pos": pos, "selected": False})
                item = GuideLineItem(GuideLineItem.VERTICAL)
                self._line_items.append(item)
                self._scene.addItem(item)
                self._update_line_geometry(len(self.cutLines) - 1)

    def _try_begin_line_drag(self, scene_pos: QPointF) -> bool:
        if self._pixmap_item is None:
            return False
        hit_index = self._find_line_index_near(scene_pos)
        if hit_index is None:
            return False
        self._set_selected_line(hit_index)
        self._dragged_line_index = hit_index
        self._update_cursor()
        return True

    def _drag_selected_line(self, scene_pos: QPointF) -> None:
        if self._dragged_line_index is None or self._pixmap_item is None:
            return
        line = self.cutLines[self._dragged_line_index]
        if line["type"] == GuideLineItem.HORIZONTAL:
            line["pos"] = self._clamp_position(GuideLineItem.HORIZONTAL, scene_pos.y())
        else:
            line["pos"] = self._clamp_position(GuideLineItem.VERTICAL, scene_pos.x())
        self._update_line_geometry(self._dragged_line_index)

    def _find_line_index_near(self, scene_pos: QPointF) -> Optional[int]:
        pixmap_rect = self.get_pixmap_rect()
        if pixmap_rect is None:
            return None
        best_index: Optional[int] = None
        best_distance = LINE_SELECTION_TOLERANCE

        for idx, line in enumerate(self.cutLines):
            if line["type"] == GuideLineItem.HORIZONTAL and pixmap_rect.left() <= scene_pos.x() <= pixmap_rect.right():
                distance = abs(scene_pos.y() - float(line["pos"]))
            elif line["type"] == GuideLineItem.VERTICAL and pixmap_rect.top() <= scene_pos.y() <= pixmap_rect.bottom():
                distance = abs(scene_pos.x() - float(line["pos"]))
            else:
                continue

            if distance <= best_distance:
                best_distance = distance
                best_index = idx

        return best_index

    def _drag_contains_local_file(self, event: QDragEnterEvent | QDragMoveEvent) -> bool:
        file_path = self._extract_local_file(event)
        return bool(file_path)

    def _extract_local_file(
        self,
        event: QDragEnterEvent | QDragMoveEvent | QDropEvent,
    ) -> Optional[str]:
        if not event.mimeData().hasUrls():
            return None
        for url in event.mimeData().urls():
            if url.isLocalFile():
                local_path = url.toLocalFile()
                if os.path.isfile(local_path):
                    return local_path
        return None

    def _is_supported_image(self, path: str) -> bool:
        _, ext = os.path.splitext(path)
        return ext.lower() in SUPPORTED_IMAGE_EXTENSIONS

    def _update_cursor(self) -> None:
        if self._mode != self.MODE_SLICE:
            self.viewport().setCursor(Qt.ArrowCursor)
            return

        if self._dragged_line_index is not None:
            self.viewport().setCursor(Qt.ClosedHandCursor)
        elif self.sliceMode == "grid" or self.lineTool == "select":
            cursor = Qt.OpenHandCursor if self._selected_line_index is not None else Qt.ArrowCursor
            self.viewport().setCursor(cursor)
        else:
            self.viewport().setCursor(Qt.CrossCursor)
