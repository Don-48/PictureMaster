from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsRectItem


class CropRectItem(QGraphicsRectItem):
    """裁剪选择矩形：半透明填充 + 虚线边框。"""

    def __init__(self, rect: QRectF, parent=None) -> None:
        super().__init__(rect, parent)

        fill_color = QColor(0, 120, 215, 60)
        self.setBrush(QBrush(fill_color))

        pen = QPen(QColor(255, 255, 255))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        self.setPen(pen)

        self.setZValue(10)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)


class GuideLineItem(QGraphicsLineItem):
    """切图线条，支持高亮显示。"""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"

    def __init__(self, orientation: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if orientation not in (self.HORIZONTAL, self.VERTICAL):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        self.orientation = orientation

        self._apply_pen(highlighted=False)
        self.setZValue(9)
        # 自定义高亮方案，因此禁用场景级的选中/拖动行为。
        self.setFlag(QGraphicsLineItem.ItemIsMovable, False)
        self.setFlag(QGraphicsLineItem.ItemIsSelectable, False)

    def _apply_pen(self, highlighted: bool) -> None:
        pen = QPen(QColor(255, 170, 0) if highlighted else QColor(255, 0, 0))
        pen.setWidth(3 if highlighted else 1)
        pen.setStyle(Qt.SolidLine if highlighted else Qt.DashLine)
        self.setPen(pen)

    def set_highlighted(self, highlighted: bool) -> None:
        """切换线条高亮效果。"""
        self._apply_pen(highlighted)

    def scene_coordinate_value(self) -> float:
        """返回线条在场景中的关键坐标。"""
        line = self.line()
        p1 = self.mapToScene(line.p1())
        p2 = self.mapToScene(line.p2())

        if self.orientation == self.HORIZONTAL:
            return (p1.y() + p2.y()) / 2.0
        return (p1.x() + p2.x()) / 2.0
