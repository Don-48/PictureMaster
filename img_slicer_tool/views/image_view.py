from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Qt, QRectF, Signal
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from models.image_document import ImageDocument
from models.slice_layout import SliceLayout
from views.overlay_items import CropRectItem, GuideLineItem


class ImageView(QGraphicsView):
    MODE_CROP = "crop"
    MODE_SLICE = "slice"

    cropRequested = Signal(float, float, float, float)

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

        self._init_view()

    def _init_view(self) -> None:
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)

    def set_document(self, document: ImageDocument) -> None:
        self._document = document
        self._scene.clear()
        self.resetTransform()
        self._current_scale = 1.0
        self._crop_rect_item = None
        self._is_dragging_crop = False
        self._drag_start_pos_scene = None

        pixmap = document.preview_pixmap
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._current_scale = 1.0

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
            for item in list(self._scene.selectedItems()):
                if isinstance(item, GuideLineItem):
                    self._scene.removeItem(item)
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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if self._is_space_pressed:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton and self._pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
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
            elif self._mode == self.MODE_SLICE:
                modifiers = event.modifiers()
                create_horizontal = False
                create_vertical = False

                if modifiers & Qt.ShiftModifier:
                    create_horizontal = True
                elif modifiers & Qt.ControlModifier:
                    create_vertical = True
                else:
                    create_horizontal = True
                    create_vertical = True

                if create_horizontal:
                    self.add_slice_line(GuideLineItem.HORIZONTAL, scene_pos.y())

                if create_vertical:
                    self.add_slice_line(GuideLineItem.VERTICAL, scene_pos.x())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
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
        """Gather GuideLineItem positions into a SliceLayout."""
        layout = SliceLayout()
        if self._pixmap_item is None:
            return layout

        pixmap_rect = self._pixmap_item.boundingRect()
        for item in self._scene.items():
            if isinstance(item, GuideLineItem):
                value = item.scene_coordinate_value()
                if item.orientation == GuideLineItem.HORIZONTAL:
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
        """在指定位置添加一条切图线。"""
        if self._pixmap_item is None:
            return
        pixmap_rect = self._pixmap_item.boundingRect()

        if orientation == GuideLineItem.HORIZONTAL:
            y = max(pixmap_rect.top(), min(position, pixmap_rect.bottom()))
            line = GuideLineItem(GuideLineItem.HORIZONTAL)
            line.setLine(pixmap_rect.left(), y, pixmap_rect.right(), y)
            self._scene.addItem(line)
        elif orientation == GuideLineItem.VERTICAL:
            x = max(pixmap_rect.left(), min(position, pixmap_rect.right()))
            line = GuideLineItem(GuideLineItem.VERTICAL)
            line.setLine(x, pixmap_rect.top(), x, pixmap_rect.bottom())
            self._scene.addItem(line)
