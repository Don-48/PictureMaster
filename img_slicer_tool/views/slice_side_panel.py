from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class SliceSidePanel(QWidget):
    """切图模式左侧工作栏。"""

    sliceModeChanged = Signal(str)
    gridValueChanged = Signal(int, int)
    lineToolChanged = Signal(str)
    executeRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sliceSidePanel")
        self.setFixedWidth(260)
        self._current_mode = "manual"
        self._block_mode_change = False
        self._block_grid_change = False
        self._block_tool_change = False
        self._tool_buttons: dict[str, QToolButton] = {}

        self._init_ui()
        self.set_slice_mode("manual")

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        layout.addWidget(self._build_mode_group())
        layout.addWidget(self._build_grid_section())
        layout.addWidget(self._build_manual_tools_section())
        layout.addWidget(self._build_select_tool_section())
        layout.addStretch(1)

        self._execute_button = QPushButton("执行切图", self)
        self._execute_button.setObjectName("executeSliceButton")
        self._execute_button.clicked.connect(self.executeRequested)
        layout.addWidget(self._execute_button)

    def _build_mode_group(self) -> QWidget:
        group = QGroupBox("切图方式", self)
        v_layout = QVBoxLayout(group)
        self._grid_radio = QRadioButton("行列生成网格", group)
        self._manual_radio = QRadioButton("手动生成切割线", group)
        self._manual_radio.setChecked(True)

        self._grid_radio.toggled.connect(self._on_mode_toggled)
        self._manual_radio.toggled.connect(self._on_mode_toggled)

        v_layout.addWidget(self._grid_radio)
        v_layout.addWidget(self._manual_radio)
        return group

    def _build_grid_section(self) -> QWidget:
        self._grid_section = QGroupBox("行列生成网格", self)
        form = QFormLayout(self._grid_section)
        self._rows_spin = QSpinBox(self._grid_section)
        self._rows_spin.setRange(1, 50)
        self._rows_spin.setValue(2)
        self._cols_spin = QSpinBox(self._grid_section)
        self._cols_spin.setRange(1, 50)
        self._cols_spin.setValue(2)

        self._rows_spin.valueChanged.connect(self._on_grid_values_changed)
        self._cols_spin.valueChanged.connect(self._on_grid_values_changed)

        form.addRow(QLabel("行数:", self._grid_section), self._rows_spin)
        form.addRow(QLabel("列数:", self._grid_section), self._cols_spin)
        return self._grid_section

    def _build_manual_tools_section(self) -> QWidget:
        self._manual_tools_group = QGroupBox("手动切割线工具", self)
        tool_layout = QHBoxLayout(self._manual_tools_group)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        for tool, label in [
            ("horizontal", "水平线"),
            ("vertical", "垂直线"),
            ("cross", "十字线"),
        ]:
            btn = QToolButton(self._manual_tools_group)
            btn.setText(label)
            btn.setCheckable(True)
            self._tool_group.addButton(btn)
            self._tool_buttons[tool] = btn
            btn.toggled.connect(lambda checked, key=tool: self._on_tool_toggled(key, checked))
            tool_layout.addWidget(btn)

        # 默认工具：十字线
        self._tool_buttons["cross"].setChecked(True)
        return self._manual_tools_group

    def _build_select_tool_section(self) -> QWidget:
        self._select_group = QGroupBox("鼠标选择工具", self)
        v_layout = QVBoxLayout(self._select_group)
        select_btn = QToolButton(self._select_group)
        select_btn.setText("选择切割线")
        select_btn.setCheckable(True)
        self._tool_group.addButton(select_btn)
        self._tool_buttons["select"] = select_btn
        select_btn.toggled.connect(lambda checked: self._on_tool_toggled("select", checked))
        v_layout.addWidget(select_btn)
        return self._select_group

    def set_slice_mode(self, mode: str) -> None:
        if mode not in {"grid", "manual"}:
            return
        self._block_mode_change = True
        if mode == "grid":
            self._grid_radio.setChecked(True)
        else:
            self._manual_radio.setChecked(True)
        self._block_mode_change = False
        self._current_mode = mode
        self._update_section_visibility()

    def set_grid_values(self, rows: int, cols: int) -> None:
        self._block_grid_change = True
        self._rows_spin.setValue(rows)
        self._cols_spin.setValue(cols)
        self._block_grid_change = False

    def set_line_tool(self, tool: str) -> None:
        btn = self._tool_buttons.get(tool)
        if btn is None:
            return
        self._block_tool_change = True
        btn.setChecked(True)
        self._block_tool_change = False

    def _on_mode_toggled(self) -> None:
        if self._block_mode_change:
            return
        mode = "grid" if self._grid_radio.isChecked() else "manual"
        if mode == self._current_mode:
            return
        self._current_mode = mode
        self._update_section_visibility()
        self.sliceModeChanged.emit(mode)

    def _update_section_visibility(self) -> None:
        is_grid = self._current_mode == "grid"
        self._grid_section.setVisible(is_grid)
        self._manual_tools_group.setVisible(not is_grid)
        self._select_group.setVisible(not is_grid)

    def _on_grid_values_changed(self) -> None:
        if self._block_grid_change:
            return
        self.gridValueChanged.emit(self._rows_spin.value(), self._cols_spin.value())

    def _on_tool_toggled(self, tool: str, checked: bool) -> None:
        if not checked or self._block_tool_change:
            return
        self.lineToolChanged.emit(tool)
