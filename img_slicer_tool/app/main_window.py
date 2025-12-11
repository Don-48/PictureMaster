from __future__ import annotations

import os
from typing import Optional

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMainWindow, QMessageBox

from models.image_document import ImageDocument
from services.crop_service import crop_document_to_new_image
from services.image_loader import load_image_document
from services.slice_service import slice_document_to_tiles
from views.image_view import ImageView
from views.overlay_items import GuideLineItem


class MainWindow(QMainWindow):
    def __init__(self, parent: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("图片裁剪与切图工具（预览版）")
        self.resize(1200, 800)

        self._image_view = ImageView(self)
        self.setCentralWidget(self._image_view)
        self._current_document: Optional[ImageDocument] = None
        self._slice_output_root: Optional[str] = None

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
        self._toggle_slice_mode_action.toggled.connect(self._on_toggle_slice_mode)
        self._generate_grid_action.triggered.connect(self._on_generate_grid_from_rows_cols)
        self._execute_slice_action.triggered.connect(self._on_execute_slice)
        self._set_slice_output_dir_action.triggered.connect(self._on_set_slice_output_dir)

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
            self.statusBar().showMessage(
                "已进入切图模式：点击生成切图线（默认十字线，Shift=横线，Ctrl=竖线）",
                5000,
            )
        else:
            self._image_view.set_mode(self._image_view.MODE_CROP)
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

        pixmap_rect = self._image_view.get_pixmap_rect()
        if pixmap_rect is None:
            QMessageBox.warning(self, "提示", "未找到预览图，无法生成宫格线。")
            return

        rows, ok_rows = QInputDialog.getInt(self, "输入行数", "切图行数（>=1）：", 2, 1, 100)
        if not ok_rows:
            return

        cols, ok_cols = QInputDialog.getInt(self, "输入列数", "切图列数（>=1）：", 2, 1, 100)
        if not ok_cols:
            return

        h_step = pixmap_rect.height() / rows
        v_step = pixmap_rect.width() / cols

        for i in range(1, rows):
            y = pixmap_rect.top() + h_step * i
            self._image_view.add_slice_line(GuideLineItem.HORIZONTAL, y)

        for j in range(1, cols):
            x = pixmap_rect.left() + v_step * j
            self._image_view.add_slice_line(GuideLineItem.VERTICAL, x)

        self.statusBar().showMessage(f"已生成 {rows}x{cols} 宫格切图线（不含边界线）。", 5000)

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

        QMessageBox.information(self, "切图完成", f"切图已完成，保存于目录：\n{output_dir}")
        self.statusBar().showMessage(f"切图完成：{output_dir}", 8000)
