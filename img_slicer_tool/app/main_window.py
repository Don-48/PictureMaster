from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from models.image_document import ImageDocument
from models.slice_layout import SliceLayout
from services.crop_service import crop_document_to_new_image
from services.image_loader import load_image_document
from services.slice_service import slice_document_to_tiles
from views.image_view import ImageView
from views.slice_side_panel import SliceSidePanel


class MainWindow(QMainWindow):
    def __init__(self, parent: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("图片裁剪与切图工具（预览版）")
        self.resize(1200, 800)

        self._image_view = ImageView(self)
        self._slice_panel = SliceSidePanel(self)
        central_widget = QWidget(self)
        central_layout = QHBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._slice_panel)
        central_layout.addWidget(self._image_view, 1)
        self.setCentralWidget(central_widget)
        self._slice_panel.setVisible(False)
        self._slice_panel.set_slice_mode(self._image_view.sliceMode)
        self._slice_panel.set_line_tool(self._image_view.lineTool)
        self._current_document: Optional[ImageDocument] = None
        self._slice_output_root: Optional[str] = None
        self._last_manual_tool = "cross"

        self._create_actions()
        self._create_menus()
        self._connect_signals()

    def _create_actions(self) -> None:
        self._open_action = QAction("打开图片(&O)", self)
        self._open_action.setShortcut("Ctrl+O")

        self._exit_action = QAction("退出(&Q)", self)
        self._exit_action.setShortcut("Ctrl+Q")

        self._toggle_slice_mode_action = QAction("切图模式(&S)", self)
        self._toggle_slice_mode_action.setCheckable(True)
        self._toggle_slice_mode_action.setShortcut("S")

        self._generate_grid_action = QAction("按行列生成宫格线(&G)", self)
        self._generate_grid_action.setShortcut("Ctrl+G")

        self._execute_slice_action = QAction("执行切图(&X)", self)
        self._execute_slice_action.setShortcut("Ctrl+Shift+X")

        self._set_slice_output_dir_action = QAction("设置切图保存路径...", self)

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

    def _connect_signals(self) -> None:
        self._open_action.triggered.connect(self.open_image_dialog)
        self._exit_action.triggered.connect(self.close)
        self._image_view.cropRequested.connect(self._on_crop_requested)
        self._image_view.imageDropped.connect(self._on_image_dropped)
        self._image_view.invalidFileDropped.connect(self._on_invalid_drop)
        self._toggle_slice_mode_action.toggled.connect(self._on_toggle_slice_mode)
        self._generate_grid_action.triggered.connect(self._on_generate_grid_from_rows_cols)
        self._execute_slice_action.triggered.connect(self._on_execute_slice)
        self._set_slice_output_dir_action.triggered.connect(self._on_set_slice_output_dir)
        self._slice_panel.sliceModeChanged.connect(self._on_slice_work_mode_changed)
        self._slice_panel.gridValueChanged.connect(self._on_grid_values_changed)
        self._slice_panel.lineToolChanged.connect(self._on_line_tool_changed)
        self._slice_panel.executeRequested.connect(self._on_execute_slice)

    def open_image_dialog(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle("选择图片")
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)")

        if dialog.exec():
            file_paths = dialog.selectedFiles()
            if not file_paths:
                return
            self.load_image(file_paths[0])

    def load_image(self, image_path: str) -> None:
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "错误", "文件不存在")
            return

        try:
            document: ImageDocument = load_image_document(image_path)
        except Exception as exc:  # noqa: BLE001 - show friendly error
            QMessageBox.critical(self, "加载失败", f"加载图片出错：\n{exc}")
            return

        self._image_view.set_document(document)
        self._current_document = document
        self.statusBar().showMessage(
            (
                f"加载成功：{os.path.basename(image_path)}  "
                f"原始尺寸：{document.original_width}x{document.original_height}  "
                f"预览尺寸：{document.preview_width}x{document.preview_height}"
            ),
            5000,
        )

    def _on_crop_requested(self, x: float, y: float, w: float, h: float) -> None:
        if self._current_document is None:
            return

        doc = self._current_document
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
            return

        try:
            new_doc = crop_document_to_new_image(doc, preview_rect, target_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "裁剪失败", f"执行裁剪时出错：\n{exc}")
            return

        self._current_document = new_doc
        self._image_view.set_document(new_doc)
        self.statusBar().showMessage(
            (
                f"裁剪完成：{os.path.basename(new_doc.path)}  "
                f"原始尺寸：{new_doc.original_width}x{new_doc.original_height}  "
                f"预览尺寸：{new_doc.preview_width}x{new_doc.preview_height}"
            ),
            5000,
        )

    def _on_toggle_slice_mode(self, enabled: bool) -> None:
        if enabled:
            self._image_view.set_mode(self._image_view.MODE_SLICE)
            self._slice_panel.setVisible(True)
            self.statusBar().showMessage("已进入切图模式：使用左侧工作栏配置切图方式和工具。", 6000)
        else:
            self._image_view.set_mode(self._image_view.MODE_CROP)
            self._slice_panel.setVisible(False)
            self.statusBar().showMessage("已退出切图模式，回到裁剪模式", 5000)

    def _on_set_slice_output_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "选择切图保存根目录")
        if dir_path:
            self._slice_output_root = dir_path
            self.statusBar().showMessage(f"切图保存根路径：{dir_path}", 5000)

    def _on_generate_grid_from_rows_cols(self) -> None:
        if self._current_document is None:
            QMessageBox.warning(self, "提示", "请先打开一张图片。")
            return

        rows, ok_rows = QInputDialog.getInt(self, "输入行数", "切图行数（>=1）：", 2, 1, 100)
        if not ok_rows:
            return

        cols, ok_cols = QInputDialog.getInt(self, "输入列数", "切图列数（>=1）：", 2, 1, 100)
        if not ok_cols:
            return

        self._ensure_slice_mode_enabled()
        self._slice_panel.set_slice_mode("grid")
        self._image_view.set_slice_work_mode("grid")
        self._slice_panel.set_grid_values(rows, cols)
        self._image_view.set_grid_size(rows, cols)
        self.statusBar().showMessage(f"已生成 {rows}x{cols} 宫格切图线。", 5000)

    def _on_execute_slice(self) -> None:
        if self._current_document is None:
            QMessageBox.warning(self, "提示", "请先打开一张图片。")
            return

        doc = self._current_document
        layout = self._image_view.get_slice_layout()
        tile_count = self._calculate_tile_count(layout)

        if not layout.horizontal_lines and not layout.vertical_lines:
            reply = QMessageBox.question(
                self,
                "确认",
                "当前没有切图线，只会导出整张图片为一个切片。\n是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        output_root = self._slice_output_root
        if not output_root:
            output_root = os.path.dirname(doc.path)
            self._slice_output_root = output_root

        try:
            output_dir = slice_document_to_tiles(doc, layout, output_root)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "切图失败", f"切图过程中发生错误：\n{exc}")
            return

        self._show_slice_result(output_dir, tile_count)

    def _on_slice_work_mode_changed(self, mode: str) -> None:
        if mode not in {"grid", "manual"}:
            return
        if (
            mode == "manual"
            and self._image_view.sliceMode == "grid"
            and self._image_view.has_cut_lines()
        ):
            reply = QMessageBox.question(
                self,
                "切换模式",
                "切换到手动模式将清除当前网格线，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self._slice_panel.set_slice_mode("grid")
                return

        self._image_view.set_slice_work_mode(mode)
        if mode == "manual":
            self._image_view.set_line_tool(self._last_manual_tool)
            self._slice_panel.set_line_tool(self._last_manual_tool)
        else:
            self._slice_panel.set_line_tool("select")

    def _on_grid_values_changed(self, rows: int, cols: int) -> None:
        if self._current_document is None or self._image_view.sliceMode != "grid":
            return
        self._image_view.set_grid_size(rows, cols)
        self.statusBar().showMessage(f"网格模式：{rows} 行 x {cols} 列。", 4000)

    def _on_line_tool_changed(self, tool: str) -> None:
        self._image_view.set_line_tool(tool)
        if tool != "select":
            self._last_manual_tool = tool
        if self._image_view.sliceMode != "manual":
            return
        hints = {
            "horizontal": "左键点击生成水平切割线。",
            "vertical": "左键点击生成垂直切割线。",
            "cross": "左键点击生成十字切割线。",
            "select": "左键点击选中切割线。",
        }
        message = hints.get(tool)
        if message:
            self.statusBar().showMessage(f"手动模式：{message}", 5000)

    def _on_image_dropped(self, path: str) -> None:
        self.load_image(path)

    def _on_invalid_drop(self, path: str) -> None:
        QMessageBox.warning(
            self,
            "不支持的文件",
            f"仅支持拖拽 jpg/png/jpeg/webp 图片文件。\n无法加载：{os.path.basename(path)}",
        )

    def _ensure_slice_mode_enabled(self) -> None:
        if not self._toggle_slice_mode_action.isChecked():
            self._toggle_slice_mode_action.setChecked(True)

    def _calculate_tile_count(self, layout: SliceLayout) -> int:
        pixmap_rect = self._image_view.get_pixmap_rect()
        if pixmap_rect is None:
            return 0
        xs, ys = layout.get_boundaries(int(pixmap_rect.width()), int(pixmap_rect.height()))
        count = 0
        for row in range(len(ys) - 1):
            if ys[row + 1] <= ys[row]:
                continue
            for col in range(len(xs) - 1):
                if xs[col + 1] <= xs[col]:
                    continue
                count += 1
        if count == 0 and xs and ys:
            count = max(1, len(xs) - 1) * max(1, len(ys) - 1)
        return max(count, 1)

    def _show_slice_result(self, output_dir: str, tile_count: int) -> None:
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("切图完成")
        msg_box.setText(f"切图完成，共生成 {tile_count} 个切片。")
        msg_box.setInformativeText(f"输出目录：\n{output_dir}")
        open_btn = msg_box.addButton("打开输出文件夹", QMessageBox.ActionRole)
        ok_btn = msg_box.addButton("确定", QMessageBox.AcceptRole)
        msg_box.setDefaultButton(ok_btn)
        msg_box.exec()

        if msg_box.clickedButton() is open_btn:
            self._open_directory(output_dir)

        self.statusBar().showMessage(
            f"切图完成（{tile_count} 个切片）：{output_dir}",
            8000,
        )

    def _open_directory(self, directory: str) -> None:
        if not directory:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))
