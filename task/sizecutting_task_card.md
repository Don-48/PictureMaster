````markdown
# 任务卡：实现「裁剪功能」（支持大图，基于预览坐标映射到原图）

## 任务目标

在现有项目（`img_slicer_tool`）基础上，为图片编辑工具实现**矩形裁剪功能**，要求：

1. 用户在工作区中通过**鼠标拖动**拉出矩形选择框。
2. 鼠标释放后，弹出确认对话框，用户可选择：
   - 直接**覆盖原图**；
   - **另存为**新文件；
   - 取消裁剪。
3. 裁剪操作基于当前文档的**原始大图尺寸**进行，使用**预览坐标 → 原图坐标**映射，保证支持超大图（例如 20000×20000）。
4. 裁剪完成后，重新加载为新的 `ImageDocument`，更新工作区显示，以便后续继续执行切图操作。

> 说明：本任务仅实现「矩形裁剪」的完整闭环，不涉及切图线和宫格切图。

---

## 一、前置条件检查

请确认当前项目中已经存在以下文件，并大致符合之前初始化任务约定的结构：

- `main.py`
- `app/application.py`
- `app/main_window.py`
- `views/image_view.py`
- `models/image_document.py`
- `services/image_loader.py`
- `utils/image_math.py`
- `utils/logging_utils.py`

如果文件不存在，请先按前一个「项目初始化任务卡」创建。

---

## 二、新增文件：`views/overlay_items.py`

> 用于封装裁剪矩形图元（半透明矩形 + 虚线边框）。

**操作：**

在 `views/` 目录下新建文件：`overlay_items.py`，写入以下内容：

```python
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsRectItem
from PySide6.QtGui import QPen, QBrush, QColor
from PySide6.QtCore import Qt, QRectF


class CropRectItem(QGraphicsRectItem):
    """裁剪选择矩形：半透明填充 + 虚线边框。"""

    def __init__(self, rect: QRectF, parent=None) -> None:
        super().__init__(rect, parent)

        # 半透明蓝色填充
        fill_color = QColor(0, 120, 215, 60)  # RGBA，带透明
        self.setBrush(QBrush(fill_color))

        # 白色虚线边框
        pen = QPen(QColor(255, 255, 255))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        self.setPen(pen)

        self.setZValue(10)  # 保证在图片之上显示
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
````

---

## 三、扩展模型工具：`utils/image_math.py`

> 增加「预览矩形 → 原图矩形」的映射函数。

**操作：**

打开 `utils/image_math.py`，将其替换或扩展为如下内容（如果已有注释，可保留并追加函数）：

```python
from __future__ import annotations

from typing import Tuple

from models.image_document import ImageDocument


def preview_rect_to_original_box(
    doc: ImageDocument,
    x: float,
    y: float,
    w: float,
    h: float,
) -> Tuple[int, int, int, int]:
    """
    将预览图坐标系中的矩形 (x, y, w, h) 映射为原图坐标系中的裁剪 box (left, upper, right, lower)。

    - 预览坐标单位：像素，对应 doc.preview_width / doc.preview_height。
    - 原图坐标单位：像素，对应 doc.original_width / doc.original_height。
    """

    if w <= 0 or h <= 0:
        raise ValueError("裁剪宽高必须为正数")

    # 左上和右下坐标（预览）
    x1_preview = x
    y1_preview = y
    x2_preview = x + w
    y2_preview = y + h

    # 映射到原图坐标
    x1 = int(round(x1_preview * doc.scale_x))
    y1 = int(round(y1_preview * doc.scale_y))
    x2 = int(round(x2_preview * doc.scale_x))
    y2 = int(round(y2_preview * doc.scale_y))

    # 边界裁剪，避免超出原图范围
    x1 = max(0, min(x1, doc.original_width))
    x2 = max(0, min(x2, doc.original_width))
    y1 = max(0, min(y1, doc.original_height))
    y2 = max(0, min(y2, doc.original_height))

    # 确保 left < right, upper < lower
    if x2 <= x1 or y2 <= y1:
        raise ValueError("裁剪区域过小或无效")

    return x1, y1, x2, y2
```

---

## 四、新增服务：`services/crop_service.py`

> 负责基于原图执行真实的裁剪操作，并返回新的 `ImageDocument`。

**操作：**

在 `services/` 目录下新建文件：`crop_service.py`，写入以下内容：

```python
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
    """
    基于预览矩形，在原图上执行裁剪，并保存到 target_path。
    然后重新加载为新的 ImageDocument 返回。

    :param doc: 当前文档（包含原图/预览信息）
    :param preview_rect: 预览坐标中的裁剪矩形 (x, y, w, h)
    :param target_path: 裁剪结果保存路径
    """

    if not doc.path or not os.path.exists(doc.path):
        raise FileNotFoundError(f"原始图片路径不存在：{doc.path}")

    x, y, w, h = preview_rect
    crop_box = preview_rect_to_original_box(doc, x, y, w, h)

    # 打开原图执行裁剪（此处使用 Pillow；后续可替换为 pyvips 实现大图优化）
    with Image.open(doc.path) as img:
        img.load()
        cropped = img.crop(crop_box)
        # 根据 target_path 后缀自动推断格式保存
        save_kwargs = {}
        ext = os.path.splitext(target_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            save_kwargs["quality"] = 95
            save_kwargs["subsampling"] = 0
        cropped.save(target_path, **save_kwargs)

    # 重新加载裁剪结果为新的文档
    new_doc = load_image_document(target_path)
    return new_doc
```

---

## 五、扩展模型：`models/image_document.py`

> 如果当前 `ImageDocument` 中**没有保存原始路径字段 `path`**，请确认已有；若没有，请加入。
> 若已经有，则保持不变。

**操作：**

打开 `models/image_document.py`，确认内容类似如下（如果缺少 `path` 字段，请补充）：

```python
from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtGui import QPixmap


@dataclass
class ImageDocument:
    path: str
    original_width: int
    original_height: int
    preview_width: int
    preview_height: int
    scale_x: float
    scale_y: float
    preview_pixmap: QPixmap
```

> 只要包含 `path: str` 字段即可，无需完全一致。

---

## 六、扩展视图：`views/image_view.py` —— 增加裁剪交互

> 功能：在工作区内通过鼠标拖动拉出裁剪矩形，并将裁剪矩形（预览坐标）通过信号发给主窗口。

**操作：**

1. 打开 `views/image_view.py`，在文件头部 `import` 部分增加：

```python
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from views.overlay_items import CropRectItem
```

> 如果已有 `Qt` 等导入，请合并避免重复。

2. 在 `ImageView` 类中，增加一个信号和若干成员变量：

在 `class ImageView(QGraphicsView):` 内部，开头添加：

```python
    # 在预览坐标系中发出裁剪请求信号: (x, y, w, h)
    cropRequested = Signal(float, float, float, float)
```

在 `__init__` 中，初始化后添加成员变量（在 `_init_view()` 之后或附近）：

```python
        self._crop_rect_item: CropRectItem | None = None
        self._is_dragging_crop: bool = False
        self._drag_start_pos_scene: QPointF | None = None
```

3. 修改 `mousePressEvent`：

在 `ImageView` 类中，找到 `mousePressEvent`，修改为：

```python
    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 空格拖动模式下，交给父类处理（ScrollHandDrag）
        if self._is_space_pressed:
            super().mousePressEvent(event)
            return

        # 左键开始绘制裁剪矩形
        if event.button() == Qt.LeftButton and self._pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
            # 限制在图片范围内
            pixmap_rect = self._pixmap_item.boundingRect()
            if not pixmap_rect.contains(scene_pos):
                super().mousePressEvent(event)
                return

            self._is_dragging_crop = True
            self._drag_start_pos_scene = scene_pos

            if self._crop_rect_item is not None:
                self._scene.removeItem(self._crop_rect_item)
                self._crop_rect_item = None

            rect = QRectF(scene_pos, scene_pos)
            self._crop_rect_item = CropRectItem(rect)
            self._scene.addItem(self._crop_rect_item)
        else:
            super().mousePressEvent(event)
```

4. 新增/修改 `mouseMoveEvent`：

```python
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging_crop and self._crop_rect_item is not None and self._drag_start_pos_scene is not None:
            scene_pos = self.mapToScene(event.pos())
            pixmap_rect = self._pixmap_item.boundingRect() if self._pixmap_item is not None else None

            # 限制在图片范围内
            if pixmap_rect is not None:
                scene_pos.setX(max(pixmap_rect.left(), min(scene_pos.x(), pixmap_rect.right())))
                scene_pos.setY(max(pixmap_rect.top(), min(scene_pos.y(), pixmap_rect.bottom())))

            rect = QRectF(self._drag_start_pos_scene, scene_pos).normalized()
            self._crop_rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)
```

5. 新增/修改 `mouseReleaseEvent`：

```python
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging_crop and event.button() == Qt.LeftButton:
            self._is_dragging_crop = False

            if self._crop_rect_item is not None:
                rect = self._crop_rect_item.rect()
                # 阈值：避免误触很小的矩形
                min_size = 5.0
                if rect.width() >= min_size and rect.height() >= min_size:
                    # 在预览坐标下发出裁剪请求信号
                    x = rect.x()
                    y = rect.y()
                    w = rect.width()
                    h = rect.height()
                    self.cropRequested.emit(x, y, w, h)

                # 不管是否裁剪，释放鼠标后先移除矩形
                self._scene.removeItem(self._crop_rect_item)
                self._crop_rect_item = None

            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)
```

> 注意：`mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` 要保持完整定义，避免删除已有逻辑（如空格拖动）。请将新增逻辑与现有代码合并。

---

## 七、扩展主窗口：`app/main_window.py` —— 响应裁剪请求

> 功能：接收 `ImageView` 发出的裁剪请求信号，弹出交互对话框，让用户选择「覆盖/另存为/取消」，调用裁剪服务，更新当前文档。

**操作：**

1. 打开 `app/main_window.py`，在文件头导入部分增加：

```python
from typing import Optional

from services.crop_service import crop_document_to_new_image
from models.image_document import ImageDocument
```

> 如果 `ImageDocument` 已经导入，请避免重复导入。

2. 在 `MainWindow.__init__` 中增加一个成员变量，用于保存当前文档：

在 `self._image_view = ImageView(self)` 后面增加：

```python
        self._current_document: Optional[ImageDocument] = None
```

3. 在 `_connect_signals` 中，连接 `cropRequested` 信号：

找到 `_connect_signals` 方法，增加一行：

```python
    def _connect_signals(self) -> None:
        self._open_action.triggered.connect(self.open_image_dialog)
        self._exit_action.triggered.connect(self.close)

        # 监听裁剪信号
        self._image_view.cropRequested.connect(self._on_crop_requested)
```

4. 在 `load_image` 方法中，保存当前文档引用：

找到 `load_image` 方法，确保在 `self._image_view.set_document(doc)` 后增加：

```python
        self._current_document = doc
```

5. 在 `MainWindow` 类中新增 `_on_crop_requested` 方法：

```python
    def _on_crop_requested(self, x: float, y: float, w: float, h: float) -> None:
        """当用户在视图中拉出裁剪框后触发。"""
        if self._current_document is None:
            return

        doc = self._current_document

        # 预览尺寸提示
        preview_info = f"预览裁剪区域：{int(w)} x {int(h)} 像素"
        original_info = (
            f"原图尺寸：{doc.original_width} x {doc.original_height} 像素\n"
            f"{preview_info}\n\n"
            "请选择裁剪保存方式："
        )

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认裁剪")
        msg_box.setText("是否裁剪选中区域？")
        msg_box.setInformativeText(original_info)
        overwrite_btn = msg_box.addButton("覆盖原图", QMessageBox.AcceptRole)
        save_as_btn = msg_box.addButton("另存为...", QMessageBox.ActionRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

        msg_box.setDefaultButton(overwrite_btn)
        msg_box.exec()

        clicked_button = msg_box.clickedButton()
        if clicked_button is cancel_btn:
            return

        # 计算裁剪矩形（预览坐标）
        preview_rect = (x, y, w, h)

        if clicked_button is overwrite_btn:
            target_path = doc.path
        elif clicked_button is save_as_btn:
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "裁剪后另存为",
                doc.path,
                "Images (*.png *.jpg *.jpeg *.bmp *.tiff)",
            )
            if not target_path:
                return
        else:
            # 理论上不会走到这里
            return

        try:
            new_doc = crop_document_to_new_image(doc, preview_rect, target_path)
        except Exception as e:
            QMessageBox.critical(self, "裁剪失败", f"执行裁剪时出错：\n{e}")
            return

        # 更新当前文档与视图
        self._current_document = new_doc
        self._image_view.set_document(new_doc)

        self.statusBar().showMessage(
            f"裁剪完成：{os.path.basename(new_doc.path)}  "
            f"原始尺寸：{new_doc.original_width}x{new_doc.original_height}  "
            f"预览尺寸：{new_doc.preview_width}x{new_doc.preview_height}",
            5000,
        )
```

---

## 八、行为验收标准

完成以上修改后，运行：

```bash
python main.py
```

验证以下行为：

1. 打开一张图片（包括大尺寸图片），工作区显示预览图。
2. 在工作区内：

   * 按住空格 + 鼠标左键拖动：可以平移视图；
   * 不按空格时，**左键按下 + 拖动**：可以拉出一个半透明矩形框；
   * 松开鼠标后：

     * 矩形足够大时，弹出“确认裁剪”对话框；
     * 可选择「覆盖原图」或「另存为」；
     * 选择后执行裁剪。
3. 裁剪完成后：

   * 工作区显示裁剪后的图片；
   * 状态栏显示新尺寸；
   * 再次拖动可以继续裁剪新的区域。
4. 对超大图片（若有）：

   * 预览显示仍然流畅；
   * 裁剪操作能够在合理时间内完成（大图可能需要几秒，但程序不崩溃）。

> 至此，「裁剪功能」实现完成，并且与后续的切图功能兼容（裁剪后新文档仍可继续切图）。

```
```
