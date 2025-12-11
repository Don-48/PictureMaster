````markdown
# 任务卡：「宫格切图功能」实现（支持大图，预览坐标 -> 原图切图）

## 任务目标

在当前项目 `img_slicer_tool` 的基础上，完成**宫格切图功能**，满足以下需求：

1. 在图片编辑工作区中：
   - 可通过输入“行数 / 列数”快速生成宫格切图线（红色虚线）。
   - 可通过鼠标点击自由生成切图线：
     - 横线、竖线、十字线（一次生成一横一竖）。
     - 线条支持拖动（调整位置）。
     - 选中线条后按 `Delete` 键删除。
2. 只有点击“执行切图”按钮（菜单命令）时才真正执行切图操作。
3. 切图时基于**预览图坐标 → 原图坐标**映射，支持超大图（如 20000×20000）。
4. 切图结果保存规则：
   - 先设置一个“切图保存根路径”（可通过菜单配置）。
   - 每次切图时，在根路径下以“原图文件名”自动创建子目录：
     - 例如：`<根路径>/<原图名>/原图名_rXX_cYY.png`

> 说明：  
> 本任务主要实现 **切图线的管理 + 宫格生成 + 执行切图保存**。  
> 默认交互：  
> - 在“切图模式”下，鼠标点击生成切图线：  
>   - **无修饰键**：十字线（横 + 竖）。  
>   - **按住 Shift 点击**：仅生成 **横线**。  
>   - **按住 Ctrl 点击**：仅生成 **竖线**。  

---

## 一、前置条件检查

确认项目已包含（来自前两个任务卡）：

- `main.py`
- `app/application.py`
- `app/main_window.py`
- `views/image_view.py`（已有缩放、平移、裁剪逻辑）
- `views/overlay_items.py`（已有 `CropRectItem`）
- `models/image_document.py`
- `services/image_loader.py`
- `services/crop_service.py`
- `utils/image_math.py`
- `utils/logging_utils.py`

若部分文件尚未创建，请先完成之前的任务卡。

---

## 二、新增模型：`models/slice_layout.py`

> 用于保存切图线布局（横线 + 竖线），并计算切图区域。

**操作：**

在 `models/` 目录下新建文件 `slice_layout.py`，写入：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class SliceLayout:
    """
    在预览坐标系中的切图线布局：

    - horizontal_lines: 所有水平切图线的 y 坐标（单位：预览像素）
    - vertical_lines: 所有竖直切图线的 x 坐标（单位：预览像素）
    """

    horizontal_lines: List[float] = field(default_factory=list)
    vertical_lines: List[float] = field(default_factory=list)

    def normalize(self, preview_width: int, preview_height: int) -> None:
        """清理非法值，并去重 + 排序。"""
        self.horizontal_lines = sorted(
            {y for y in self.horizontal_lines if 0 < y < preview_height}
        )
        self.vertical_lines = sorted(
            {x for x in self.vertical_lines if 0 < x < preview_width}
        )

    def get_boundaries(
        self,
        preview_width: int,
        preview_height: int,
    ) -> Tuple[List[float], List[float]]:
        """
        返回完整边界列表（含 0 和 最大边界），用于生成宫格：

        xs = [0, ..., preview_width]
        ys = [0, ..., preview_height]
        """
        self.normalize(preview_width, preview_height)

        xs = [0.0] + self.vertical_lines + [float(preview_width)]
        ys = [0.0] + self.horizontal_lines + [float(preview_height)]
        return xs, ys
````

---

## 三、扩展图元：`views/overlay_items.py` —— 增加切图线图元

> 在已有 `CropRectItem` 的基础上，新建 `GuideLineItem`，表示一条横/竖切图线。

**操作：**

打开 `views/overlay_items.py`，在文件末尾追加：

```python
from PySide6.QtWidgets import QGraphicsLineItem
from PySide6.QtGui import QPen
from PySide6.QtCore import Qt, QPointF


class GuideLineItem(QGraphicsLineItem):
    """红色虚线切图线，可移动、可选中。"""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"

    def __init__(self, orientation: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if orientation not in (self.HORIZONTAL, self.VERTICAL):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        self.orientation = orientation

        pen = QPen(Qt.red)
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        self.setPen(pen)

        self.setZValue(9)
        self.setFlag(QGraphicsLineItem.ItemIsMovable, True)
        self.setFlag(QGraphicsLineItem.ItemIsSelectable, True)

    def scene_coordinate_value(self) -> float:
        """
        返回该线在场景中的关键坐标：
        - 对于水平线：y
        - 对于竖直线：x
        """
        line = self.line()
        p1 = self.mapToScene(line.p1())
        p2 = self.mapToScene(line.p2())

        if self.orientation == self.HORIZONTAL:
            # 取平均值更稳妥
            return (p1.y() + p2.y()) / 2.0
        else:
            return (p1.x() + p2.x()) / 2.0
```

---

## 四、扩展工具函数：`utils/image_math.py` —— 增加切图映射相关逻辑

**操作：**

打开 `utils/image_math.py`，在已有内容基础上追加以下函数：

```python
from typing import List, Tuple
from models.slice_layout import SliceLayout
from models.image_document import ImageDocument


def preview_lines_to_original_boundaries(
    doc: ImageDocument,
    layout: SliceLayout,
) -> Tuple[List[int], List[int]]:
    """
    将预览坐标系中的切图线布局转换为原图中的切图边界（整数像素坐标）。

    返回：
        xs_original: List[int]
        ys_original: List[int]
    """

    xs_preview, ys_preview = layout.get_boundaries(doc.preview_width, doc.preview_height)

    xs_original: List[int] = []
    for x in xs_preview:
        xo = int(round(x * doc.scale_x))
        xo = max(0, min(xo, doc.original_width))
        xs_original.append(xo)

    ys_original: List[int] = []
    for y in ys_preview:
        yo = int(round(y * doc.scale_y))
        yo = max(0, min(yo, doc.original_height))
        ys_original.append(yo)

    # 去重 & 排序，避免浮点误差造成重复
    xs_original = sorted(set(xs_original))
    ys_original = sorted(set(ys_original))

    # 需要至少 2 个边界才有一个区域
    if len(xs_original) < 2 or len(ys_original) < 2:
        raise ValueError("切图边界不足，无法生成宫格")

    return xs_original, ys_original
```

---

## 五、新增服务：`services/slice_service.py`

> 负责将布局好的宫格线转换为原图多个小图，并保存到子目录。

**操作：**

在 `services/` 目录下新建文件 `slice_service.py`，写入：

```python
from __future__ import annotations

import os
from typing import Tuple

from PIL import Image

from models.image_document import ImageDocument
from models.slice_layout import SliceLayout
from utils.image_math import preview_lines_to_original_boundaries


def slice_document_to_tiles(
    doc: ImageDocument,
    layout: SliceLayout,
    output_root_dir: str,
) -> str:
    """
    基于切图线布局，将当前文档切分为宫格小图并保存。

    :param doc: 当前图片文档
    :param layout: 在预览坐标中的切图线布局
    :param output_root_dir: 切图保存根路径
    :return: 实际使用的输出子目录路径
    """

    if not os.path.exists(doc.path):
        raise FileNotFoundError(f"原始图片不存在：{doc.path}")

    if not output_root_dir:
        raise ValueError("输出根路径不能为空")

    os.makedirs(output_root_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(doc.path))[0]
    ext = os.path.splitext(doc.path)[1].lower()
    if not ext:
        ext = ".png"

    # 子目录：root / 原图名/
    output_dir = os.path.join(output_root_dir, base_name)
    os.makedirs(output_dir, exist_ok=True)

    xs, ys = preview_lines_to_original_boundaries(doc, layout)

    # 打开原图，只打开一次，循环裁剪
    with Image.open(doc.path) as img:
        img.load()

        tile_count = 0
        for row in range(len(ys) - 1):
            y1 = ys[row]
            y2 = ys[row + 1]
            if y2 <= y1:
                continue

            for col in range(len(xs) - 1):
                x1 = xs[col]
                x2 = xs[col + 1]
                if x2 <= x1:
                    continue

                box = (x1, y1, x2, y2)
                tile = img.crop(box)

                tile_count += 1
                filename = f"{base_name}_r{row+1:02d}_c{col+1:02d}{ext}"
                save_path = os.path.join(output_dir, filename)

                save_kwargs = {}
                if ext in [".jpg", ".jpeg"]:
                    save_kwargs["quality"] = 95
                    save_kwargs["subsampling"] = 0

                tile.save(save_path, **save_kwargs)

    return output_dir
```

---

## 六、扩展视图：`views/image_view.py` —— 切图模式与切图线交互

### 6.1 新增导入

**操作：**

打开 `views/image_view.py`，在顶部 import 区增加：

```python
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from views.overlay_items import CropRectItem, GuideLineItem
from models.slice_layout import SliceLayout
```

> 如已导入 `Qt`, `QRectF`, `QPointF`, `Signal` 等，请合理合并避免重复。

### 6.2 增加模式定义和内部状态

在 `class ImageView(QGraphicsView):` 内部，新增类级模式常量和信号：

```python
    MODE_CROP = "crop"
    MODE_SLICE = "slice"

    # 在预览坐标系中发出裁剪框信号: (x, y, w, h)
    cropRequested = Signal(float, float, float, float)
```

在 `__init__` 中初始化变量（在 `_init_view()` 之后）：

```python
        self._mode: str = self.MODE_CROP

        self._crop_rect_item: CropRectItem | None = None
        self._is_dragging_crop: bool = False
        self._drag_start_pos_scene: QPointF | None = None
```

### 6.3 增加模式切换方法

在 `ImageView` 类中添加：

```python
    def set_mode(self, mode: str) -> None:
        if mode not in (self.MODE_CROP, self.MODE_SLICE):
            return
        self._mode = mode
        # 切换模式时，清理现有裁剪框
        if self._crop_rect_item is not None:
            self._scene.removeItem(self._crop_rect_item)
            self._crop_rect_item = None
```

### 6.4 修改 `mousePressEvent`：分别处理裁剪模式与切图模式

将原来的 `mousePressEvent` 替换为如下版本（将原有逻辑融合其中）：

```python
    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 空格拖动模式：交给父类处理
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
                # 裁剪模式：拖出矩形
                self._is_dragging_crop = True
                self._drag_start_pos_scene = scene_pos

                if self._crop_rect_item is not None:
                    self._scene.removeItem(self._crop_rect_item)
                    self._crop_rect_item = None

                rect = QRectF(scene_pos, scene_pos)
                self._crop_rect_item = CropRectItem(rect)
                self._scene.addItem(self._crop_rect_item)
            elif self._mode == self.MODE_SLICE:
                # 切图模式：点击生成切图线
                modifiers = event.modifiers()

                create_horizontal = False
                create_vertical = False

                if modifiers & Qt.ShiftModifier:
                    create_horizontal = True
                elif modifiers & Qt.ControlModifier:
                    create_vertical = True
                else:
                    # 默认十字线
                    create_horizontal = True
                    create_vertical = True

                if create_horizontal:
                    y = scene_pos.y()
                    line = GuideLineItem(
                        GuideLineItem.HORIZONTAL,
                    )
                    line.setLine(pixmap_rect.left(), y, pixmap_rect.right(), y)
                    self._scene.addItem(line)

                if create_vertical:
                    x = scene_pos.x()
                    line = GuideLineItem(
                        GuideLineItem.VERTICAL,
                    )
                    line.setLine(x, pixmap_rect.top(), x, pixmap_rect.bottom())
                    self._scene.addItem(line)
        else:
            super().mousePressEvent(event)
```

### 6.5 修改 `mouseMoveEvent`：仅在裁剪模式下拖动矩形

```python
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._mode == self.MODE_CROP
            and self._is_dragging_crop
            and self._crop_rect_item is not None
            and self._drag_start_pos_scene is not None
        ):
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

### 6.6 修改 `mouseReleaseEvent`：完成裁剪区域的发射

```python
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
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
                    x = rect.x()
                    y = rect.y()
                    w = rect.width()
                    h = rect.height()
                    self.cropRequested.emit(x, y, w, h)

                self._scene.removeItem(self._crop_rect_item)
                self._crop_rect_item = None

            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)
```

### 6.7 扩展 `keyPressEvent`：支持 Delete 删除切图线

在现有 `keyPressEvent` 中追加 Delete 逻辑（保持空格逻辑不变）：

```python
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not self._is_space_pressed:
            self._is_space_pressed = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif event.key() == Qt.Key_Delete:
            # 删除选中的切图线
            for item in self._scene.selectedItems():
                if isinstance(item, GuideLineItem):
                    self._scene.removeItem(item)
        super().keyPressEvent(event)
```

### 6.8 新增方法：获取当前切图布局

在 `ImageView` 类中增加方法：

```python
    def get_slice_layout(self) -> SliceLayout:
        """从场景中的 GuideLineItem 收集切图线布局（在预览坐标系中）。"""
        layout = SliceLayout()

        if self._pixmap_item is None:
            return layout

        pixmap_rect = self._pixmap_item.boundingRect()

        for item in self._scene.items():
            if isinstance(item, GuideLineItem):
                value = item.scene_coordinate_value()
                # 限制到图片范围
                if item.orientation == GuideLineItem.HORIZONTAL:
                    if pixmap_rect.top() <= value <= pixmap_rect.bottom():
                        layout.horizontal_lines.append(value)
                else:
                    if pixmap_rect.left() <= value <= pixmap_rect.right():
                        layout.vertical_lines.append(value)

        # 归一化（去重&排序）在 SliceLayout 内部处理
        layout.normalize(int(pixmap_rect.width()), int(pixmap_rect.height()))
        return layout
```

---

## 七、扩展主窗口：`app/main_window.py` —— 切图模式、宫格生成、执行切图

### 7.1 新增导入和成员

**操作：**

打开 `app/main_window.py`，在顶部增加导入：

```python
from models.slice_layout import SliceLayout
from services.slice_service import slice_document_to_tiles
```

在 `__init__` 中 `self._current_document` 后增加一个输出路径成员：

```python
        self._current_document: Optional[ImageDocument] = None
        self._slice_output_root: Optional[str] = None
```

### 7.2 扩展 `_create_actions`：新增切图相关动作

在 `_create_actions` 方法中新增动作定义：

```python
    def _create_actions(self) -> None:
        self._open_action = QAction("打开图片(&O)", self)
        self._open_action.setShortcut("Ctrl+O")

        self._exit_action = QAction("退出(&Q)", self)
        self._exit_action.setShortcut("Ctrl+Q")

        # 切图模式开关
        self._toggle_slice_mode_action = QAction("切图模式(&S)", self)
        self._toggle_slice_mode_action.setCheckable(True)
        self._toggle_slice_mode_action.setShortcut("S")

        # 输入行列生成宫格线
        self._generate_grid_action = QAction("按行列生成宫格线(&G)", self)
        self._generate_grid_action.setShortcut("Ctrl+G")

        # 执行切图
        self._execute_slice_action = QAction("执行切图(&X)", self)
        self._execute_slice_action.setShortcut("Ctrl+Shift+X")

        # 设置切图保存路径
        self._set_slice_output_dir_action = QAction("设置切图保存路径...", self)
```

### 7.3 扩展 `_create_menus`：加入新的菜单项

```python
    def _create_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction(self._open_action)
        file_menu.addSeparator()
        file_menu.addAction(self._set_slice_output_dir_action)
        file_menu.addSeparator()
        file_menu.addAction(self._exit_action)

        edit_menu = menubar.addMenu("编辑(&E)")
        edit_menu.addAction(self._toggle_slice_mode_action)

        slice_menu = menubar.addMenu("切图(&S)")
        slice_menu.addAction(self._generate_grid_action)
        slice_menu.addAction(self._execute_slice_action)
```

### 7.4 扩展 `_connect_signals`：连接新动作

```python
    def _connect_signals(self) -> None:
        self._open_action.triggered.connect(self.open_image_dialog)
        self._exit_action.triggered.connect(self.close)

        # 裁剪信号
        self._image_view.cropRequested.connect(self._on_crop_requested)

        # 切图相关
        self._toggle_slice_mode_action.toggled.connect(self._on_toggle_slice_mode)
        self._generate_grid_action.triggered.connect(self._on_generate_grid_from_rows_cols)
        self._execute_slice_action.triggered.connect(self._on_execute_slice)
        self._set_slice_output_dir_action.triggered.connect(self._on_set_slice_output_dir)
```

> 注意：`_on_crop_requested` 在之前裁剪任务卡中已实现。

### 7.5 切图模式切换：`_on_toggle_slice_mode`

在 `MainWindow` 类中新增方法：

```python
    def _on_toggle_slice_mode(self, enabled: bool) -> None:
        if enabled:
            self._image_view.set_mode(self._image_view.MODE_SLICE)
            self.statusBar().showMessage("已进入切图模式：点击生成切图线（默认十字线，Shift=横线，Ctrl=竖线）", 5000)
        else:
            self._image_view.set_mode(self._image_view.MODE_CROP)
            self.statusBar().showMessage("已退出切图模式，回到裁剪模式", 5000)
```

### 7.6 设置切图保存路径：`_on_set_slice_output_dir`

```python
    def _on_set_slice_output_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "选择切图保存根目录")
        if dir_path:
            self._slice_output_root = dir_path
            self.statusBar().showMessage(f"切图保存根路径：{dir_path}", 5000)
```

### 7.7 按行列生成宫格线：`_on_generate_grid_from_rows_cols`

为简单起见，使用输入对话框让用户输入行 / 列：

```python
from PySide6.QtWidgets import QInputDialog
```

在文件顶部导入 `QInputDialog`，然后在 `MainWindow` 类中新增方法：

```python
    def _on_generate_grid_from_rows_cols(self) -> None:
        if self._current_document is None or self._image_view is None:
            QMessageBox.warning(self, "提示", "请先打开一张图片。")
            return

        # 行数
        rows, ok_rows = QInputDialog.getInt(
            self,
            "输入行数",
            "切图行数（>=1）：",
            value=2,
            min=1,
            max=100,
        )
        if not ok_rows:
            return

        # 列数
        cols, ok_cols = QInputDialog.getInt(
            self,
            "输入列数",
            "切图列数（>=1）：",
            value=2,
            min=1,
            max=100,
        )
        if not ok_cols:
            return

        # 生成宫格线（在预览坐标系中）
        doc = self._current_document
        preview_w = doc.preview_width
        preview_h = doc.preview_height

        # 清理当前所有 GuideLineItem（可选：保留手动线则跳过）
        # 这里我们不清理，直接叠加行列线。若需要清空，请遍历 scene.items() 删除 GuideLineItem。

        h_step = preview_h / rows
        v_step = preview_w / cols

        pixmap_item = self._image_view._pixmap_item
        if pixmap_item is None:
            return

        pixmap_rect = pixmap_item.boundingRect()

        # 水平线（不包括边界）
        for i in range(1, rows):
            y = pixmap_rect.top() + h_step * i
            line = GuideLineItem(GuideLineItem.HORIZONTAL)
            line.setLine(pixmap_rect.left(), y, pixmap_rect.right(), y)
            self._image_view.scene().addItem(line)

        # 竖直线（不包括边界）
        for j in range(1, cols):
            x = pixmap_rect.left() + v_step * j
            line = GuideLineItem(GuideLineItem.VERTICAL)
            line.setLine(x, pixmap_rect.top(), x, pixmap_rect.bottom())
            self._image_view.scene().addItem(line)

        self.statusBar().showMessage(f"已生成 {rows}x{cols} 宫格切图线（不含边界线）。", 5000)
```

> 说明：
>
> * 边界线（0 和最大宽/高）在 `SliceLayout.get_boundaries` 中自动加入，不需要在视图里画。
> * 若希望“生成宫格线前清空原有线”，可在生成前遍历 `scene.items()` 删除所有 `GuideLineItem`。

### 7.8 执行切图：`_on_execute_slice`

```python
    def _on_execute_slice(self) -> None:
        if self._current_document is None:
            QMessageBox.warning(self, "提示", "请先打开一张图片。")
            return

        doc = self._current_document
        layout = self._image_view.get_slice_layout()

        if not layout.horizontal_lines and not layout.vertical_lines:
            reply = QMessageBox.question(
                self,
                "确认",
                "当前没有明显的切图线，只会导出整张图片为一个切片。\n是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        # 确定输出根路径
        output_root = self._slice_output_root
        if not output_root:
            # 默认使用原图所在目录
            output_root = os.path.dirname(doc.path)
            self._slice_output_root = output_root

        try:
            output_dir = slice_document_to_tiles(doc, layout, output_root)
        except Exception as e:
            QMessageBox.critical(self, "切图失败", f"切图过程中发生错误：\n{e}")
            return

        QMessageBox.information(
            self,
            "切图完成",
            f"切图已完成，保存于目录：\n{output_dir}",
        )
        self.statusBar().showMessage(f"切图完成：{output_dir}", 8000)
```

---

## 八、行为验收标准

运行：

```bash
python main.py
```

验证以下行为：

1. 正常打开大图，进入编辑界面。
2. 在菜单「编辑 → 切图模式」打勾：

   * 状态栏提示“已进入切图模式”。
3. 在切图模式下，鼠标交互：

   * **左键点击画布（无修饰键）**：生成一条横线 + 一条竖线，均为红色虚线。
   * **按住 Shift + 左键点击**：只生成一条水平切图线。
   * **按住 Ctrl + 左键点击**：只生成一条竖直切图线。
   * 切图线可以用鼠标拖动：

     * 水平线整体上下移动；
     * 竖直线整体左右移动。
   * 点击线条使其高亮，然后按 `Delete` 键，线条被删除。
4. 菜单「切图 → 按行列生成宫格线」：

   * 输入行数和列数（例如 3 行 4 列）后，工作区生成宫格形式的切图线（不包括边界线）。
5. 菜单「切图 → 执行切图」：

   * 若未设置保存路径，默认使用原图所在目录。
   * 程序在根目录下创建子目录 `<原图名>/`，并将所有切片按

     * `原图名_rXX_cYY.ext`
       的命名规则保存。
   * 切图完成弹出提示框，并在状态栏显示输出目录。
6. 切图后原图不被修改，仅在文件系统中多出子图文件。
7. 对于大图（如果有 10000×10000 或 20000×20000），切图过程可能耗时稍长，但程序不会崩溃，内存占用在合理范围内。

> 至此，“宫格切图功能”已实现：包含宫格线生成、自定义切图线、线条编辑、执行切图和保存规则，且兼容大图场景，可在后续迭代中进一步引入 `pyvips` 做性能优化（无需修改 UI 和布局逻辑）。

```
```
