from __future__ import annotations

import os
from typing import Sequence

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


class ImageApp:
    def __init__(self, argv: Sequence[str]) -> None:
        self._app = QApplication(list(argv))
        self._main_window = MainWindow()
        self._configure_app()

    def _configure_app(self) -> None:
        self._app.setApplicationName("Img Slicer Tool")
        self._app.setOrganizationName("LocalDev")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "..", "resources", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self._app.setWindowIcon(QIcon(icon_path))

        qss_path = os.path.join(base_dir, "..", "resources", "qss", "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as file:
                self._app.setStyleSheet(file.read())

    def run(self) -> int:
        self._main_window.show()
        return self._app.exec()
