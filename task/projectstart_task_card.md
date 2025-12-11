````markdown
# 任务卡：大图裁剪&切图工具项目初始化（PySide6 + Pillow + pyvips）

## 一、任务目标

在当前代码目录下（或新建 `img_slicer_tool` 目录），为“支持超大图（20k×20k）的裁剪 + 宫格切图工具”完成**项目骨架搭建**，包括：

1. 创建项目目录结构与基础文件。
2. 创建并填写 `requirements.txt`（使用推荐依赖版本）。
3. 实现一个**最小可运行 Demo**：
   - 启动 PySide6 窗口程序。
   - 主窗口内有图片编辑工作区（基于 QGraphicsView）。
   - 通过菜单“文件 → 打开图片”加载本地图片。
   - 只加载一次图片，自动生成“预览图”（最长边限制 4000 像素）。
   - 支持：
     - 鼠标滚轮 + `Ctrl`：缩放预览图。
     - 按住空格 + 左键拖动：平移视图。
   - 支持大图（高分辨率）时仍然流畅（预览图机制）。

> 注意：本任务**只负责项目初始化 + 大图预览功能**，裁剪与切图逻辑将在后续任务中实现。

---

## 二、环境与依赖要求

1. 使用 **Python 3.10+**。
2. 使用 **PySide6** 作为 GUI 框架。
3. 使用 **Pillow** 生成预览图。
4. 预留 **pyvips** + `numpy` 用于后续大图处理优化。
5. 使用 `pyinstaller` 作为打包工具（本任务仅写入依赖，不执行打包）。
6. 若当前目录为空，可在当前目录直接创建 `img_slicer_tool` 项目；若已有项目根目录，由你决定是否在其中创建子目录。

---

## 三、项目目录结构

在项目根目录（例如 `img_slicer_tool`）下创建以下结构：

```bash
img_slicer_tool/
├─ README.md
├─ requirements.txt
├─ main.py

├─ app/
│  ├─ __init__.py
│  ├─ application.py
│  └─ main_window.py

├─ views/
│  ├─ __init__.py
│  └─ image_view.py

├─ models/
│  ├─ __init__.py
│  └─ image_document.py

├─ services/
│  ├─ __init__.py
│  └─ image_loader.py

├─ utils/
│  ├─ __init__.py
│  ├─ image_math.py
│  └─ logging_utils.py

├─ resources/
│  ├─ icons/
│  │  └─ app_icon.png      # 可用占位图或留空文件
│  └─ qss/
│     └─ style.qss         # 可留空

└─ build/
   └─ img_slicer.spec      # 先创建占位文件
````

---

## 四、依赖文件：`requirements.txt`

在项目根目录创建并写入：

```txt
# GUI
PySide6==6.7.2

# Image processing
Pillow==10.2.0
pyvips==2.2.1
numpy==1.26.4

# Packaging
pyinstaller==6.3.0

# Logging (optional but recommended)
loguru==0.7.2
```

> 不在本任务中执行 `pip install`，只需生成该文件。

---

## 五、核心代码文件实现要求

### 1. `main.py`

功能：

* 作为程序入口。
* 创建并运行 `ImageApp` 应用。

示例实现（请写入文件，注意保持可运行）：

```python
import sys
from app.application import ImageApp

def main():
    app = ImageApp(sys.argv)
    sys.exit(app.run())

if __name__ == "__main__":
    main()
```

---

### 2. `app/application.py`

功能：

* 创建 `QApplication` 实例。
* 设置应用图标（如果图标不存在，则不报错）。
* 可选加载样式表 `resources/qss/style.qss`。
* 创建并显示主窗口 `MainWindow`。

实现要求：

* 定义 `ImageApp` 类，构造函数接收 `argv`。
* 提供 `run(self) -> int` 方法，执行主事件循环。

代码示例（可直接使用）：

```python
from __future__ import annotations

import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from app.main_window import MainWindow


class ImageApp:
    def __init__(self, argv: list[str]) -> None:
        self._app = QApplication(argv)
        self._main_window = MainWindow()
        self._configure_app()

    def _configure_app(self) -> None:
        self._app.setApplicationName("Img Slicer Tool")
        self._app.setOrganizationName("LocalDev")

        # 设置应用图标（可选）
        icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self._app.setWindowIcon(QIcon(icon_path))

        # 加载样式（可选）
        qss_path = os.path.join(os.path.dirname(__file__), "..", "resources", "qss", "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self._app.setStyleSheet(f.read())

    def run(self) -> int:
        self._main_window.show()
        return self._app.exec()
```

---

### 3. `app/main_window.py`

功能：

* 定义 `MainWindow` 类（继承 `QMainWindow`）。
* 中央区域放置 `ImageView`。
* 创建菜单栏“文件 → 打开图片”。
* 点击菜单后弹出文件选择框，选择图片并交给 `ImageView` 显示。

实现要求：

* 使用 `views.image_view.ImageView` 作为中心 widget。
* 打开图片时，调用 `services.image_loader.load_image_document(path)` 获取 `ImageDocument`，再传给 `ImageView.set_document()`。

代码示例（最小实现）：

```python
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from views.image_view import ImageView
from services.image_loader import load_image_document
from models.image_document import ImageDocument


class MainWindow(QMainWindow):
    def __init__(self, parent: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("图片裁剪与切图工具（预览版）")
        self.resize(1200, 800)

        self._image_view = ImageView(self)
        self.setCentralWidget(self._image_view)

        self._create_actions()
        self._create_menus()
        self._connect_signals()

    def _create_actions(self) -> None:
        self._open_action = QAction("打开图片(&O)", self)
        self._open_action.setShortcut("Ctrl+O")

        self._exit_action = QAction("退出(&Q)", self)
        self._exit_action.setShortcut("Ctrl+Q")

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction(self._open_action)
        file_menu.addSeparator()
        file_menu.addAction(self._exit_action)

    def _connect_signals(self) -> None:
        self._open_action.triggered.connect(self.open_image_dialog)
        self._exit_action.triggered.connect(self.close)

    def open_image_dialog(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle("选择图片")
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)")

        if dialog.exec():
            file_paths = dialog.selectedFiles()
            if not file_paths:
                return
            image_path = file_paths[0]
            self.load_image(image_path)

    def load_image(self, image_path: str) -> None:
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "错误", "文件不存在")
            return

        try:
            doc: ImageDocument = load_image_document(image_path)
        except Exception as e:  # 简单错误提示，后续可接 loguru
            QMessageBox.critical(self, "加载失败", f"加载图片出错：\n{e}")
            return

        self._image_view.set_document(doc)
        self.statusBar().showMessage(
            f"加载成功：{os.path.basename(image_path)}  "
            f"原始尺寸：{doc.original_width}x{doc.original_height}  "
            f"预览尺寸：{doc.preview_width}x{doc.preview_height}",
            5000,
        )
```

---

### 4. `views/image_view.py`

功能：

* 继承 `QGraphicsView`，作为图片编辑工作区。
* 内部使用 `QGraphicsScene` 显示预览图。
* 支持：

  * 滚轮 + `Ctrl`：缩放（以 1.1 / 0.9 为缩放因子）。
  * 空格 + 左键拖动：平移。
* 提供 `set_document(ImageDocument)` 方法：

  * 清空场景。
  * 添加新的预览图 pixmap。
  * 重置缩放为适配视图（使用 `fitInView`）。

实现示例：

```python
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPixmap, QWheelEvent, QMouseEvent
from PySide6.QtCore import Qt, QRectF

from models.image_document import ImageDocument


class ImageView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = None
        self._document: Optional[ImageDocument] = None

        self._current_scale: float = 1.0
        self._is_space_pressed: bool = False

        self._init_view()

    def _init_view(self) -> None:
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)

    def set_document(self, document: ImageDocument) -> None:
        """将 ImageDocument 绑定到视图并显示预览图。"""
        self._document = document
        self._scene.clear()
        self.resetTransform()
        self._current_scale = 1.0

        pixmap: QPixmap = document.preview_pixmap
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        # 自适应视图大小
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._current_scale = 1.0  # fitInView 后作为基本缩放参考

    # 缩放：Ctrl + 滚轮
    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                factor = 1.1
            else:
                factor = 0.9
            self._current_scale *= factor
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    # 空格控制拖动模式
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not self._is_space_pressed:
            self._is_space_pressed = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self._is_space_pressed = False
            self.setDragMode(QGraphicsView.NoDrag)
        super().keyReleaseEvent(event)

    # 禁止在非 HandDrag 模式下误触拖动事件
    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
```

---

### 5. `models/image_document.py`

功能：

* 定义 `ImageDocument` 数据结构，保存：

  * 原始图片路径
  * 原始宽高
  * 预览宽高
  * 预览图 `QPixmap`
  * 坐标映射比例 `scale_x / scale_y`（原图 / 预览）
* 这些信息将用于后续的裁剪和切图。

实现示例：

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

---

### 6. `services/image_loader.py`

功能：

* 从给定路径加载图片。
* 使用 Pillow 生成预览图（最长边不超过 4000 像素）。
* 将预览图转换为 `QPixmap`。
* 返回 `ImageDocument` 实例。
* 注意：此处可先使用同步实现（后续可改为 QThread）。

实现示例：

```python
from __future__ import annotations

import os
from typing import Tuple

from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from models.image_document import ImageDocument


MAX_PREVIEW_SIZE = 4000  # 预览图最大边长（像素）


def _calc_preview_size(width: int, height: int) -> Tuple[int, int, float]:
    """根据原始尺寸计算预览图尺寸和缩放比例。"""
    if width <= MAX_PREVIEW_SIZE and height <= MAX_PREVIEW_SIZE:
        return width, height, 1.0

    ratio = min(MAX_PREVIEW_SIZE / width, MAX_PREVIEW_SIZE / height)
    preview_width = int(width * ratio)
    preview_height = int(height * ratio)
    return preview_width, preview_height, ratio


def load_image_document(path: str) -> ImageDocument:
    """从文件路径加载图片并生成 ImageDocument（带预览图）。"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    # 使用 Pillow 打开图片
    with Image.open(path) as img:
        img.load()
        original_width, original_height = img.size

        preview_width, preview_height, ratio = _calc_preview_size(
            original_width, original_height
        )

        if ratio != 1.0:
            preview_img = img.resize((preview_width, preview_height), Image.LANCZOS)
        else:
            preview_img = img

        # 转换为 QPixmap
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
    """将 Pillow Image 转为 QImage。"""
    if pil_image.mode == "RGB":
        r, g, b = pil_image.split()
        pil_image = Image.merge("RGB", (r, g, b))
        data = pil_image.tobytes("raw", "RGB")
        qimage = QImage(
            data,
            pil_image.size[0],
            pil_image.size[1],
            QImage.Format.Format_RGB888,
        )
        return qimage
    elif pil_image.mode == "RGBA":
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(
            data,
            pil_image.size[0],
            pil_image.size[1],
            QImage.Format.Format_RGBA8888,
        )
        return qimage
    else:
        # 其他模式先转成 RGBA
        pil_image = pil_image.convert("RGBA")
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(
            data,
            pil_image.size[0],
            pil_image.size[1],
            QImage.Format.Format_RGBA8888,
        )
        return qimage
```

---

### 7. `utils/image_math.py`

当前任务只需要一个预留文件，后续裁剪与切图时再补充坐标映射逻辑。
请创建文件并填入简单占位内容：

```python
from __future__ import annotations

"""
图像相关的数学工具函数模块。

后续将放置：
- 预览坐标 <-> 原图坐标 映射
- 宫格线位置计算
- 边界裁剪与安全校验 等
"""
```

---

### 8. `utils/logging_utils.py`

创建日志工具占位（后续可接 loguru）：

```python
from __future__ import annotations

from loguru import logger

logger.add("img_slicer.log", rotation="5 MB", encoding="utf-8", enqueue=True)
```

---

### 9. 其他文件

* `README.md`：写入简要说明，例如：

```markdown
# Img Slicer Tool

基于 PySide6 + Pillow + pyvips 的大图裁剪与宫格切图小工具。

当前版本：
- 支持加载大图并以预览图方式显示
- 支持 Ctrl + 滚轮缩放、空格 + 拖动平移视图
- 后续将逐步增加：裁剪、宫格切图、线条编辑等功能
```

* `resources/icons/app_icon.png`：

  * 若无法提供真实图标，可创建一个空文件或简单占位图片。

* `resources/qss/style.qss`：

  * 可写入空内容或简单样式。

* `build/img_slicer.spec`：占位（后续打包配置再完善）：

```python
# 占位文件，后续由 pyinstaller 生成或补充
```

---

## 六、验收标准

1. 在项目根目录执行：

   ```bash
   python main.py
   ```

   程序能正常启动一个窗口，标题为“图片裁剪与切图工具（预览版）”。

2. 通过菜单“文件 → 打开图片”：

   * 选择一张本地图片（包括大图）；
   * 图片能在中央工作区显示，窗口大小改变时仍能看到完整预览图。

3. 操作体验：

   * 按住 `Ctrl` + 滚轮：预览图缩放（放大/缩小）。
   * 按住空格 + 鼠标左键拖动：平移视图查看细节。
   * 加载高分辨率图片（例如超大海报）时，程序仍然可以流畅显示预览，不明显卡死。

4. 所有上述文件路径与模块引用关系正确，无 ImportError 或语法错误。

---

> 任务完成后，这个项目骨架将作为后续“裁剪功能实现”和“宫格切图功能实现”的基础。请严格按照上述目录结构与文件内容创建与修改代码。

```
