"""Entry point for the AMR operator GUI."""

import base64
import json
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QProcess, QSettings, QSize, QTimer, Qt
from PyQt5.QtGui import QColor, QIcon, QKeySequence, QTextCharFormat
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from amr_operator_gui.local_rviz import (
    DEFAULT_LOCAL_WORKSPACE,
    rviz_launch_command,
)
from amr_operator_gui.local_vscode import vscode_remote_arguments
from amr_operator_gui.health_model import (
    HEALTH_MARKER,
    evaluate_health,
    overall_health,
)
from amr_operator_gui.network_diagnostics import (
    diagnostic_probe_command,
    diagnostic_summary,
    local_diagnostic_probe_command,
    parse_probe_output,
)
from amr_operator_gui.parameter_tuning import ParameterDocument
from amr_operator_gui.remote_bringup import (
    DEFAULT_REMOTE_WORKSPACE,
    RUNNING_MARKER,
    STOPPED_MARKER,
    TMUX_MISSING_MARKER,
    bringup_status_command,
    restart_bringup_command,
    start_bringup_command,
    stop_bringup_command,
)
from amr_operator_gui.remote_localization import (
    LOCALIZATION_RUNNING_MARKER,
    LOCALIZATION_STOPPED_MARKER,
    TMUX_MISSING_MARKER as LOCALIZATION_TMUX_MISSING_MARKER,
    localization_status_command,
    map_list_command,
    start_localization_command,
    stop_localization_command,
)
from amr_operator_gui.remote_mapping import (
    MAPPING_RUNNING_MARKER,
    MAPPING_STOPPED_MARKER,
    TMUX_MISSING_MARKER as MAPPING_TMUX_MISSING_MARKER,
    mapping_status_command,
    save_map_command,
    start_mapping_command,
    stop_mapping_command,
)
from amr_operator_gui.remote_health import system_health_probe_command
from amr_operator_gui.remote_navigation import (
    NAVIGATION_RUNNING_MARKER,
    NAVIGATION_STOPPED_MARKER,
    TMUX_MISSING_MARKER as NAVIGATION_TMUX_MISSING_MARKER,
    navigation_status_command,
    restart_navigation_command,
    start_navigation_command,
    stop_navigation_command,
)
from amr_operator_gui.remote_power import (
    SHUTDOWN_AUTHORIZED_MARKER,
    SHUTDOWN_PERMISSION_DENIED_MARKER,
    shutdown_command,
)
from amr_operator_gui.remote_parameters import (
    PARAMETER_CONFLICT_MARKER,
    PARAMETER_FILE_MARKER,
    PARAMETER_SAVE_MARKER,
    content_sha256,
    live_parameter_command,
    parameter_file_list_command,
    parameter_file_read_command,
    parameter_file_write_command,
)
from amr_operator_gui.ssh_connection import (
    SshSettings,
    connection_test_arguments,
    remote_command_arguments,
)


DARK_STYLESHEET = """
QWidget {
    color: #e6edf3;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10.5pt;
}
QMainWindow, QMessageBox, QWidget#AppRoot { background-color: #0f151c; }
QFrame[panel="true"] {
    background-color: #17212b;
    border: 1px solid #2c3a47;
    border-radius: 7px;
}
QFrame[subpanel="true"] {
    background-color: #131c25;
    border: 1px solid #293744;
    border-radius: 6px;
}
QLabel[heading="true"] {
    color: #f0f6fc;
    font-size: 11pt;
    font-weight: 700;
}
QLabel[muted="true"] { color: #9aabba; }
QLabel[dependency="true"] { color: #8ea0b1; font-size: 9pt; }
QLabel[mission="true"] { color: #58a6ff; font-weight: 600; }
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTableWidget, QTreeWidget {
    background-color: #0d1319;
    color: #f0f6fc;
    border: 1px solid #354655;
    border-radius: 4px;
    padding: 5px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus,
QTableWidget:focus, QTreeWidget:focus {
    border: 1px solid #58a6ff;
}
QPushButton {
    background-color: #263442;
    color: #f0f6fc;
    border: 1px solid #415466;
    border-radius: 5px;
    padding: 7px 12px;
    min-height: 18px;
}
QPushButton:hover { background-color: #314354; border-color: #5a7187; }
QPushButton:pressed { background-color: #1c2833; }
QPushButton:disabled {
    background-color: #1a232c;
    color: #647484;
    border-color: #2b3742;
}
QPushButton[role="start"] {
    background-color: #17663a;
    border-color: #2ea75f;
}
QPushButton[role="start"]:hover { background-color: #21834d; }
QPushButton[role="stop"] {
    background-color: #7d2929;
    border-color: #c14b4b;
}
QPushButton[role="stop"]:hover { background-color: #983737; }
QPushButton[role="action"] {
    background-color: #174f83;
    border-color: #2f81d1;
}
QPushButton[role="action"]:hover { background-color: #1f659f; }
QPushButton[role="quiet"] { background-color: transparent; border-color: #354655; }
QPushButton[role="start"]:disabled,
QPushButton[role="stop"]:disabled,
QPushButton[role="action"]:disabled {
    background-color: #1a232c;
    color: #647484;
    border-color: #2b3742;
}
QTabWidget::pane { border: 1px solid #354655; background-color: #111922; }
QTabBar::tab {
    background-color: #17212b;
    color: #aebdca;
    padding: 8px 14px;
    border: 1px solid #2c3a47;
}
QTabBar::tab:selected { background-color: #223140; color: #ffffff; border-bottom: 2px solid #58a6ff; }
QTableWidget, QTreeWidget {
    gridline-color: #2c3a47;
    alternate-background-color: #131c25;
}
QHeaderView::section {
    background-color: #202d39;
    color: #f0f6fc;
    border: 1px solid #354655;
    padding: 8px;
    font-weight: 600;
}
QToolButton { color: #dce5ed; padding: 5px; }
QCheckBox { spacing: 7px; }
QSplitter::handle { background-color: #354655; }
QSplitter::handle:vertical { height: 4px; }
QSplitter::handle:horizontal { width: 4px; }
QTreeWidget#ParameterTree { font-size: 11pt; }
QTreeWidget#ParameterTree QLineEdit,
QTreeWidget#ParameterTree QPushButton { font-size: 10.5pt; min-height: 22px; }
QToolTip {
    background-color: #101419;
    color: #f0f4f8;
    border: 1px solid #637180;
    padding: 4px;
}
QScrollBar:vertical { background: #111820; width: 12px; }
QScrollBar::handle:vertical { background: #415466; min-height: 28px; border-radius: 5px; }
"""

LIGHT_STYLESHEET = """
QWidget {
    color: #1f2328;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10.5pt;
}
QMainWindow, QMessageBox, QWidget#AppRoot { background-color: #f5f7fa; }
QFrame[panel="true"] {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 7px;
}
QFrame[subpanel="true"] {
    background-color: #f8fafc;
    border: 1px solid #d8dee4;
    border-radius: 6px;
}
QLabel[heading="true"] { color: #1f2328; font-size: 11pt; font-weight: 700; }
QLabel[muted="true"] { color: #57606a; }
QLabel[dependency="true"] { color: #6e7781; font-size: 9pt; }
QLabel[mission="true"] { color: #0969da; font-weight: 600; }
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTableWidget, QTreeWidget {
    background-color: #ffffff;
    color: #171b1f;
    border: 1px solid #b8c2cc;
    border-radius: 4px;
    padding: 4px;
    selection-background-color: #8fc5eb;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus,
QTableWidget:focus, QTreeWidget:focus {
    border: 1px solid #2479b5;
}
QPushButton {
    background-color: #eef2f6;
    color: #20262c;
    border: 1px solid #aab4be;
    border-radius: 5px;
    padding: 6px 11px;
}
QPushButton:hover { background-color: #e1e7ed; border-color: #8c99a5; }
QPushButton:pressed { background-color: #c8d2dc; }
QPushButton:disabled {
    background-color: #edf0f3;
    color: #919ba4;
    border-color: #d4dae0;
}
QPushButton[role="start"] {
    background-color: #1f883d;
    color: #ffffff;
    border-color: #1a7f37;
}
QPushButton[role="start"]:hover { background-color: #1a7f37; }
QPushButton[role="stop"] {
    background-color: #cf222e;
    color: #ffffff;
    border-color: #a40e26;
}
QPushButton[role="stop"]:hover { background-color: #a40e26; }
QPushButton[role="action"] {
    background-color: #0969da;
    color: #ffffff;
    border-color: #0550ae;
}
QPushButton[role="action"]:hover { background-color: #0550ae; }
QPushButton[role="quiet"] { background-color: transparent; color: #1f2328; border-color: #b8c2cc; }
QPushButton[role="start"]:disabled,
QPushButton[role="stop"]:disabled,
QPushButton[role="action"]:disabled {
    background-color: #edf0f3;
    color: #8c959f;
    border-color: #d0d7de;
}
QTabWidget::pane { border: 1px solid #d0d7de; background-color: #ffffff; }
QTabBar::tab {
    background-color: #e4e9ee;
    color: #43505c;
    padding: 7px 13px;
    border: 1px solid #b9c2ca;
}
QTabBar::tab:selected { background-color: #ffffff; color: #15191d; border-bottom: 2px solid #0969da; }
QTableWidget, QTreeWidget {
    gridline-color: #c6ced6;
    alternate-background-color: #edf1f4;
}
QHeaderView::section {
    background-color: #e4e9ee;
    color: #20262c;
    border: 1px solid #b9c2ca;
    padding: 8px;
    font-weight: 600;
}
QToolButton { color: #26313a; padding: 5px; }
QCheckBox { spacing: 7px; }
QSplitter::handle { background-color: #c5cdd5; }
QSplitter::handle:vertical { height: 4px; }
QSplitter::handle:horizontal { width: 4px; }
QTreeWidget#ParameterTree { font-size: 11pt; }
QTreeWidget#ParameterTree QLineEdit,
QTreeWidget#ParameterTree QPushButton { font-size: 10.5pt; min-height: 22px; }
QToolTip {
    background-color: #ffffff;
    color: #171b1f;
    border: 1px solid #8f9aa5;
    padding: 4px;
}
QScrollBar:vertical { background: #e5e9ed; width: 12px; }
QScrollBar::handle:vertical { background: #a9b3bd; min-height: 24px; }
"""

DEFAULT_LOG_FONT_SIZE = 10
MIN_LOG_FONT_SIZE = 7
MAX_LOG_FONT_SIZE = 24

APPLICATION_ICON_PATH = (
    Path(__file__).resolve().parent / "icons" / "amr_operator_gui.svg"
)


class CollapsibleSection(QWidget):
    """Compact section whose content can be expanded when settings are needed."""

    def __init__(self, title: str, expanded: bool = False, parent=None) -> None:
        super().__init__(parent)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(2)

        self._toggle = QToolButton()
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._toggle.setStyleSheet("QToolButton { font-weight: 600; border: none; }")
        self._toggle.toggled.connect(self._set_expanded)
        outer_layout.addWidget(self._toggle)

        self._content = QWidget()
        self._content.setVisible(expanded)
        outer_layout.addWidget(self._content)

    def set_content_layout(self, layout) -> None:
        """Install the layout shown beneath the section toggle."""
        self._content.setLayout(layout)

    def set_expanded(self, expanded: bool) -> None:
        """Expose expansion so a toolbar settings action can control it."""
        self._toggle.setChecked(expanded)

    def toggle(self) -> None:
        """Toggle the section from an external command button."""
        self._toggle.toggle()

    def _set_expanded(self, expanded: bool) -> None:
        self._toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._content.setVisible(expanded)


class OperatorWindow(QMainWindow):
    """Operator window for robot bringup, localization, logs, and RViz."""

    MONITOR_INTERVAL_MS = 10000
    BRINGUP_POLL_INTERVAL_MS = 2500

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AMR Operator")
        self.setWindowIcon(QIcon(str(APPLICATION_ICON_PATH)))
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)

        self._settings = QSettings("AMR", "AMR Operator")
        self._dark_theme = self._settings.value(
            "appearance/dark_theme", True, type=bool
        )
        self._log_font_size = self._settings.value(
            "appearance/log_font_size", DEFAULT_LOG_FONT_SIZE, type=int
        )
        self._log_font_size = max(
            MIN_LOG_FONT_SIZE,
            min(MAX_LOG_FONT_SIZE, self._log_font_size),
        )
        self._ssh_process = None
        self._connection_check_queue = []
        self._connection_route_under_test = ""
        self._wifi_connected = False
        self._ethernet_connected = False
        self._active_route = "wifi"
        self._diagnostic_local_process = None
        self._diagnostic_remote_process = None
        self._diagnostic_local_output = ""
        self._shutdown_process = None
        self._parameter_file_list_process = None
        self._parameter_read_process = None
        self._parameter_write_process = None
        self._parameter_live_process = None
        self._parameter_document = None
        self._parameter_current_file = ""
        self._parameter_source_sha256 = ""
        self._parameter_saved_content = ""
        self._parameter_tree_building = False
        self._parameter_favorites = set()
        self._parameter_items = {}
        self._parameter_value_edits = {}
        self._parameter_action_buttons = {}
        self._parameter_invalid_edits = set()
        self._pending_parameter_file = ""
        self._pending_parameter_restart = ""
        self._close_after_parameter_save = False
        self._allow_close = False
        self._bringup_status_process = None
        self._bringup_operation_process = None
        self._rviz_process = None
        self._map_list_process = None
        self._localization_status_process = None
        self._localization_operation_process = None
        self._tf_probe_process = None
        self._tf_probe_buffer = ""
        self._tf_last_transform_time = 0.0
        self._bringup_operation_action = ""
        self._mapping_status_process = None
        self._mapping_operation_process = None
        self._mapping_running = False
        self._mapping_state_known = False
        self._navigation_status_process = None
        self._navigation_operation_process = None
        self._navigation_running = False
        self._navigation_state_known = False
        self._nav_health_process = None
        self._nav_health_buffer = ""
        self._nav_action_last_ready_time = 0.0
        self._system_health_process = None
        self._system_health_buffer = ""
        self._system_health_last_snapshot_time = 0.0
        self._health_snapshot = None
        self._health_checks = []
        self._health_previous_states = {}
        self._health_previously_healthy = set()
        self._launch_intent = {
            "bringup": None,
            "localization": None,
            "mapping": None,
            "nav2": None,
        }
        self._launch_intent_time = {
            name: time.monotonic() for name in self._launch_intent
        }
        self._check_was_manual = False
        self._ssh_connected = False
        self._bringup_running = False
        self._bringup_state_known = False
        self._localization_running = False
        self._localization_state_known = False
        self._saved_map_name = "LakecityFlat4AMap.yaml"

        self._build_mission_control_ui()
        self._load_settings()
        self._apply_theme()
        self._apply_log_font_size()

        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(self.MONITOR_INTERVAL_MS)
        self._monitor_timer.timeout.connect(self._automatic_connection_test)
        self._auto_monitor.toggled.connect(self._set_auto_monitoring)
        self._set_auto_monitoring(self._auto_monitor.isChecked())
        self._automatic_fallback.toggled.connect(
            self._fallback_policy_changed
        )

        self._bringup_timer = QTimer(self)
        self._bringup_timer.setInterval(self.BRINGUP_POLL_INTERVAL_MS)
        self._bringup_timer.timeout.connect(self._poll_bringup)
        self._bringup_timer.start()

        self._localization_timer = QTimer(self)
        self._localization_timer.setInterval(self.BRINGUP_POLL_INTERVAL_MS)
        self._localization_timer.timeout.connect(self._poll_localization)
        self._localization_timer.start()

        self._mapping_timer = QTimer(self)
        self._mapping_timer.setInterval(self.BRINGUP_POLL_INTERVAL_MS)
        self._mapping_timer.timeout.connect(self._poll_mapping)
        self._mapping_timer.start()

        self._navigation_timer = QTimer(self)
        self._navigation_timer.setInterval(self.BRINGUP_POLL_INTERVAL_MS)
        self._navigation_timer.timeout.connect(self._poll_navigation)
        self._navigation_timer.start()

        self._tf_health_timer = QTimer(self)
        self._tf_health_timer.setInterval(1000)
        self._tf_health_timer.timeout.connect(self._update_tf_health)
        self._tf_health_timer.timeout.connect(self._update_nav_health)
        self._tf_health_timer.timeout.connect(self._update_system_health)
        self._tf_health_timer.start()

        QTimer.singleShot(
            400, lambda: self._start_connection_checks(manual=False)
        )

    def _panel(self, title: str, subtitle: str = ""):
        frame = QFrame()
        frame.setProperty("panel", True)
        panel_layout = QVBoxLayout(frame)
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(8)
        heading = QLabel(title.upper())
        heading.setProperty("heading", True)
        panel_layout.addWidget(heading)
        if subtitle:
            supporting_text = QLabel(subtitle)
            supporting_text.setProperty("muted", True)
            supporting_text.setWordWrap(True)
            panel_layout.addWidget(supporting_text)
        return frame, panel_layout

    @staticmethod
    def _subpanel() -> tuple:
        frame = QFrame()
        frame.setProperty("subpanel", True)
        panel_layout = QVBoxLayout(frame)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(7)
        return frame, panel_layout

    @staticmethod
    def _status_widget(dot: QLabel, text: QLabel, secondary=None) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        primary = QHBoxLayout()
        primary.setContentsMargins(0, 0, 0, 0)
        primary.setSpacing(6)
        primary.addWidget(dot)
        primary.addWidget(text, stretch=1)
        layout.addLayout(primary)
        if secondary is not None:
            secondary_row = QHBoxLayout()
            secondary_row.setContentsMargins(0, 0, 0, 0)
            secondary_row.setSpacing(6)
            secondary_row.addSpacing(20)
            if isinstance(secondary, tuple):
                secondary_row.addWidget(secondary[0])
                secondary_row.addWidget(secondary[1], stretch=1)
            else:
                secondary_row.addWidget(secondary, stretch=1)
            layout.addLayout(secondary_row)
        return widget

    @staticmethod
    def _stack_layer(step: int, title: str, dependency: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(3)
        name = QLabel("{}   {}".format(step, title))
        name.setStyleSheet("font-weight: 700;")
        layout.addWidget(name)
        depends = QLabel(dependency)
        depends.setProperty("dependency", True)
        layout.addWidget(depends)
        return widget

    @staticmethod
    def _icon(theme_names, standard_icon=None, file_paths=()) -> QIcon:
        for filename in file_paths:
            path = Path(filename).expanduser()
            if path.is_file():
                return QIcon(str(path))
        for name in theme_names:
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                return icon
        app = QApplication.instance()
        if app is not None and standard_icon is not None:
            return app.style().standardIcon(standard_icon)
        return QIcon()

    def _decorate_button(
        self, button: QPushButton, theme_names, standard_icon=None,
        file_paths=()
    ) -> None:
        button.setIcon(self._icon(theme_names, standard_icon, file_paths))
        button.setIconSize(QSize(18, 18))

    def _build_mission_control_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("AppRoot")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(10)
        app_mark = QLabel()
        app_mark.setPixmap(QIcon(str(APPLICATION_ICON_PATH)).pixmap(30, 30))
        header.addWidget(app_mark)
        title = QLabel("AMR OPERATOR")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        header.addWidget(title)
        mission = QLabel("Mission Control")
        mission.setProperty("mission", True)
        header.addWidget(mission)
        header.addStretch()

        self._launch_rviz_button = QPushButton("Launch RViz")
        self._launch_rviz_button.setProperty("role", "quiet")
        self._launch_rviz_button.clicked.connect(self._launch_rviz)
        self._decorate_button(
            self._launch_rviz_button,
            ("media-playback-start", "applications-graphics"),
            QStyle.SP_MediaPlay,
        )
        header.addWidget(self._launch_rviz_button)

        self._open_vscode_button = QPushButton("Open VS Code")
        self._open_vscode_button.setProperty("role", "quiet")
        self._open_vscode_button.setToolTip(
            "Open this repository on the Jetson through VS Code Remote-SSH. "
            "The repository setting focuses the Codex sidebar on startup."
        )
        self._open_vscode_button.clicked.connect(self._open_vscode)
        self._decorate_button(
            self._open_vscode_button,
            ("visual-studio-code", "com.visualstudio.code", "code"),
            QStyle.SP_ComputerIcon,
            (
                "/snap/code/current/meta/gui/vscode.png",
                "/snap/code/current/snap/gui/vscode.png",
                "/usr/share/pixmaps/code.png",
            ),
        )
        header.addWidget(self._open_vscode_button)

        self._show_health_button = QPushButton("System Health")
        self._show_health_button.setProperty("role", "quiet")
        self._show_health_button.clicked.connect(self._show_system_health)
        self._decorate_button(
            self._show_health_button,
            ("emblem-default", "dialog-information"),
            QStyle.SP_DialogApplyButton,
        )
        header.addWidget(self._show_health_button)

        self._settings_button = QPushButton("Settings")
        self._settings_button.setProperty("role", "quiet")
        self._decorate_button(
            self._settings_button,
            ("preferences-system", "settings-configure"),
            QStyle.SP_FileDialogDetailedView,
        )
        header.addWidget(self._settings_button)

        self._theme_button = QPushButton()
        self._theme_button.setProperty("role", "quiet")
        self._theme_button.setToolTip(
            "Switch between the dark and light application themes."
        )
        self._theme_button.clicked.connect(self._toggle_theme)
        header.addWidget(self._theme_button)

        self._shutdown_jetson_button = QPushButton("Shutdown Jetson")
        self._shutdown_jetson_button.setProperty("role", "stop")
        self._shutdown_jetson_button.setToolTip(
            "Safely power off the Jetson over the currently active SSH route."
        )
        self._shutdown_jetson_button.clicked.connect(self._shutdown_jetson)
        self._decorate_button(
            self._shutdown_jetson_button,
            ("system-shutdown",),
            QStyle.SP_DialogCloseButton,
        )
        header.addWidget(self._shutdown_jetson_button)
        layout.addLayout(header)

        self._settings_section = CollapsibleSection(
            "Connection & environment settings"
        )
        settings_grid = QGridLayout()
        settings_grid.setContentsMargins(8, 4, 8, 8)
        settings_grid.setHorizontalSpacing(16)
        settings_grid.setVerticalSpacing(8)

        wifi_form = QFormLayout()
        wifi_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._host = QLineEdit()
        self._host.setPlaceholderText("Jetson IP address or SSH alias")
        wifi_form.addRow("Wi-Fi host", self._host)
        self._username = QLineEdit()
        wifi_form.addRow("Username", self._username)
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        wifi_form.addRow("SSH port", self._port)
        settings_grid.addWidget(QLabel("Primary SSH"), 0, 0)
        settings_grid.addLayout(wifi_form, 1, 0)

        fallback_form = QFormLayout()
        fallback_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._ethernet_host = QLineEdit()
        self._ethernet_host.setPlaceholderText("e.g. nano_ethernet")
        fallback_form.addRow("Ethernet alias", self._ethernet_host)
        self._identity_file = QLineEdit()
        self._identity_file.setPlaceholderText("Optional private key")
        fallback_form.addRow("Private key", self._identity_file)
        self._automatic_fallback = QCheckBox(
            "Use Ethernet automatically when Wi-Fi SSH fails"
        )
        self._automatic_fallback.setChecked(True)
        self._automatic_fallback.setToolTip(
            "Wi-Fi remains preferred. Commands switch to Ethernet only while "
            "the Wi-Fi route is unavailable."
        )
        fallback_form.addRow("", self._automatic_fallback)
        settings_grid.addWidget(QLabel("Fallback route"), 0, 1)
        settings_grid.addLayout(fallback_form, 1, 1)

        robot_form = QFormLayout()
        robot_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._remote_workspace = QLineEdit()
        self._remote_workspace.setPlaceholderText("Jetson ros2_ws path")
        robot_form.addRow("Workspace", self._remote_workspace)
        self._domain_id = QSpinBox()
        self._domain_id.setRange(0, 232)
        robot_form.addRow("ROS domain", self._domain_id)
        self._rmw_implementation = QLineEdit()
        robot_form.addRow("RMW", self._rmw_implementation)
        settings_grid.addWidget(QLabel("Robot environment"), 0, 2)
        settings_grid.addLayout(robot_form, 1, 2)

        local_form = QFormLayout()
        local_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._local_workspace = QLineEdit()
        self._local_workspace.setPlaceholderText("Development ros2_ws path")
        local_form.addRow("Workspace", self._local_workspace)
        settings_grid.addWidget(QLabel("Local RViz environment"), 0, 3)
        settings_grid.addLayout(local_form, 1, 3)
        for column in range(4):
            settings_grid.setColumnStretch(column, 1)
        self._settings_section.set_content_layout(settings_grid)
        self._settings_button.clicked.connect(self._settings_section.toggle)
        layout.addWidget(self._settings_section)

        connection_frame = QFrame()
        connection_frame.setProperty("panel", True)
        connection_row = QHBoxLayout(connection_frame)
        connection_row.setContentsMargins(13, 8, 13, 8)
        connection_row.setSpacing(8)
        connection_row.addWidget(QLabel("Connection"))
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._status_text = QLabel("Not checked")
        self._status_text.setStyleSheet("font-weight: 600;")
        connection_row.addWidget(self._status_dot)
        connection_row.addWidget(self._status_text)
        connection_row.addSpacing(16)
        self._wifi_route_dot = QLabel("●")
        self._wifi_route_dot.setStyleSheet("font-size: 16px; color: #777;")
        self._wifi_route_text = QLabel("Wi-Fi SSH unchecked")
        connection_row.addWidget(self._wifi_route_dot)
        connection_row.addWidget(self._wifi_route_text)
        connection_row.addSpacing(12)
        self._ethernet_route_dot = QLabel("●")
        self._ethernet_route_dot.setStyleSheet("font-size: 16px; color: #777;")
        self._ethernet_route_text = QLabel("Ethernet SSH unchecked")
        connection_row.addWidget(self._ethernet_route_dot)
        connection_row.addWidget(self._ethernet_route_text)
        connection_row.addStretch()
        self._auto_monitor = QCheckBox("Check every 10 seconds")
        self._auto_monitor.setChecked(True)
        connection_row.addWidget(self._auto_monitor)
        self._test_button = QPushButton("Test SSH routes")
        self._test_button.setProperty("role", "action")
        self._test_button.clicked.connect(self._manual_connection_test)
        connection_row.addWidget(self._test_button)
        self._diagnose_button = QPushButton("Diagnose network")
        self._diagnose_button.setProperty("role", "action")
        self._diagnose_button.setToolTip(
            "Run read-only route, peer, gateway, internet-IP, and DNS checks "
            "on both the development machine and Jetson."
        )
        self._diagnose_button.clicked.connect(self._start_network_diagnostics)
        self._decorate_button(
            self._diagnose_button,
            ("network-wired", "network-transmit-receive"),
            QStyle.SP_DriveNetIcon,
        )
        connection_row.addWidget(self._diagnose_button)
        layout.addWidget(connection_frame)

        operations = QSplitter(Qt.Horizontal)
        operations.setChildrenCollapsible(False)

        stack_frame, stack_layout = self._panel(
            "Robot stack",
            "Start the physical robot layers in order. Stop actions safely "
            "close dependent layers first.",
        )
        stack_table = QFrame()
        stack_table.setProperty("subpanel", True)
        stack_grid = QGridLayout(stack_table)
        stack_grid.setContentsMargins(12, 8, 12, 8)
        stack_grid.setHorizontalSpacing(12)
        stack_grid.setVerticalSpacing(8)
        for column, text in enumerate(
            ("LAYER", "STATUS", "CONFIGURATION", "PRIMARY ACTION", "STOP")
        ):
            label = QLabel(text)
            label.setProperty("muted", True)
            label.setStyleSheet("font-size: 9pt; font-weight: 700;")
            stack_grid.addWidget(label, 0, column)

        self._bringup_status_dot = QLabel("●")
        self._bringup_status_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._bringup_status_text = QLabel("Bringup status unknown")
        self._bringup_status_text.setStyleSheet("font-weight: 600;")
        self._bringup_status_text.setWordWrap(True)
        self._show_start_confirmation = QCheckBox("Confirm start")
        self._show_start_confirmation.setChecked(True)
        self._show_start_confirmation.setToolTip(
            "Uncheck to suppress the physical-hardware start warning."
        )
        self._start_bringup_button = QPushButton("Start bringup")
        self._start_bringup_button.setProperty("role", "start")
        self._start_bringup_button.clicked.connect(self._start_robot_bringup)
        self._stop_bringup_button = QPushButton("Stop")
        self._stop_bringup_button.setProperty("role", "stop")
        self._stop_bringup_button.setToolTip(
            "Stop Nav2 and localization or mapping first, then stop Bringup."
        )
        self._stop_bringup_button.clicked.connect(self._stop_robot_bringup)
        stack_grid.addWidget(self._stack_layer(1, "Bringup", "No dependencies"), 1, 0)
        stack_grid.addWidget(
            self._status_widget(
                self._bringup_status_dot, self._bringup_status_text
            ), 1, 1
        )
        stack_grid.addWidget(self._show_start_confirmation, 1, 2)
        stack_grid.addWidget(self._start_bringup_button, 1, 3)
        stack_grid.addWidget(self._stop_bringup_button, 1, 4)

        self._localization_status_dot = QLabel("●")
        self._localization_status_dot.setStyleSheet(
            "font-size: 18px; color: #777;"
        )
        self._localization_status_text = QLabel("Localization status unknown")
        self._localization_status_text.setStyleSheet("font-weight: 600;")
        self._localization_status_text.setWordWrap(True)
        map_controls = QWidget()
        map_layout = QVBoxLayout(map_controls)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(5)
        self._map_selector = QComboBox()
        self._map_selector.setMinimumWidth(205)
        self._refresh_maps_button = QPushButton("Refresh maps")
        self._refresh_maps_button.clicked.connect(self._refresh_maps)
        self._start_localization_button = QPushButton("Start localization")
        self._start_localization_button.setProperty("role", "start")
        self._start_localization_button.clicked.connect(self._start_localization)
        self._stop_localization_button = QPushButton("Stop")
        self._stop_localization_button.setProperty("role", "stop")
        self._stop_localization_button.setToolTip(
            "Stop Nav2 first when necessary, then stop localization."
        )
        self._stop_localization_button.clicked.connect(self._stop_localization)
        map_layout.addWidget(self._map_selector)
        map_layout.addWidget(self._refresh_maps_button)
        stack_grid.addWidget(
            self._stack_layer(2, "Localization", "Depends on Bringup"), 2, 0
        )
        stack_grid.addWidget(
            self._status_widget(
                self._localization_status_dot, self._localization_status_text
            ), 2, 1
        )
        stack_grid.addWidget(map_controls, 2, 2)
        stack_grid.addWidget(self._start_localization_button, 2, 3)
        stack_grid.addWidget(self._stop_localization_button, 2, 4)

        self._navigation_status_dot = QLabel("●")
        self._navigation_status_dot.setStyleSheet(
            "font-size: 18px; color: #777;"
        )
        self._navigation_status_text = QLabel("Nav2 status unknown")
        self._navigation_status_text.setStyleSheet("font-weight: 600;")
        self._navigation_status_text.setWordWrap(True)
        self._nav_action_status_dot = QLabel("●")
        self._nav_action_status_dot.setStyleSheet(
            "font-size: 16px; color: #777;"
        )
        self._nav_action_status_text = QLabel("NavigateToPose unavailable")
        self._nav_action_status_text.setWordWrap(True)
        self._nav_action_status_text.setToolTip(
            "Turns green only when bt_navigator's NavigateToPose action server "
            "is discoverable and ready to accept goals."
        )
        self._start_navigation_button = QPushButton("Start Nav2")
        self._start_navigation_button.setProperty("role", "start")
        self._start_navigation_button.clicked.connect(self._start_navigation)
        self._stop_navigation_button = QPushButton("Stop")
        self._stop_navigation_button.setProperty("role", "stop")
        self._stop_navigation_button.setToolTip("Stop the Nav2 process.")
        self._stop_navigation_button.clicked.connect(self._stop_navigation)
        stack_grid.addWidget(
            self._stack_layer(3, "Nav2", "Depends on Localization"), 3, 0
        )
        stack_grid.addWidget(
            self._status_widget(
                self._navigation_status_dot,
                self._navigation_status_text,
                (self._nav_action_status_dot, self._nav_action_status_text),
            ), 3, 1
        )
        nav_config = QLabel("Uses selected Nav2 YAML")
        nav_config.setProperty("muted", True)
        nav_config.setWordWrap(True)
        stack_grid.addWidget(nav_config, 3, 2)
        stack_grid.addWidget(self._start_navigation_button, 3, 3)
        stack_grid.addWidget(self._stop_navigation_button, 3, 4)
        stack_grid.setColumnStretch(0, 2)
        stack_grid.setColumnStretch(1, 3)
        stack_grid.setColumnStretch(2, 3)
        stack_grid.setColumnStretch(3, 2)
        stack_grid.setColumnStretch(4, 2)
        for button in (
            self._start_bringup_button,
            self._start_localization_button,
            self._start_navigation_button,
        ):
            button.setMinimumWidth(145)
            self._decorate_button(
                button, ("media-playback-start",), QStyle.SP_MediaPlay
            )
        for button in (
            self._stop_bringup_button,
            self._stop_localization_button,
            self._stop_navigation_button,
        ):
            button.setMinimumWidth(100)
            self._decorate_button(
                button, ("process-stop",), QStyle.SP_MediaStop
            )
        self._decorate_button(
            self._refresh_maps_button,
            ("view-refresh",),
            QStyle.SP_BrowserReload,
        )
        # Keep the stack table at its content height. Let the diagnostics pane,
        # rather than the operation rows, absorb extra vertical window space.
        stack_layout.addWidget(stack_table)

        legend = QHBoxLayout()
        legend.addWidget(QLabel("●  Running"))
        legend.addSpacing(12)
        legend.addWidget(QLabel("●  Stopped / inactive"))
        legend.addSpacing(12)
        legend.addWidget(QLabel("●  Waiting / unavailable"))
        legend.addStretch()
        stack_layout.addLayout(legend)
        operations.addWidget(stack_frame)

        tools_frame, tools_layout = self._panel("Tools & alternate mode")
        rviz_panel, rviz_layout = self._subpanel()
        rviz_title = QHBoxLayout()
        rviz_name = QLabel("Unified RViz")
        rviz_name.setStyleSheet("font-weight: 700;")
        rviz_title.addWidget(rviz_name)
        rviz_title.addStretch()
        self._close_rviz_button = QPushButton("Close RViz")
        self._close_rviz_button.setProperty("role", "stop")
        self._close_rviz_button.clicked.connect(self._close_rviz)
        self._decorate_button(
            self._close_rviz_button, ("window-close",), QStyle.SP_DialogCloseButton
        )
        rviz_title.addWidget(self._close_rviz_button)
        rviz_layout.addLayout(rviz_title)
        self._rviz_status_dot = QLabel("●")
        self._rviz_status_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._rviz_status_text = QLabel("RViz stopped")
        self._rviz_status_text.setStyleSheet("font-weight: 600;")
        rviz_status = QHBoxLayout()
        rviz_status.addWidget(self._rviz_status_dot)
        rviz_status.addWidget(self._rviz_status_text)
        rviz_status.addStretch()
        self._launch_rviz_with_bringup = QCheckBox("Auto-launch with Bringup")
        self._launch_rviz_with_bringup.setChecked(True)
        rviz_status.addWidget(self._launch_rviz_with_bringup)
        rviz_layout.addLayout(rviz_status)
        tools_layout.addWidget(rviz_panel)

        mapping_panel, mapping_layout = self._subpanel()
        mapping_header = QHBoxLayout()
        mapping_title = QLabel("SLAM Mapping")
        mapping_title.setStyleSheet("font-weight: 700;")
        mapping_header.addWidget(mapping_title)
        alternate = QLabel("alternate mode")
        alternate.setProperty("muted", True)
        mapping_header.addWidget(alternate)
        mapping_header.addStretch()
        self._mapping_status_dot = QLabel("●")
        self._mapping_status_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._mapping_status_text = QLabel("Mapping status unknown")
        self._mapping_status_text.setStyleSheet("font-weight: 600;")
        mapping_header.addWidget(self._mapping_status_dot)
        mapping_header.addWidget(self._mapping_status_text)
        mapping_layout.addLayout(mapping_header)
        map_name_row = QHBoxLayout()
        map_name_label = QLabel("New map name")
        map_name_label.setProperty("muted", True)
        map_name_row.addWidget(map_name_label)
        self._map_name = QLineEdit()
        self._map_name.setPlaceholderText("New map name")
        self._map_name.setToolTip(
            "Start with a letter; use letters, numbers, underscores, or hyphens."
        )
        self._map_name.textChanged.connect(self._update_mapping_controls)
        map_name_row.addWidget(self._map_name, stretch=1)
        mapping_layout.addLayout(map_name_row)
        mapping_actions = QHBoxLayout()
        mapping_actions.addStretch()
        self._start_mapping_button = QPushButton("Start new map")
        self._start_mapping_button.setProperty("role", "start")
        self._start_mapping_button.clicked.connect(self._start_mapping)
        mapping_actions.addWidget(self._start_mapping_button)
        self._save_map_button = QPushButton("Save map")
        self._save_map_button.setProperty("role", "action")
        self._save_map_button.clicked.connect(self._save_map)
        mapping_actions.addWidget(self._save_map_button)
        self._stop_mapping_button = QPushButton("Stop mapping")
        self._stop_mapping_button.setProperty("role", "stop")
        self._stop_mapping_button.clicked.connect(self._stop_mapping)
        mapping_actions.addWidget(self._stop_mapping_button)
        mapping_layout.addLayout(mapping_actions)
        self._decorate_button(
            self._start_mapping_button,
            ("document-new",),
            QStyle.SP_FileIcon,
        )
        self._decorate_button(
            self._save_map_button,
            ("document-save",),
            QStyle.SP_DialogSaveButton,
        )
        self._decorate_button(
            self._stop_mapping_button,
            ("process-stop",),
            QStyle.SP_MediaStop,
        )
        tools_layout.addWidget(mapping_panel)

        insight_row = QHBoxLayout()
        health_panel, health_layout = self._subpanel()
        health_name = QLabel("System Health")
        health_name.setStyleSheet("font-weight: 700;")
        health_layout.addWidget(health_name)
        self._health_status_dot = QLabel("●")
        self._health_status_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._health_status_text = QLabel("System health: waiting for probe")
        self._health_status_text.setWordWrap(True)
        self._health_status_text.setToolTip(
            "Summarizes sessions, ROS nodes, topic publishers, freshness, "
            "lifecycle state, actions, and transforms."
        )
        health_layout.addWidget(
            self._status_widget(self._health_status_dot, self._health_status_text)
        )
        insight_row.addWidget(health_panel, stretch=1)
        tf_panel, tf_layout = self._subpanel()
        tf_name = QLabel("Global TF")
        tf_name.setStyleSheet("font-weight: 700;")
        tf_layout.addWidget(tf_name)
        self._tf_status_dot = QLabel("●")
        self._tf_status_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._tf_status_text = QLabel("Global TF: map → base_link unavailable")
        self._tf_status_text.setWordWrap(True)
        self._tf_status_text.setToolTip(
            "End-to-end transform required by RViz and navigation."
        )
        tf_layout.addWidget(
            self._status_widget(self._tf_status_dot, self._tf_status_text)
        )
        insight_row.addWidget(tf_panel, stretch=1)
        tools_layout.addLayout(insight_row)
        operations.addWidget(tools_frame)
        operations.setStretchFactor(0, 7)
        operations.setStretchFactor(1, 5)
        operations.setSizes([820, 590])
        self._operations_splitter = operations

        log_frame = QWidget()
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(5)
        log_header = QHBoxLayout()
        activity_label = QLabel("ACTIVITY & DIAGNOSTICS")
        activity_label.setProperty("heading", True)
        log_header.addWidget(activity_label)
        log_header.addStretch()
        self._follow_bringup_log = QCheckBox("Auto-scroll logs")
        self._follow_bringup_log.setChecked(True)
        self._follow_bringup_log.setToolTip(
            "Keep live logs scrolled to their newest output."
        )
        log_header.addWidget(self._follow_bringup_log)
        log_layout.addLayout(log_header)

        self._log_tabs = QTabWidget()
        self._health_table = QTableWidget(0, 4)
        self._health_table.setHorizontalHeaderLabels([
            "Subsystem", "Check", "State", "Details"
        ])
        self._health_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._health_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._health_table.setAlternatingRowColors(True)
        self._health_table.verticalHeader().setVisible(False)
        health_header = self._health_table.horizontalHeader()
        health_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        health_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        health_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        health_header.setSectionResizeMode(3, QHeaderView.Stretch)
        self._log_tabs.addTab(self._health_table, "System Health")

        parameter_widget = QWidget()
        self._parameter_widget = parameter_widget
        parameter_layout = QVBoxLayout(parameter_widget)
        parameter_layout.setContentsMargins(12, 12, 12, 12)
        parameter_layout.setSpacing(9)
        parameter_intro = QLabel(
            "Tune important YAML values with their original section and "
            "documentation visible. Star parameters to keep a focused list."
        )
        parameter_intro.setProperty("muted", True)
        parameter_intro.setWordWrap(True)
        parameter_layout.addWidget(parameter_intro)
        parameter_controls = QHBoxLayout()
        parameter_controls.addWidget(QLabel("YAML file"))
        self._parameter_file_selector = QComboBox()
        self._parameter_file_selector.setMinimumWidth(250)
        self._parameter_file_selector.setToolTip(
            "Navigation configuration files from the Jetson source tree."
        )
        self._parameter_file_selector.currentTextChanged.connect(
            self._parameter_file_selected
        )
        parameter_controls.addWidget(self._parameter_file_selector)
        self._refresh_parameter_files_button = QPushButton("Refresh files")
        self._refresh_parameter_files_button.clicked.connect(
            self._refresh_parameter_files
        )
        parameter_controls.addWidget(self._refresh_parameter_files_button)
        self._favorite_parameters_only = QCheckBox("Starred only")
        self._favorite_parameters_only.setToolTip(
            "Show starred parameters in original YAML order with section headers."
        )
        self._favorite_parameters_only.toggled.connect(
            self._rebuild_parameter_tree
        )
        parameter_controls.addWidget(self._favorite_parameters_only)
        self._parameter_focus_button = QPushButton("Focus tuning")
        self._parameter_focus_button.setProperty("role", "quiet")
        self._parameter_focus_button.setCheckable(True)
        self._parameter_focus_button.setToolTip(
            "Temporarily hide the operations dashboard and use the full "
            "workspace for the parameter table."
        )
        self._parameter_focus_button.toggled.connect(
            self._toggle_parameter_focus
        )
        parameter_controls.addWidget(self._parameter_focus_button)
        parameter_controls.addStretch()
        self._save_parameter_yaml_button = QPushButton("Save YAML")
        self._save_parameter_yaml_button.setProperty("role", "action")
        self._save_parameter_yaml_button.setToolTip(
            "Atomically save all staged values while preserving comments."
        )
        self._save_parameter_yaml_button.clicked.connect(
            self._save_parameter_yaml
        )
        parameter_controls.addWidget(self._save_parameter_yaml_button)
        parameter_layout.addLayout(parameter_controls)
        self._parameter_status = QLabel(
            "Connect to the Jetson, then select or refresh a YAML file."
        )
        self._parameter_status.setWordWrap(True)
        self._parameter_status.setStyleSheet("font-weight: 600;")
        parameter_layout.addWidget(self._parameter_status)
        self._parameter_tree = QTreeWidget()
        self._parameter_tree.setObjectName("ParameterTree")
        self._parameter_tree.setColumnCount(5)
        self._parameter_tree.setHeaderLabels([
            "★", "Parameter", "Staged value", "YAML comment", "Apply"
        ])
        self._parameter_tree.setAlternatingRowColors(True)
        self._parameter_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._parameter_tree.setWordWrap(True)
        self._parameter_tree.setUniformRowHeights(False)
        self._parameter_tree.setIndentation(16)
        self._parameter_tree.itemChanged.connect(
            self._parameter_tree_item_changed
        )
        parameter_header = self._parameter_tree.header()
        parameter_header.setMinimumHeight(36)
        parameter_header.setMinimumSectionSize(44)
        parameter_header.setSectionResizeMode(0, QHeaderView.Fixed)
        parameter_header.resizeSection(0, 48)
        parameter_header.setSectionResizeMode(1, QHeaderView.Interactive)
        parameter_header.resizeSection(1, 260)
        parameter_header.setSectionResizeMode(2, QHeaderView.Interactive)
        parameter_header.resizeSection(2, 220)
        parameter_header.setSectionResizeMode(3, QHeaderView.Stretch)
        parameter_header.setSectionResizeMode(4, QHeaderView.Fixed)
        parameter_header.resizeSection(4, 155)
        parameter_layout.addWidget(self._parameter_tree, stretch=1)
        self._log_tabs.addTab(parameter_widget, "Parameter Tuning")

        self._connection_log = self._new_log_view(
            "Connect to the Jetson to inspect SSH activity.", 500
        )
        self._log_tabs.addTab(self._connection_log, "Connection")
        self._diagnostics_log = self._new_log_view(
            "Connect through Wi-Fi or Ethernet, then select Diagnose network.",
            1000,
        )
        self._log_tabs.addTab(self._diagnostics_log, "Network Diagnosis")
        self._bringup_log = self._new_log_view(
            "Connect to inspect the amr_bringup tmux session.", 2000
        )
        self._log_tabs.addTab(self._bringup_log, "Bringup Log")
        self._localization_log = self._new_log_view(
            "Start localization to view AMCL and map_server output.", 2000
        )
        self._log_tabs.addTab(self._localization_log, "Localization Log")
        self._navigation_log = self._new_log_view(
            "Start Nav2 after localization and Global TF are ready.", 2500
        )
        self._log_tabs.addTab(self._navigation_log, "Nav2 Log")
        self._mapping_log = self._new_log_view(
            "Start a new map to view Slam Toolbox output.", 2000
        )
        self._log_tabs.addTab(self._mapping_log, "Mapping Log")
        self._rviz_log = self._new_log_view("", 1000)
        self._log_tabs.addTab(self._rviz_log, "RViz Log")
        self._log_tabs.currentChanged.connect(self._log_tab_changed)
        log_layout.addWidget(self._log_tabs, stretch=1)

        hint = QLabel(
            "Nav2 requires active localization and Global TF. Mapping is "
            "mutually exclusive with localization/Nav2. Closing this GUI "
            "leaves remote tmux sessions running."
        )
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        log_layout.addWidget(hint)

        self._main_splitter = QSplitter(Qt.Vertical)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.addWidget(operations)
        self._main_splitter.addWidget(log_frame)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([390, 440])
        layout.addWidget(self._main_splitter, stretch=1)

        self._log_views = [
            self._connection_log,
            self._diagnostics_log,
            self._bringup_log,
            self._localization_log,
            self._navigation_log,
            self._mapping_log,
            self._rviz_log,
        ]
        self._appearance_shortcuts = []
        for sequence, change in (
            (QKeySequence("Ctrl++"), 1),
            (QKeySequence("Ctrl+="), 1),
            (QKeySequence("Ctrl+Shift+="), 1),
            (QKeySequence("Ctrl+-"), -1),
        ):
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(
                lambda step=change: self._change_log_font_size(step)
            )
            self._appearance_shortcuts.append(shortcut)
        reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        reset_shortcut.setContext(Qt.WindowShortcut)
        reset_shortcut.activated.connect(self._reset_log_font_size)
        self._appearance_shortcuts.append(reset_shortcut)

        self.setCentralWidget(central)
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()
        self._update_navigation_controls()
        self._update_rviz_controls()
        self._update_connection_controls()

    @staticmethod
    def _new_log_view(initial_text: str, maximum_blocks: int) -> QPlainTextEdit:
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.NoWrap)
        view.document().setMaximumBlockCount(maximum_blocks)
        view.setPlainText(initial_text)
        return view

    def _toggle_parameter_focus(self, focused: bool) -> None:
        self._operations_splitter.setVisible(not focused)
        self._parameter_focus_button.setText(
            "Show dashboard" if focused else "Focus tuning"
        )

    def _log_tab_changed(self, index: int) -> None:
        parameter_index = self._log_tabs.indexOf(self._parameter_widget)
        if index != parameter_index and self._parameter_focus_button.isChecked():
            self._parameter_focus_button.setChecked(False)

    def _build_legacy_ui(self) -> None:
        """Retained temporarily as a reference for pre-Mission-Control UI."""
        central = QWidget(self)
        layout = QVBoxLayout(central)

        title_row = QHBoxLayout()
        title = QLabel("Autonomous Mobile Robot")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._theme_button = QPushButton()
        self._theme_button.setProperty("role", "action")
        self._theme_button.setToolTip(
            "Switch between the dark and light application themes."
        )
        self._theme_button.clicked.connect(self._toggle_theme)
        title_row.addWidget(self._theme_button)
        layout.addLayout(title_row)

        stage = QLabel(
            "Stage 5: operate bringup, localization, Nav2, or SLAM mapping; "
            "monitor the global TF and NavigateToPose action; save new maps; "
            "and keep one unified RViz view open locally."
        )
        stage.setWordWrap(True)
        layout.addWidget(stage)

        connection_section = CollapsibleSection("Jetson connection")
        connection_layout = QFormLayout()

        self._host = QLineEdit()
        self._host.setPlaceholderText("Jetson IP address or resolvable hostname")
        connection_layout.addRow("Wi-Fi host", self._host)

        self._username = QLineEdit()
        connection_layout.addRow("Username", self._username)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        connection_layout.addRow("SSH port", self._port)

        self._identity_file = QLineEdit()
        self._identity_file.setPlaceholderText(
            "Optional, e.g. ~/.ssh/id_ed25519 (uses SSH defaults when empty)"
        )
        connection_layout.addRow("Private key", self._identity_file)
        connection_section.set_content_layout(connection_layout)
        layout.addWidget(connection_section)

        fallback_section = CollapsibleSection("Fallback Ethernet SSH")
        fallback_layout = QFormLayout()
        self._ethernet_host = QLineEdit()
        self._ethernet_host.setPlaceholderText(
            "SSH config alias, e.g. nano_ethernet"
        )
        fallback_layout.addRow("Ethernet alias", self._ethernet_host)
        self._automatic_fallback = QCheckBox(
            "Automatically use Ethernet when Wi-Fi SSH fails"
        )
        self._automatic_fallback.setChecked(True)
        self._automatic_fallback.setToolTip(
            "Wi-Fi remains preferred. All robot commands switch to the SSH "
            "config alias only while the Wi-Fi route is unavailable."
        )
        fallback_layout.addRow("", self._automatic_fallback)
        fallback_section.set_content_layout(fallback_layout)
        layout.addWidget(fallback_section)

        robot_section = CollapsibleSection("Remote robot environment")
        robot_layout = QFormLayout()

        self._remote_workspace = QLineEdit()
        self._remote_workspace.setPlaceholderText("Absolute Jetson ros2_ws path")
        robot_layout.addRow("Workspace", self._remote_workspace)

        self._domain_id = QSpinBox()
        self._domain_id.setRange(0, 232)
        robot_layout.addRow("ROS domain ID", self._domain_id)

        self._rmw_implementation = QLineEdit()
        robot_layout.addRow("RMW implementation", self._rmw_implementation)
        robot_section.set_content_layout(robot_layout)
        layout.addWidget(robot_section)

        local_section = CollapsibleSection("Local RViz environment")
        local_layout = QFormLayout()
        self._local_workspace = QLineEdit()
        self._local_workspace.setPlaceholderText(
            "Development-machine ros2_ws path"
        )
        local_layout.addRow("Local workspace", self._local_workspace)
        local_section.set_content_layout(local_layout)
        layout.addWidget(local_section)

        status_row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("font-size: 22px; color: #777;")
        self._status_text = QLabel("Not checked")
        self._status_text.setStyleSheet("font-weight: 600;")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_text)
        status_row.addStretch()

        self._auto_monitor = QCheckBox("Check every 10 seconds")
        self._auto_monitor.setChecked(True)
        status_row.addWidget(self._auto_monitor)

        self._test_button = QPushButton("Test SSH routes")
        self._test_button.setProperty("role", "action")
        self._test_button.clicked.connect(self._manual_connection_test)
        status_row.addWidget(self._test_button)
        layout.addLayout(status_row)

        route_row = QHBoxLayout()
        self._wifi_route_dot = QLabel("●")
        self._wifi_route_dot.setStyleSheet("font-size: 18px; color: #777;")
        self._wifi_route_text = QLabel("Wi-Fi SSH unchecked")
        route_row.addWidget(self._wifi_route_dot)
        route_row.addWidget(self._wifi_route_text)

        self._ethernet_route_dot = QLabel("●")
        self._ethernet_route_dot.setStyleSheet(
            "font-size: 18px; color: #777;"
        )
        self._ethernet_route_text = QLabel("Ethernet SSH unchecked")
        route_row.addWidget(self._ethernet_route_dot)
        route_row.addWidget(self._ethernet_route_text)
        route_row.addStretch()

        self._diagnose_button = QPushButton("Diagnose network")
        self._diagnose_button.setProperty("role", "action")
        self._diagnose_button.setToolTip(
            "Run read-only route, peer, gateway, internet-IP, and DNS checks "
            "on both the development machine and Jetson."
        )
        self._diagnose_button.clicked.connect(self._start_network_diagnostics)
        route_row.addWidget(self._diagnose_button)

        self._shutdown_jetson_button = QPushButton("Shutdown Jetson")
        self._shutdown_jetson_button.setProperty("role", "stop")
        self._shutdown_jetson_button.setToolTip(
            "Safely power off the Jetson over the currently active SSH route."
        )
        self._shutdown_jetson_button.clicked.connect(self._shutdown_jetson)
        route_row.addWidget(self._shutdown_jetson_button)
        layout.addLayout(route_row)

        bringup_row = QHBoxLayout()
        self._bringup_status_dot = QLabel("●")
        self._bringup_status_dot.setStyleSheet("font-size: 22px; color: #777;")
        self._bringup_status_text = QLabel("Bringup status unknown")
        self._bringup_status_text.setStyleSheet("font-weight: 600;")
        bringup_row.addWidget(self._bringup_status_dot)
        bringup_row.addWidget(self._bringup_status_text)
        bringup_row.addStretch()

        self._show_start_confirmation = QCheckBox("Confirm start")
        self._show_start_confirmation.setChecked(True)
        self._show_start_confirmation.setToolTip(
            "Uncheck to suppress the physical-hardware start warning."
        )
        bringup_row.addWidget(self._show_start_confirmation)

        self._launch_rviz_with_bringup = QCheckBox("Auto-launch RViz")
        self._launch_rviz_with_bringup.setChecked(True)
        bringup_row.addWidget(self._launch_rviz_with_bringup)

        self._start_bringup_button = QPushButton("Start robot bringup")
        self._start_bringup_button.setProperty("role", "start")
        self._start_bringup_button.clicked.connect(self._start_robot_bringup)
        bringup_row.addWidget(self._start_bringup_button)

        self._stop_bringup_button = QPushButton("Stop bringup")
        self._stop_bringup_button.setProperty("role", "stop")
        self._stop_bringup_button.clicked.connect(self._stop_robot_bringup)
        bringup_row.addWidget(self._stop_bringup_button)
        layout.addLayout(bringup_row)

        rviz_row = QHBoxLayout()
        self._rviz_status_dot = QLabel("●")
        self._rviz_status_dot.setStyleSheet("font-size: 22px; color: #777;")
        self._rviz_status_text = QLabel("RViz stopped")
        self._rviz_status_text.setStyleSheet("font-weight: 600;")
        rviz_row.addWidget(self._rviz_status_dot)
        rviz_row.addWidget(self._rviz_status_text)
        rviz_row.addStretch()

        self._launch_rviz_button = QPushButton("Launch RViz")
        self._launch_rviz_button.setProperty("role", "action")
        self._launch_rviz_button.clicked.connect(self._launch_rviz)
        rviz_row.addWidget(self._launch_rviz_button)

        self._open_vscode_button = QPushButton("Open VS Code")
        self._open_vscode_button.setProperty("role", "action")
        self._open_vscode_button.setToolTip(
            "Open this repository on the Jetson through VS Code Remote-SSH. "
            "The repository setting focuses the Codex sidebar on startup."
        )
        self._open_vscode_button.clicked.connect(self._open_vscode)
        rviz_row.addWidget(self._open_vscode_button)

        self._close_rviz_button = QPushButton("Close RViz")
        self._close_rviz_button.setProperty("role", "stop")
        self._close_rviz_button.clicked.connect(self._close_rviz)
        rviz_row.addWidget(self._close_rviz_button)
        layout.addLayout(rviz_row)

        localization_row = QHBoxLayout()
        self._localization_status_dot = QLabel("●")
        self._localization_status_dot.setStyleSheet(
            "font-size: 22px; color: #777;"
        )
        self._localization_status_text = QLabel("Localization status unknown")
        self._localization_status_text.setStyleSheet("font-weight: 600;")
        localization_row.addWidget(self._localization_status_dot)
        localization_row.addWidget(self._localization_status_text)

        self._map_selector = QComboBox()
        self._map_selector.setMinimumWidth(190)
        localization_row.addWidget(QLabel("Map"))
        localization_row.addWidget(self._map_selector)

        self._refresh_maps_button = QPushButton("Refresh maps")
        self._refresh_maps_button.clicked.connect(self._refresh_maps)
        localization_row.addWidget(self._refresh_maps_button)

        self._start_localization_button = QPushButton("Start localization")
        self._start_localization_button.setProperty("role", "start")
        self._start_localization_button.clicked.connect(self._start_localization)
        localization_row.addWidget(self._start_localization_button)

        self._stop_localization_button = QPushButton("Stop localization")
        self._stop_localization_button.setProperty("role", "stop")
        self._stop_localization_button.clicked.connect(self._stop_localization)
        localization_row.addWidget(self._stop_localization_button)
        layout.addLayout(localization_row)

        navigation_row = QHBoxLayout()
        self._navigation_status_dot = QLabel("●")
        self._navigation_status_dot.setStyleSheet(
            "font-size: 22px; color: #777;"
        )
        self._navigation_status_text = QLabel("Nav2 status unknown")
        self._navigation_status_text.setStyleSheet("font-weight: 600;")
        navigation_row.addWidget(self._navigation_status_dot)
        navigation_row.addWidget(self._navigation_status_text)

        self._nav_action_status_dot = QLabel("●")
        self._nav_action_status_dot.setStyleSheet(
            "font-size: 22px; color: #777;"
        )
        self._nav_action_status_text = QLabel("NavigateToPose unavailable")
        self._nav_action_status_text.setToolTip(
            "Turns green only when bt_navigator's NavigateToPose action server "
            "is discoverable and ready to accept goals."
        )
        navigation_row.addWidget(self._nav_action_status_dot)
        navigation_row.addWidget(self._nav_action_status_text)
        navigation_row.addStretch()

        self._start_navigation_button = QPushButton("Start Nav2")
        self._start_navigation_button.setProperty("role", "start")
        self._start_navigation_button.clicked.connect(self._start_navigation)
        navigation_row.addWidget(self._start_navigation_button)

        self._stop_navigation_button = QPushButton("Stop Nav2")
        self._stop_navigation_button.setProperty("role", "stop")
        self._stop_navigation_button.clicked.connect(self._stop_navigation)
        navigation_row.addWidget(self._stop_navigation_button)
        layout.addLayout(navigation_row)

        mapping_row = QHBoxLayout()
        self._mapping_status_dot = QLabel("●")
        self._mapping_status_dot.setStyleSheet("font-size: 22px; color: #777;")
        self._mapping_status_text = QLabel("Mapping status unknown")
        self._mapping_status_text.setStyleSheet("font-weight: 600;")
        mapping_row.addWidget(self._mapping_status_dot)
        mapping_row.addWidget(self._mapping_status_text)
        mapping_row.addStretch()

        self._start_mapping_button = QPushButton("Start new map")
        self._start_mapping_button.setProperty("role", "start")
        self._start_mapping_button.clicked.connect(self._start_mapping)
        mapping_row.addWidget(self._start_mapping_button)

        self._map_name = QLineEdit()
        self._map_name.setPlaceholderText("New map name")
        self._map_name.setMaximumWidth(190)
        self._map_name.setToolTip(
            "Start with a letter; use letters, numbers, underscores, or hyphens."
        )
        self._map_name.textChanged.connect(self._update_mapping_controls)
        mapping_row.addWidget(self._map_name)

        self._save_map_button = QPushButton("Save map")
        self._save_map_button.setProperty("role", "action")
        self._save_map_button.clicked.connect(self._save_map)
        mapping_row.addWidget(self._save_map_button)

        self._stop_mapping_button = QPushButton("Stop mapping")
        self._stop_mapping_button.setProperty("role", "stop")
        self._stop_mapping_button.clicked.connect(self._stop_mapping)
        mapping_row.addWidget(self._stop_mapping_button)
        layout.addLayout(mapping_row)

        health_row = QHBoxLayout()
        self._health_status_dot = QLabel("●")
        self._health_status_dot.setStyleSheet("font-size: 22px; color: #777;")
        self._health_status_text = QLabel("System health: waiting for probe")
        self._health_status_text.setStyleSheet("font-weight: 600;")
        self._health_status_text.setToolTip(
            "Summarizes expected launch sessions, ROS nodes, topic publishers, "
            "message freshness, lifecycle state, actions, and transforms."
        )
        health_row.addWidget(self._health_status_dot)
        health_row.addWidget(self._health_status_text)
        health_row.addStretch()

        self._show_health_button = QPushButton("Show system health")
        self._show_health_button.setProperty("role", "action")
        self._show_health_button.clicked.connect(self._show_system_health)
        health_row.addWidget(self._show_health_button)
        layout.addLayout(health_row)

        tf_row = QHBoxLayout()
        self._tf_status_dot = QLabel("●")
        self._tf_status_dot.setStyleSheet("font-size: 22px; color: #777;")
        self._tf_status_text = QLabel("Global TF: map → base_link unavailable")
        self._tf_status_text.setStyleSheet("font-weight: 600;")
        self._tf_status_text.setToolTip(
            "End-to-end transform required by RViz and navigation. It verifies "
            "map→odom from AMCL/Slam Toolbox and odom→base_link from the driver."
        )
        tf_row.addWidget(self._tf_status_dot)
        tf_row.addWidget(self._tf_status_text)
        tf_row.addStretch()

        self._follow_bringup_log = QCheckBox("Auto-scroll logs")
        self._follow_bringup_log.setChecked(True)
        self._follow_bringup_log.setToolTip(
            "Keep live Bringup, Localization, Nav2, and Mapping logs scrolled "
            "to their newest output."
        )
        tf_row.addWidget(self._follow_bringup_log)
        layout.addLayout(tf_row)

        self._log_tabs = QTabWidget()

        self._health_table = QTableWidget(0, 4)
        self._health_table.setHorizontalHeaderLabels([
            "Subsystem", "Check", "State", "Details"
        ])
        self._health_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._health_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._health_table.setAlternatingRowColors(True)
        self._health_table.verticalHeader().setVisible(False)
        health_header = self._health_table.horizontalHeader()
        health_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        health_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        health_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        health_header.setSectionResizeMode(3, QHeaderView.Stretch)
        self._log_tabs.addTab(self._health_table, "System Health")

        parameter_widget = QWidget()
        parameter_layout = QVBoxLayout(parameter_widget)
        parameter_controls = QHBoxLayout()
        parameter_controls.addWidget(QLabel("YAML file"))
        self._parameter_file_selector = QComboBox()
        self._parameter_file_selector.setMinimumWidth(220)
        self._parameter_file_selector.setToolTip(
            "Navigation configuration files from the Jetson source tree."
        )
        self._parameter_file_selector.currentTextChanged.connect(
            self._parameter_file_selected
        )
        parameter_controls.addWidget(self._parameter_file_selector)

        self._refresh_parameter_files_button = QPushButton("Refresh files")
        self._refresh_parameter_files_button.clicked.connect(
            self._refresh_parameter_files
        )
        parameter_controls.addWidget(self._refresh_parameter_files_button)

        self._favorite_parameters_only = QCheckBox("Starred only")
        self._favorite_parameters_only.setToolTip(
            "Keep starred parameters in their original YAML order and show "
            "the section header for each group."
        )
        self._favorite_parameters_only.toggled.connect(
            self._rebuild_parameter_tree
        )
        parameter_controls.addWidget(self._favorite_parameters_only)
        parameter_controls.addStretch()

        self._save_parameter_yaml_button = QPushButton("Save YAML")
        self._save_parameter_yaml_button.setProperty("role", "action")
        self._save_parameter_yaml_button.setToolTip(
            "Atomically save all staged values to the selected Jetson YAML "
            "file while preserving its comments."
        )
        self._save_parameter_yaml_button.clicked.connect(
            self._save_parameter_yaml
        )
        parameter_controls.addWidget(self._save_parameter_yaml_button)
        parameter_layout.addLayout(parameter_controls)

        self._parameter_status = QLabel(
            "Connect to the Jetson, then select or refresh a YAML file."
        )
        self._parameter_status.setWordWrap(True)
        parameter_layout.addWidget(self._parameter_status)

        self._parameter_tree = QTreeWidget()
        self._parameter_tree.setColumnCount(5)
        self._parameter_tree.setHeaderLabels([
            "★", "Parameter", "Staged value", "YAML comment", "Apply"
        ])
        self._parameter_tree.setAlternatingRowColors(True)
        self._parameter_tree.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self._parameter_tree.itemChanged.connect(
            self._parameter_tree_item_changed
        )
        parameter_header = self._parameter_tree.header()
        parameter_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        parameter_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        parameter_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        parameter_header.setSectionResizeMode(3, QHeaderView.Stretch)
        parameter_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        parameter_layout.addWidget(self._parameter_tree, stretch=1)
        self._log_tabs.addTab(parameter_widget, "Parameter Tuning")

        self._connection_log = QPlainTextEdit()
        self._connection_log.setReadOnly(True)
        self._connection_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._connection_log.document().setMaximumBlockCount(500)
        self._log_tabs.addTab(self._connection_log, "Connection")

        self._diagnostics_log = QPlainTextEdit()
        self._diagnostics_log.setReadOnly(True)
        self._diagnostics_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._diagnostics_log.document().setMaximumBlockCount(1000)
        self._diagnostics_log.setPlainText(
            "Connect through Wi-Fi or fallback Ethernet, then select "
            "Diagnose network."
        )
        self._log_tabs.addTab(self._diagnostics_log, "Network Diagnosis")

        self._bringup_log = QPlainTextEdit()
        self._bringup_log.setReadOnly(True)
        self._bringup_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._bringup_log.document().setMaximumBlockCount(2000)
        self._bringup_log.setPlainText(
            "Connect to the Jetson to inspect the amr_bringup tmux session."
        )
        self._log_tabs.addTab(self._bringup_log, "Bringup Log")

        self._localization_log = QPlainTextEdit()
        self._localization_log.setReadOnly(True)
        self._localization_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._localization_log.document().setMaximumBlockCount(2000)
        self._localization_log.setPlainText(
            "Start localization to view AMCL and map_server output."
        )
        self._log_tabs.addTab(self._localization_log, "Localization Log")

        self._navigation_log = QPlainTextEdit()
        self._navigation_log.setReadOnly(True)
        self._navigation_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._navigation_log.document().setMaximumBlockCount(2500)
        self._navigation_log.setPlainText(
            "Start Nav2 after localization and Global TF are ready."
        )
        self._log_tabs.addTab(self._navigation_log, "Nav2 Log")

        self._mapping_log = QPlainTextEdit()
        self._mapping_log.setReadOnly(True)
        self._mapping_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._mapping_log.document().setMaximumBlockCount(2000)
        self._mapping_log.setPlainText(
            "Start a new map to view Slam Toolbox output."
        )
        self._log_tabs.addTab(self._mapping_log, "Mapping Log")

        self._rviz_log = QPlainTextEdit()
        self._rviz_log.setReadOnly(True)
        self._rviz_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._rviz_log.document().setMaximumBlockCount(1000)
        self._log_tabs.addTab(self._rviz_log, "RViz Log")
        layout.addWidget(self._log_tabs, stretch=1)

        self._log_views = [
            self._connection_log,
            self._diagnostics_log,
            self._bringup_log,
            self._localization_log,
            self._navigation_log,
            self._mapping_log,
            self._rviz_log,
        ]
        self._appearance_shortcuts = []
        for sequence, change in (
            (QKeySequence("Ctrl++"), 1),
            (QKeySequence("Ctrl+="), 1),
            (QKeySequence("Ctrl+Shift+="), 1),
            (QKeySequence("Ctrl+-"), -1),
        ):
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(
                lambda step=change: self._change_log_font_size(step)
            )
            self._appearance_shortcuts.append(shortcut)

        reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        reset_shortcut.setContext(Qt.WindowShortcut)
        reset_shortcut.activated.connect(self._reset_log_font_size)
        self._appearance_shortcuts.append(reset_shortcut)

        hint = QLabel(
            "Nav2 requires active localization and Global TF. Mapping is "
            "mutually exclusive with localization/Nav2. Closing this GUI "
            "leaves remote tmux sessions running."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        self.setCentralWidget(central)
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()
        self._update_navigation_controls()
        self._update_rviz_controls()
        self._update_connection_controls()

    def _load_settings(self) -> None:
        wifi_host = self._settings.value("ssh/host", "nano_wifi", type=str)
        if wifi_host in {"10.42.0.129", "nano_ethernet", "nano_ethernt"}:
            wifi_host = "nano_wifi"
        self._host.setText(wifi_host)
        self._username.setText(
            self._settings.value("ssh/username", "jetson", type=str)
        )
        self._port.setValue(self._settings.value("ssh/port", 22, type=int))
        self._identity_file.setText(
            self._settings.value("ssh/identity_file", "", type=str)
        )
        self._ethernet_host.setText(
            self._settings.value(
                "ssh/ethernet_host", "nano_ethernet", type=str
            )
        )
        self._automatic_fallback.setChecked(
            self._settings.value(
                "ssh/automatic_ethernet_fallback", True, type=bool
            )
        )
        self._remote_workspace.setText(
            self._settings.value(
                "robot/workspace", DEFAULT_REMOTE_WORKSPACE, type=str
            )
        )
        self._domain_id.setValue(
            self._settings.value("robot/domain_id", 0, type=int)
        )
        self._rmw_implementation.setText(
            self._settings.value(
                "robot/rmw_implementation", "rmw_cyclonedds_cpp", type=str
            )
        )
        self._local_workspace.setText(
            self._settings.value(
                "local/workspace", DEFAULT_LOCAL_WORKSPACE, type=str
            )
        )
        self._show_start_confirmation.setChecked(
            self._settings.value(
                "options/show_start_confirmation", True, type=bool
            )
        )
        self._launch_rviz_with_bringup.setChecked(
            self._settings.value(
                "options/launch_rviz_with_bringup", True, type=bool
            )
        )
        self._saved_map_name = self._settings.value(
            "localization/map", "LakecityFlat4AMap.yaml", type=str
        )
        self._map_name.setText(
            self._settings.value("mapping/map_name", "", type=str)
        )
        self._auto_monitor.setChecked(
            self._settings.value("ssh/auto_monitor", True, type=bool)
        )
        self._saved_parameter_filename = self._settings.value(
            "parameters/selected_file",
            "nav2_params_real.yaml",
            type=str,
        )
        favorite_json = self._settings.value(
            "parameters/favorites", "[]", type=str
        )
        try:
            favorites = json.loads(favorite_json)
            self._parameter_favorites = {
                str(value) for value in favorites if isinstance(value, str)
            }
        except (TypeError, ValueError):
            self._parameter_favorites = set()

    def _toggle_theme(self) -> None:
        self._dark_theme = not self._dark_theme
        self._apply_theme()
        self._settings.setValue("appearance/dark_theme", self._dark_theme)
        self._settings.sync()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(
                DARK_STYLESHEET if self._dark_theme else LIGHT_STYLESHEET
            )
        self._theme_button.setText(
            "Light theme" if self._dark_theme else "Dark theme"
        )
        self._decorate_button(
            self._theme_button,
            ("weather-clear", "display-brightness")
            if self._dark_theme
            else ("weather-clear-night", "night-light"),
            QStyle.SP_TitleBarShadeButton,
        )

    def _change_log_font_size(self, change: int) -> None:
        new_size = max(
            MIN_LOG_FONT_SIZE,
            min(MAX_LOG_FONT_SIZE, self._log_font_size + change),
        )
        if new_size == self._log_font_size:
            return
        self._log_font_size = new_size
        self._apply_log_font_size()
        self._settings.setValue(
            "appearance/log_font_size", self._log_font_size
        )
        selected_parameter_file = self._parameter_file_selector.currentText()
        if selected_parameter_file:
            self._settings.setValue(
                "parameters/selected_file", selected_parameter_file
            )
        self._settings.setValue(
            "parameters/favorites",
            json.dumps(sorted(self._parameter_favorites)),
        )
        self._settings.sync()

    def _reset_log_font_size(self) -> None:
        self._log_font_size = DEFAULT_LOG_FONT_SIZE
        self._apply_log_font_size()
        self._settings.setValue(
            "appearance/log_font_size", self._log_font_size
        )
        self._settings.sync()

    def _apply_log_font_size(self) -> None:
        for log_view in self._log_views:
            font = log_view.font()
            font.setPointSize(self._log_font_size)
            log_view.setFont(font)
            log_view.setToolTip(
                "Log text: {} pt (Ctrl++ / Ctrl+-; Ctrl+0 resets)".format(
                    self._log_font_size
                )
            )

    def _save_settings(self) -> None:
        self._settings.setValue("ssh/host", self._host.text().strip())
        self._settings.setValue("ssh/username", self._username.text().strip())
        self._settings.setValue("ssh/port", self._port.value())
        self._settings.setValue(
            "ssh/identity_file", self._identity_file.text().strip()
        )
        self._settings.setValue(
            "ssh/ethernet_host", self._ethernet_host.text().strip()
        )
        self._settings.setValue(
            "ssh/automatic_ethernet_fallback",
            self._automatic_fallback.isChecked(),
        )
        self._settings.setValue(
            "robot/workspace", self._remote_workspace.text().strip()
        )
        self._settings.setValue("robot/domain_id", self._domain_id.value())
        self._settings.setValue(
            "robot/rmw_implementation", self._rmw_implementation.text().strip()
        )
        self._settings.setValue(
            "local/workspace", self._local_workspace.text().strip()
        )
        self._settings.setValue(
            "options/show_start_confirmation",
            self._show_start_confirmation.isChecked(),
        )
        self._settings.setValue(
            "options/launch_rviz_with_bringup",
            self._launch_rviz_with_bringup.isChecked(),
        )
        if self._map_selector.currentText():
            self._settings.setValue(
                "localization/map", self._map_selector.currentText()
            )
        self._settings.setValue("mapping/map_name", self._map_name.text().strip())
        self._settings.setValue("ssh/auto_monitor", self._auto_monitor.isChecked())
        self._settings.setValue("appearance/dark_theme", self._dark_theme)
        self._settings.setValue(
            "appearance/log_font_size", self._log_font_size
        )
        self._settings.sync()

    def _wifi_settings(self) -> SshSettings:
        return SshSettings(
            host=self._host.text().strip(),
            username=self._username.text().strip(),
            port=self._port.value(),
            identity_file=self._identity_file.text().strip(),
        )

    def _ethernet_settings(self) -> SshSettings:
        return SshSettings(
            host=self._ethernet_host.text().strip(),
            username=self._username.text().strip(),
            port=22,
            identity_file=self._identity_file.text().strip(),
        )

    def _settings_for_route(self, route: str) -> SshSettings:
        if route == "wifi":
            return self._wifi_settings()
        if route == "ethernet":
            return self._ethernet_settings()
        raise ValueError("Unknown SSH route: {}".format(route))

    def _current_settings(self) -> SshSettings:
        return self._settings_for_route(self._active_route)

    def _set_launch_intent(self, subsystem: str, desired: bool) -> None:
        self._launch_intent[subsystem] = desired
        self._launch_intent_time[subsystem] = time.monotonic()
        if desired:
            prefix = subsystem.title() + "/"
            self._health_previously_healthy = {
                key for key in self._health_previously_healthy
                if not key.startswith(prefix)
            }
        self._update_system_health()

    def _observe_launch_state(self, subsystem: str, running: bool) -> None:
        if self._launch_intent[subsystem] is None:
            self._launch_intent[subsystem] = running
            self._launch_intent_time[subsystem] = time.monotonic()
        self._update_system_health()

    def _clear_launch_intent(self, subsystem: str) -> None:
        self._launch_intent[subsystem] = None
        self._launch_intent_time[subsystem] = time.monotonic()
        self._update_system_health()

    def _launch_health_states(self):
        now = time.monotonic()
        return {
            "bringup": {
                "desired": self._launch_intent["bringup"],
                "running": self._bringup_running,
                "known": self._bringup_state_known,
                "elapsed": now - self._launch_intent_time["bringup"],
            },
            "localization": {
                "desired": self._launch_intent["localization"],
                "running": self._localization_running,
                "known": self._localization_state_known,
                "elapsed": now - self._launch_intent_time["localization"],
            },
            "mapping": {
                "desired": self._launch_intent["mapping"],
                "running": self._mapping_running,
                "known": self._mapping_state_known,
                "elapsed": now - self._launch_intent_time["mapping"],
            },
            "nav2": {
                "desired": self._launch_intent["nav2"],
                "running": self._navigation_running,
                "known": self._navigation_state_known,
                "elapsed": now - self._launch_intent_time["nav2"],
            },
        }

    def _show_system_health(self) -> None:
        self._log_tabs.setCurrentWidget(self._health_table)

    def _refresh_parameter_files(self, _checked=False) -> None:
        if not self._ssh_connected or self._parameter_file_list_process is not None:
            return
        workspace, _domain_id, _rmw = self._robot_command_settings()
        try:
            command = parameter_file_list_command(workspace)
            arguments = remote_command_arguments(
                self._current_settings(), command
            )
        except ValueError as error:
            self._parameter_status.setText(str(error))
            return
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._parameter_file_list_finished)
        process.errorOccurred.connect(self._parameter_file_list_error)
        self._parameter_file_list_process = process
        self._parameter_status.setText("Discovering YAML files on the Jetson…")
        self._update_parameter_controls()
        process.start("ssh", arguments)

    def _parameter_file_list_finished(
        self, exit_code: int, _exit_status
    ) -> None:
        process = self._parameter_file_list_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._parameter_file_list_process = None
        if exit_code != 0:
            self._parameter_status.setText(
                output or "Could not list parameter YAML files."
            )
            self._update_parameter_controls()
            return
        filenames = [
            line.strip() for line in output.splitlines()
            if line.strip().endswith((".yaml", ".yml"))
        ]
        previous = self._parameter_current_file
        target = previous or self._saved_parameter_filename
        if target not in filenames:
            target = (
                "nav2_params_real.yaml"
                if "nav2_params_real.yaml" in filenames
                else (filenames[0] if filenames else "")
            )
        self._parameter_file_selector.blockSignals(True)
        self._parameter_file_selector.clear()
        self._parameter_file_selector.addItems(filenames)
        if target:
            self._parameter_file_selector.setCurrentText(target)
        self._parameter_file_selector.blockSignals(False)
        if target and (self._parameter_document is None or target != previous):
            self._load_parameter_file(target)
        elif not filenames:
            self._parameter_status.setText(
                "No YAML files found in amr_navigation/config."
            )
        self._update_parameter_controls()

    def _parameter_file_list_error(self, _process_error) -> None:
        process = self._parameter_file_list_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._parameter_file_list_process = None
        process.deleteLater()
        self._parameter_status.setText(
            "Could not start SSH while listing parameter files."
        )
        self._update_parameter_controls()

    def _parameter_file_selected(self, filename: str) -> None:
        if not filename or filename == self._parameter_current_file:
            return
        if self._parameter_invalid_edits:
            answer = QMessageBox.warning(
                self,
                "Invalid staged parameter values",
                "The red values cannot be saved. Discard those invalid edits "
                "before opening another file?",
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if answer != QMessageBox.Discard:
                self._restore_parameter_selector()
                return
            self._parameter_invalid_edits.clear()
        document = self._parameter_document
        if document is not None and document.dirty:
            answer = QMessageBox.warning(
                self,
                "Unsaved parameter changes",
                "Save changes to {} before opening {}?".format(
                    self._parameter_current_file, filename
                ),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer == QMessageBox.Cancel:
                self._restore_parameter_selector()
                return
            if answer == QMessageBox.Save:
                self._pending_parameter_file = filename
                self._restore_parameter_selector()
                self._save_parameter_yaml()
                return
        self._load_parameter_file(filename)

    def _restore_parameter_selector(self) -> None:
        self._parameter_file_selector.blockSignals(True)
        self._parameter_file_selector.setCurrentText(
            self._parameter_current_file
        )
        self._parameter_file_selector.blockSignals(False)

    def _load_parameter_file(self, filename: str) -> None:
        if not self._ssh_connected or self._parameter_read_process is not None:
            return
        workspace, _domain_id, _rmw = self._robot_command_settings()
        try:
            command = parameter_file_read_command(workspace, filename)
            arguments = remote_command_arguments(
                self._current_settings(), command
            )
        except ValueError as error:
            self._parameter_status.setText(str(error))
            return
        process = QProcess(self)
        process.setProperty("filename", filename)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._parameter_file_read_finished)
        process.errorOccurred.connect(self._parameter_file_read_error)
        self._parameter_read_process = process
        self._parameter_status.setText("Loading {}…".format(filename))
        self._update_parameter_controls()
        process.start("ssh", arguments)

    def _parameter_file_read_finished(
        self, exit_code: int, _exit_status
    ) -> None:
        process = self._parameter_read_process
        if process is None:
            return
        filename = process.property("filename")
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._parameter_read_process = None
        if exit_code != 0 or PARAMETER_FILE_MARKER not in output:
            self._parameter_status.setText(
                output or "Could not read {}.".format(filename)
            )
            self._restore_parameter_selector()
            self._update_parameter_controls()
            return
        encoded = output.split(PARAMETER_FILE_MARKER, 1)[1].strip()
        try:
            source = base64.b64decode(encoded, validate=True).decode("utf-8")
            document = ParameterDocument(filename, source)
        except (ValueError, UnicodeError) as error:
            self._parameter_status.setText(
                "Could not parse {}: {}".format(filename, error)
            )
            self._restore_parameter_selector()
            self._update_parameter_controls()
            return
        self._parameter_document = document
        self._parameter_current_file = filename
        self._parameter_source_sha256 = content_sha256(source)
        self._saved_parameter_filename = filename
        self._parameter_file_selector.blockSignals(True)
        self._parameter_file_selector.setCurrentText(filename)
        self._parameter_file_selector.blockSignals(False)
        self._rebuild_parameter_tree()
        self._parameter_status.setText(
            "Loaded {} parameters from {}. Changes are staged until Save "
            "YAML is selected.".format(len(document.entries), filename)
        )
        self._save_settings()
        self._update_parameter_controls()

    def _parameter_file_read_error(self, _process_error) -> None:
        process = self._parameter_read_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._parameter_read_process = None
        process.deleteLater()
        self._parameter_status.setText(
            "Could not start SSH while reading the parameter file."
        )
        self._restore_parameter_selector()
        self._update_parameter_controls()

    def _rebuild_parameter_tree(self, _checked=False) -> None:
        if not hasattr(self, "_parameter_tree"):
            return
        self._parameter_tree_building = True
        self._parameter_tree.clear()
        self._parameter_items = {}
        self._parameter_value_edits = {}
        self._parameter_action_buttons = {}
        self._parameter_invalid_edits = set()
        document = self._parameter_document
        if document is None:
            self._parameter_tree_building = False
            self._update_parameter_controls()
            return
        entries = document.entries
        if self._favorite_parameters_only.isChecked():
            entries = [
                entry for entry in entries
                if entry.identifier in self._parameter_favorites
            ]
        group_item = None
        group_key = None
        for entry in entries:
            next_group = (entry.node, entry.section)
            if next_group != group_key:
                group_key = next_group
                group_item = QTreeWidgetItem(self._parameter_tree)
                group_item.setText(
                    0, "{} — {}".format(entry.section, entry.node)
                )
                group_item.setFirstColumnSpanned(True)
                group_item.setExpanded(True)
                font = group_item.font(0)
                font.setBold(True)
                group_item.setFont(0, font)
                group_item.setSizeHint(0, QSize(0, 36))
            item = QTreeWidgetItem(group_item)
            item.setData(0, Qt.UserRole, entry.identifier)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                0,
                Qt.Checked
                if entry.identifier in self._parameter_favorites
                else Qt.Unchecked,
            )
            item.setText(1, entry.name)
            item.setText(3, entry.description or "No YAML comment provided.")
            item.setToolTip(3, item.text(3))
            item.setSizeHint(0, QSize(0, 46))
            self._parameter_items[entry.identifier] = item

            value_edit = QLineEdit()
            value_edit.setText(entry.display_text.replace("\n", " "))
            value_edit.setReadOnly(not entry.editable)
            value_edit.setMinimumHeight(34)
            value_edit.setToolTip(
                "Edit this scalar value; it remains staged until Save YAML."
                if entry.editable
                else "Complex list/map values are displayed read-only."
            )
            value_edit.editingFinished.connect(
                lambda identifier=entry.identifier:
                self._parameter_value_edited(identifier)
            )
            self._parameter_tree.setItemWidget(item, 2, value_edit)
            self._parameter_value_edits[entry.identifier] = value_edit
            self._style_parameter_value(entry)

            if entry.policy.mode == "live":
                button = QPushButton("Send live")
                button.setProperty("role", "action")
                button.setToolTip(
                    "Apply this verified Foxy runtime parameter immediately. "
                    "Save YAML separately to keep it after restart."
                )
                button.clicked.connect(
                    lambda _checked=False, identifier=entry.identifier:
                    self._send_parameter_live(identifier)
                )
            else:
                owner_label = {
                    "nav2": "Nav2",
                    "bringup": "bringup",
                    "external": "external process",
                }[entry.policy.owner]
                button = QPushButton("Restart {}".format(owner_label))
                button.setProperty("role", "stop")
                button.setToolTip(
                    "This value is loaded during configuration. Save YAML, "
                    "then restart its owning process."
                )
                button.clicked.connect(
                    lambda _checked=False, identifier=entry.identifier:
                    self._restart_parameter_owner(identifier)
                )
                self._decorate_button(
                    button, ("view-refresh",), QStyle.SP_BrowserReload
                )
            button.setMinimumHeight(34)
            self._parameter_tree.setItemWidget(item, 4, button)
            self._parameter_action_buttons[entry.identifier] = button
        self._parameter_tree_building = False
        if self._favorite_parameters_only.isChecked() and not entries:
            self._parameter_status.setText(
                "No parameters are starred in this YAML file."
            )
        self._update_parameter_controls()

    def _parameter_tree_item_changed(self, item, column: int) -> None:
        if self._parameter_tree_building or column != 0:
            return
        identifier = item.data(0, Qt.UserRole)
        if not identifier:
            return
        if item.checkState(0) == Qt.Checked:
            self._parameter_favorites.add(identifier)
        else:
            self._parameter_favorites.discard(identifier)
        self._save_settings()
        if self._favorite_parameters_only.isChecked():
            QTimer.singleShot(0, self._rebuild_parameter_tree)

    def _parameter_value_edited(self, identifier: str) -> None:
        document = self._parameter_document
        value_edit = self._parameter_value_edits.get(identifier)
        if document is None or value_edit is None:
            return
        if not document.entry(identifier).editable:
            return
        try:
            entry = document.stage(identifier, value_edit.text())
        except ValueError as error:
            self._parameter_invalid_edits.add(identifier)
            value_edit.setStyleSheet("border: 1px solid #c62828;")
            value_edit.setToolTip(str(error))
            self._parameter_status.setText(
                "Invalid value for {}: {}".format(
                    document.entry(identifier).name, error
                )
            )
            self._update_parameter_controls()
            return
        self._parameter_invalid_edits.discard(identifier)
        value_edit.setText(entry.display_text)
        self._style_parameter_value(entry)
        if entry.dirty:
            self._parameter_status.setText(
                "Staged {} = {}. Save YAML to make it persistent.".format(
                    entry.name, entry.staged_text
                )
            )
        else:
            self._parameter_status.setText(
                "{} matches the saved YAML value.".format(entry.name)
            )
        self._update_parameter_controls()

    def _style_parameter_value(self, entry) -> None:
        value_edit = self._parameter_value_edits.get(entry.identifier)
        if value_edit is None:
            return
        if entry.dirty:
            value_edit.setStyleSheet("border: 1px solid #d18b00;")
            value_edit.setToolTip(
                "Unsaved staged value. Select Save YAML to persist it."
            )
        else:
            value_edit.setStyleSheet("")

    def _save_parameter_yaml(self, _checked=False) -> None:
        document = self._parameter_document
        if document is None:
            return
        if self._parameter_invalid_edits:
            QMessageBox.warning(
                self,
                "Invalid parameter value",
                "Correct the red parameter value before saving the YAML.",
            )
            return
        if not document.dirty:
            self._parameter_status.setText("No parameter changes to save.")
            self._continue_after_parameter_save()
            return
        if not self._ssh_connected or self._parameter_write_process is not None:
            self._parameter_status.setText(
                "A working SSH connection is required to save YAML."
            )
            self._close_after_parameter_save = False
            return
        try:
            content = document.render()
            command = parameter_file_write_command(
                self._remote_workspace.text().strip(),
                self._parameter_current_file,
                content,
                self._parameter_source_sha256,
            )
            arguments = remote_command_arguments(
                self._current_settings(), command
            )
        except ValueError as error:
            self._parameter_status.setText(str(error))
            self._close_after_parameter_save = False
            return
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._parameter_file_write_finished)
        process.errorOccurred.connect(self._parameter_file_write_error)
        self._parameter_write_process = process
        self._parameter_saved_content = content
        self._parameter_status.setText(
            "Saving {} atomically…".format(self._parameter_current_file)
        )
        self._update_parameter_controls()
        process.start("ssh", arguments)

    def _parameter_file_write_finished(
        self, exit_code: int, _exit_status
    ) -> None:
        process = self._parameter_write_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._parameter_write_process = None
        if exit_code != 0 or PARAMETER_SAVE_MARKER not in output:
            self._close_after_parameter_save = False
            if PARAMETER_CONFLICT_MARKER in output:
                message = (
                    "The Jetson YAML changed after it was loaded. Refresh the "
                    "file before saving so another edit is not overwritten."
                )
            else:
                message = output or "The remote YAML save failed."
            self._parameter_status.setText(message)
            QMessageBox.warning(self, "Could not save parameter YAML", message)
            self._update_parameter_controls()
            return
        try:
            document = ParameterDocument(
                self._parameter_current_file,
                self._parameter_saved_content,
            )
        except ValueError as error:
            self._parameter_status.setText(
                "YAML saved, but could not refresh the editor: {}".format(error)
            )
            self._update_parameter_controls()
            return
        self._parameter_document = document
        self._parameter_source_sha256 = content_sha256(
            self._parameter_saved_content
        )
        self._parameter_saved_content = ""
        self._rebuild_parameter_tree()
        self._parameter_status.setText(
            "Saved {}. A timestamp-independent backup is stored beside it as "
            "{}.amr_operator_gui.bak.".format(
                self._parameter_current_file, self._parameter_current_file
            )
        )
        self._append_log(
            "Saved staged parameter changes to {} on the Jetson.".format(
                self._parameter_current_file
            )
        )
        self._continue_after_parameter_save()

    def _continue_after_parameter_save(self) -> None:
        pending_file = self._pending_parameter_file
        pending_restart = self._pending_parameter_restart
        close_after_save = self._close_after_parameter_save
        self._pending_parameter_file = ""
        self._pending_parameter_restart = ""
        self._close_after_parameter_save = False
        if pending_file:
            self._load_parameter_file(pending_file)
        elif pending_restart:
            self._perform_parameter_restart(pending_restart)
        elif close_after_save:
            self._allow_close = True
            self.close()

    def _parameter_file_write_error(self, _process_error) -> None:
        process = self._parameter_write_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._parameter_write_process = None
        self._close_after_parameter_save = False
        process.deleteLater()
        self._parameter_status.setText(
            "Could not start SSH while saving the parameter file."
        )
        self._update_parameter_controls()

    def _send_parameter_live(self, identifier: str) -> None:
        document = self._parameter_document
        if document is None or self._parameter_live_process is not None:
            return
        self._parameter_value_edited(identifier)
        if identifier in self._parameter_invalid_edits:
            return
        entry = document.entry(identifier)
        if entry.policy.mode != "live" or not self._navigation_running:
            return
        answer = QMessageBox.question(
            self,
            "Apply parameter to running Nav2?",
            "Apply {} = {} immediately? This can change robot motion during "
            "an active goal. The value remains staged until Save YAML is "
            "selected.".format(entry.name, entry.display_text),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = live_parameter_command(
                workspace,
                entry.policy.node,
                entry.name,
                entry.display_text,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
            arguments = remote_command_arguments(
                self._current_settings(), command
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot apply parameter", str(error))
            return
        process = QProcess(self)
        process.setProperty("identifier", identifier)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._live_parameter_finished)
        process.errorOccurred.connect(self._live_parameter_error)
        self._parameter_live_process = process
        self._parameter_status.setText(
            "Sending {} to {}…".format(entry.name, entry.policy.node)
        )
        self._update_parameter_controls()
        process.start("ssh", arguments)

    def _live_parameter_finished(self, exit_code: int, _exit_status) -> None:
        process = self._parameter_live_process
        if process is None:
            return
        identifier = process.property("identifier")
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._parameter_live_process = None
        entry = (
            self._parameter_document.entry(identifier)
            if self._parameter_document is not None
            else None
        )
        if exit_code == 0 and entry is not None:
            self._parameter_status.setText(
                "Live update accepted for {}. {}".format(entry.name, output)
            )
            self._append_log(
                "Live Nav2 parameter update: {} = {}. {}".format(
                    entry.name, entry.display_text, output
                )
            )
        else:
            message = output or "Live parameter command failed."
            self._parameter_status.setText(message)
            QMessageBox.warning(self, "Live parameter rejected", message)
        self._update_parameter_controls()

    def _live_parameter_error(self, _process_error) -> None:
        process = self._parameter_live_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._parameter_live_process = None
        process.deleteLater()
        self._parameter_status.setText(
            "Could not start SSH for the live parameter update."
        )
        self._update_parameter_controls()

    def _restart_parameter_owner(self, identifier: str) -> None:
        document = self._parameter_document
        if document is None:
            return
        self._parameter_value_edited(identifier)
        if identifier in self._parameter_invalid_edits:
            return
        owner = document.entry(identifier).policy.owner
        if document.dirty:
            answer = QMessageBox.question(
                self,
                "Save before restart?",
                "Restarting loads values from the YAML file. Save all staged "
                "changes before restarting {}?".format(owner),
                QMessageBox.Save | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer != QMessageBox.Save:
                return
            self._pending_parameter_restart = owner
            self._save_parameter_yaml()
            return
        self._perform_parameter_restart(owner)

    def _perform_parameter_restart(self, owner: str) -> None:
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        if owner == "nav2":
            if not self._navigation_running:
                QMessageBox.information(
                    self,
                    "Nav2 is stopped",
                    "No restart is needed. The next Start Nav2 action will "
                    "load the saved YAML values.",
                )
                return
            answer = QMessageBox.warning(
                self,
                "Restart Nav2?",
                "This cancels any active navigation goal, gracefully stops "
                "Nav2, and starts its lifecycle nodes with the saved YAML. "
                "Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            try:
                command = restart_navigation_command(
                    workspace,
                    domain_id=domain_id,
                    rmw_implementation=rmw_implementation,
                )
            except ValueError as error:
                QMessageBox.warning(self, "Cannot restart Nav2", str(error))
                return
            self._run_navigation_operation(
                command, "Restarting Nav2 with saved parameters…", "restart"
            )
            return
        if owner == "bringup":
            if self._navigation_running or self._localization_running:
                QMessageBox.information(
                    self,
                    "Dependent processes are running",
                    "Stop Nav2 and localization before restarting physical "
                    "bringup. This preserves the required shutdown order.",
                )
                return
            if self._mapping_running:
                QMessageBox.information(
                    self,
                    "Mapping is running",
                    "Stop mapping before restarting physical bringup.",
                )
                return
            if not self._bringup_running:
                QMessageBox.information(
                    self,
                    "Bringup is stopped",
                    "No restart is needed. The next physical bringup start "
                    "will load the saved YAML values.",
                )
                return
            answer = QMessageBox.warning(
                self,
                "Restart physical bringup?",
                "This stops and restarts the motor driver, sensors, joystick, "
                "and twist mux. Ensure the robot is stationary. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            try:
                command = restart_bringup_command(
                    workspace,
                    domain_id=domain_id,
                    rmw_implementation=rmw_implementation,
                )
            except ValueError as error:
                QMessageBox.warning(self, "Cannot restart bringup", str(error))
                return
            self._run_bringup_operation(
                command,
                "Restarting physical bringup with saved parameters…",
                "restart",
            )
            return
        QMessageBox.information(
            self,
            "External restart required",
            "This YAML file is not owned by a process managed by the operator "
            "app. Save it, then restart its launch externally.",
        )

    def _update_parameter_controls(self) -> None:
        if not hasattr(self, "_parameter_file_selector"):
            return
        file_busy = any((
            self._parameter_file_list_process is not None,
            self._parameter_read_process is not None,
            self._parameter_write_process is not None,
        ))
        self._refresh_parameter_files_button.setEnabled(
            self._ssh_connected and not file_busy
        )
        self._parameter_file_selector.setEnabled(not file_busy)
        dirty = bool(
            self._parameter_document is not None
            and self._parameter_document.dirty
        )
        self._save_parameter_yaml_button.setEnabled(
            self._ssh_connected and dirty and not file_busy
        )
        for identifier, button in self._parameter_action_buttons.items():
            if self._parameter_document is None:
                button.setEnabled(False)
                continue
            entry = self._parameter_document.entry(identifier)
            if entry.policy.mode == "live":
                enabled = (
                    self._ssh_connected
                    and self._navigation_running
                    and self._parameter_live_process is None
                    and entry.editable
                )
            elif entry.policy.owner == "nav2":
                enabled = (
                    self._ssh_connected
                    and self._navigation_running
                    and self._navigation_operation_process is None
                    and not file_busy
                )
            elif entry.policy.owner == "bringup":
                enabled = (
                    self._ssh_connected
                    and self._bringup_running
                    and not self._navigation_running
                    and not self._localization_running
                    and not self._mapping_running
                    and self._bringup_operation_process is None
                    and not file_busy
                )
            else:
                enabled = self._ssh_connected and not file_busy
            button.setEnabled(enabled)

    def _start_system_health_probe(self) -> None:
        if self._system_health_process is not None or not self._ssh_connected:
            return
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = system_health_probe_command(
                workspace,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
            arguments = remote_command_arguments(
                self._current_settings(), command
            )
        except ValueError as error:
            self._set_health_status("error", str(error))
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_system_health_output)
        process.finished.connect(self._system_health_finished)
        process.errorOccurred.connect(self._system_health_process_error)
        self._system_health_process = process
        self._system_health_buffer = ""
        self._system_health_last_snapshot_time = 0.0
        self._health_snapshot = None
        self._set_health_status("starting", "System health probe connecting…")
        process.start("ssh", arguments)

    def _read_system_health_output(self) -> None:
        process = self._system_health_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._system_health_buffer += output
        lines = self._system_health_buffer.split("\n")
        self._system_health_buffer = lines.pop()
        for line in lines:
            marker_index = line.find(HEALTH_MARKER)
            if marker_index < 0:
                continue
            payload = line[marker_index + len(HEALTH_MARKER):]
            try:
                snapshot = json.loads(payload)
            except (TypeError, ValueError):
                continue
            if snapshot.get("version") != 1:
                continue
            self._health_snapshot = snapshot
            self._system_health_last_snapshot_time = time.monotonic()
            self._apply_probe_health_to_primary_indicators(snapshot)
            self._render_system_health()

    def _apply_probe_health_to_primary_indicators(self, snapshot) -> None:
        map_base = snapshot.get("transforms", {}).get("map_base", {})
        if map_base.get("available"):
            self._tf_last_transform_time = time.monotonic()
            if self._localization_running or self._mapping_running:
                self._set_tf_status("ready", "map → base_link available")
        elif self._localization_running or self._mapping_running:
            self._tf_last_transform_time = 0.0
            self._set_tf_status("waiting", "Waiting for map → base_link")

        if self._navigation_running:
            action_ready = bool(
                snapshot.get("actions", {}).get("navigate_to_pose", False)
            )
            if action_ready:
                self._nav_action_last_ready_time = time.monotonic()
                self._set_nav_action_status("ready", "NavigateToPose ready")
            else:
                self._nav_action_last_ready_time = 0.0
                self._set_nav_action_status(
                    "waiting", "NavigateToPose waiting"
                )

    def _update_system_health(self) -> None:
        if not self._ssh_connected:
            self._render_system_health()
            return
        if self._system_health_process is None:
            self._start_system_health_probe()
        if (
            self._system_health_last_snapshot_time
            and time.monotonic() - self._system_health_last_snapshot_time > 6.0
        ):
            self._health_snapshot = None
            self._tf_last_transform_time = 0.0
            self._set_health_status("warning", "Health probe data is stale")
        self._render_system_health()

    def _render_system_health(self) -> None:
        checks = evaluate_health(
            self._health_snapshot,
            self._launch_health_states(),
            connected=self._ssh_connected,
            previously_healthy=self._health_previously_healthy,
        )
        self._health_checks = checks
        for check in checks:
            if check.state == "healthy":
                self._health_previously_healthy.add(check.key)

        self._health_table.setRowCount(len(checks))
        state_colours = {
            "healthy": "#1b8a3c",
            "warning": "#d18b00",
            "starting": "#2d78b7",
            "error": "#c62828",
            "inactive": "#777777",
            "unknown": "#777777",
        }
        state_labels = {
            "healthy": "Healthy",
            "warning": "Warning",
            "starting": "Starting",
            "error": "Error",
            "inactive": "Stopped",
            "unknown": "Unknown",
        }
        current_states = {}
        for row, check in enumerate(checks):
            values = (
                check.subsystem,
                check.name,
                state_labels.get(check.state, check.state.title()),
                check.detail,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setForeground(QColor(state_colours.get(
                        check.state, "#777777"
                    )))
                self._health_table.setItem(row, column, item)
            current_states[check.key] = check.state
            previous = self._health_previous_states.get(check.key)
            if previous is not None and previous != check.state:
                if check.state == "error":
                    self._append_log(
                        "Health error: {} — {}".format(
                            check.key, check.detail
                        ),
                        error=True,
                    )
                elif previous == "error" and check.state == "healthy":
                    self._append_log(
                        "Health recovered: {}.".format(check.key)
                    )
        self._health_previous_states = current_states

        overall, counts = overall_health(checks)
        if counts["error"]:
            summary = "{} error(s), {} warning(s)".format(
                counts["error"], counts["warning"]
            )
        elif counts["warning"]:
            summary = "{} warning(s)".format(counts["warning"])
        elif counts["starting"]:
            summary = "{} check(s) starting".format(counts["starting"])
        elif checks and all(check.state == "inactive" for check in checks):
            summary = "All robot launches stopped"
        elif overall == "healthy":
            summary = "All expected systems healthy"
        else:
            summary = "Health unavailable"
        self._set_health_status(overall, summary)

    def _set_health_status(self, state: str, text: str) -> None:
        colours = {
            "healthy": "#1b8a3c",
            "warning": "#d18b00",
            "starting": "#2d78b7",
            "error": "#c62828",
            "unknown": "#777777",
        }
        self._health_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(
                colours.get(state, "#777777")
            )
        )
        self._health_status_text.setText("System health: {}".format(text))

    def _stop_system_health_probe(self) -> None:
        process = self._system_health_process
        self._system_health_process = None
        self._system_health_buffer = ""
        self._system_health_last_snapshot_time = 0.0
        self._health_snapshot = None
        if process is not None:
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()
        self._render_system_health()

    def _system_health_finished(self, _exit_code: int, _exit_status) -> None:
        process = self._system_health_process
        if process is None:
            return
        self._read_system_health_output()
        process.deleteLater()
        self._system_health_process = None
        self._system_health_last_snapshot_time = 0.0
        self._health_snapshot = None
        if self._ssh_connected:
            self._set_health_status("warning", "Health probe reconnecting…")

    def _system_health_process_error(self, _process_error) -> None:
        process = self._system_health_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._system_health_process = None
        process.deleteLater()
        self._health_snapshot = None
        self._set_health_status("error", "Could not start health probe")
        self._render_system_health()

    def _manual_connection_test(self) -> None:
        self._start_connection_checks(manual=True)

    def _automatic_connection_test(self) -> None:
        if self._auto_monitor.isChecked():
            self._start_connection_checks(manual=False)

    def _start_connection_checks(self, manual: bool) -> None:
        if self._ssh_process is not None:
            return
        if self._connection_check_queue:
            return

        self._save_settings()
        self._check_was_manual = manual
        self._connection_check_queue = ["wifi"]
        if manual or self._automatic_fallback.isChecked():
            self._connection_check_queue.append("ethernet")
        if manual:
            self._append_log("Testing Wi-Fi and Ethernet SSH routes…")
        self._test_button.setEnabled(False)
        self._run_next_connection_check()

    def _run_next_connection_check(self) -> None:
        if not self._connection_check_queue:
            self._finish_connection_checks()
            return

        route = self._connection_check_queue.pop(0)
        try:
            settings = self._settings_for_route(route)
            arguments = connection_test_arguments(settings)
        except ValueError as error:
            self._set_route_connected(route, False)
            self._append_log(str(error), error=True)
            QTimer.singleShot(0, self._run_next_connection_check)
            return

        self._connection_route_under_test = route
        route_label = self._route_label(route)
        self._set_status("checking", "Checking {} SSH…".format(route_label))
        self._set_route_status(route, "checking", "{} checking".format(
            route_label
        ))

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._connection_test_finished)
        process.errorOccurred.connect(self._connection_process_error)
        self._ssh_process = process
        process.start("ssh", arguments)

    def _connection_test_finished(self, exit_code: int, _exit_status) -> None:
        process = self._ssh_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        route = self._connection_route_under_test
        route_label = self._route_label(route)
        process.deleteLater()
        self._ssh_process = None
        self._connection_route_under_test = ""

        if exit_code == 0:
            self._set_route_connected(route, True)
            self._set_route_status(
                route, "connected", "{} SSH available".format(route_label)
            )
            if self._check_was_manual:
                self._append_log("{} SSH passed.".format(route_label))
        else:
            self._set_route_connected(route, False)
            self._set_route_status(
                route, "disconnected", "{} SSH unavailable".format(route_label)
            )
            if self._check_was_manual:
                self._append_log(
                    "{} SSH failed (exit {}).{}".format(
                        route_label,
                        exit_code,
                        "\n" + output if output else "",
                    ),
                    error=True,
                )
        QTimer.singleShot(0, self._run_next_connection_check)

    def _finish_connection_checks(self) -> None:
        previous_route = self._active_route
        was_connected = self._ssh_connected
        if self._wifi_connected:
            self._active_route = "wifi"
            self._ssh_connected = True
        elif self._automatic_fallback.isChecked() and self._ethernet_connected:
            self._active_route = "ethernet"
            self._ssh_connected = True
        else:
            self._ssh_connected = False

        self._test_button.setEnabled(True)
        if self._ssh_connected:
            active_label = self._route_label(self._active_route)
            self._set_status(
                "connected", "SSH connected via {}".format(active_label)
            )
            if not was_connected or previous_route != self._active_route:
                self._append_log(
                    "Active robot connection: {} SSH.".format(active_label)
                )
                self._stop_system_health_probe()
            self._start_system_health_probe()
            self._poll_bringup()
            self._poll_localization()
            self._poll_mapping()
            self._poll_navigation()
            if self._map_selector.count() == 0:
                self._refresh_maps()
            if self._parameter_file_selector.count() == 0:
                self._refresh_parameter_files()
        else:
            self._mark_robot_connection_unavailable()
        self._update_connection_controls()
        self._update_all_session_controls()
        self._update_parameter_controls()

    def _connection_process_error(self, _process_error) -> None:
        if self._ssh_process is None:
            return
        if self._ssh_process.error() == QProcess.FailedToStart:
            process = self._ssh_process
            self._ssh_process = None
            self._connection_check_queue = []
            self._connection_route_under_test = ""
            self._test_button.setEnabled(True)
            self._mark_robot_connection_unavailable()
            self._set_status("error", "OpenSSH client not found")
            self._append_log(
                "Could not start the 'ssh' executable. Install openssh-client.",
                error=True,
            )
            process.deleteLater()
            self._update_connection_controls()
            self._update_all_session_controls()

    @staticmethod
    def _route_label(route: str) -> str:
        return "Wi-Fi" if route == "wifi" else "Ethernet fallback"

    def _set_route_connected(self, route: str, connected: bool) -> None:
        if route == "wifi":
            self._wifi_connected = connected
        else:
            self._ethernet_connected = connected

    def _set_route_status(self, route: str, state: str, text: str) -> None:
        colours = {
            "connected": "#1b8a3c",
            "checking": "#d18b00",
            "disconnected": "#c62828",
        }
        dot = self._wifi_route_dot if route == "wifi" else self._ethernet_route_dot
        label = (
            self._wifi_route_text
            if route == "wifi"
            else self._ethernet_route_text
        )
        dot.setStyleSheet(
            "font-size: 18px; color: {};".format(colours.get(state, "#777"))
        )
        label.setText(text)

    def _mark_robot_connection_unavailable(self) -> None:
        self._ssh_connected = False
        self._bringup_running = False
        self._localization_running = False
        self._mapping_running = False
        self._navigation_running = False
        self._bringup_state_known = False
        self._localization_state_known = False
        self._mapping_state_known = False
        self._navigation_state_known = False
        self._set_status("disconnected", "Both SSH routes unavailable")
        self._set_bringup_status("unknown", "Bringup status unavailable")
        self._set_localization_status("unknown", "Localization unavailable")
        self._set_mapping_status("unknown", "Mapping status unavailable")
        self._set_navigation_status("unknown", "Nav2 status unavailable")
        self._stop_tf_probe()
        self._stop_nav_health_probe()
        self._stop_system_health_probe()
        self._update_parameter_controls()

    def _update_connection_controls(self) -> None:
        checking = self._ssh_process is not None or bool(
            self._connection_check_queue
        )
        diagnosing = (
            self._diagnostic_local_process is not None
            or self._diagnostic_remote_process is not None
        )
        self._test_button.setEnabled(not checking)
        self._diagnose_button.setEnabled(self._ssh_connected and not diagnosing)
        self._shutdown_jetson_button.setEnabled(
            self._ssh_connected and self._shutdown_process is None
        )
        self._update_parameter_controls()

    def _fallback_policy_changed(self, _enabled: bool) -> None:
        self._save_settings()
        self._start_connection_checks(manual=False)

    def _shutdown_jetson(self) -> None:
        if not self._ssh_connected or self._shutdown_process is not None:
            return

        running = []
        if self._navigation_running:
            running.append("Nav2")
        if self._mapping_running:
            running.append("SLAM mapping")
        if self._localization_running:
            running.append("localization")
        if self._bringup_running:
            running.append("physical bringup")
        running_text = ""
        if running:
            running_text = (
                "\n\nCurrently running: {}. These processes will be stopped "
                "by the operating-system shutdown."
            ).format(", ".join(running))

        answer = QMessageBox.warning(
            self,
            "Shut down Jetson Nano?",
            "This will power off the Jetson, stop all robot processes, and "
            "disconnect SSH. Make sure the robot is stationary before "
            "continuing.{}".format(running_text),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            arguments = remote_command_arguments(
                self._current_settings(), shutdown_command()
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid SSH settings", str(error))
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._shutdown_finished)
        process.errorOccurred.connect(self._shutdown_process_error)
        self._shutdown_process = process
        self._append_log(
            "Sending guarded shutdown request over {} SSH…".format(
                self._route_label(self._active_route)
            )
        )
        self._set_status("checking", "Requesting Jetson shutdown…")
        self._update_connection_controls()
        process.start("ssh", arguments)

    def _shutdown_finished(self, exit_code: int, _exit_status) -> None:
        process = self._shutdown_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._shutdown_process = None

        permission_denied = SHUTDOWN_PERMISSION_DENIED_MARKER in output
        authorized = SHUTDOWN_AUTHORIZED_MARKER in output
        succeeded = exit_code == 0 or (exit_code == 255 and authorized)
        clean_output = output.replace(SHUTDOWN_AUTHORIZED_MARKER, "").replace(
            SHUTDOWN_PERMISSION_DENIED_MARKER, ""
        ).strip()

        if permission_denied:
            self._append_log(
                "Jetson shutdown was refused: passwordless permission for "
                "'/bin/systemctl poweroff' is not configured.",
                error=True,
            )
            QMessageBox.warning(
                self,
                "Jetson shutdown permission required",
                "The GUI never asks for or stores a sudo password. Configure "
                "the command-specific sudoers rule documented in the "
                "amr_operator_gui README, then try again.",
            )
        elif not succeeded:
            detail = clean_output or (
                "SSH command exited with code {}.".format(exit_code)
            )
            self._append_log(
                "Jetson shutdown command failed: {}".format(detail),
                error=True,
            )
            QMessageBox.warning(
                self, "Jetson shutdown failed", detail
            )
        else:
            if clean_output:
                self._append_log(clean_output)
            self._append_log(
                "Jetson accepted the shutdown request; SSH going offline is "
                "expected."
            )
            self._mark_robot_connection_unavailable()
            self._wifi_connected = False
            self._ethernet_connected = False
            self._set_route_status(
                "wifi", "disconnected", "Wi-Fi SSH shutting down"
            )
            self._set_route_status(
                "ethernet", "disconnected", "Ethernet SSH shutting down"
            )
            self._set_status("checking", "Jetson shutdown requested")
            self._update_all_session_controls()

        self._update_connection_controls()

    def _shutdown_process_error(self, _process_error) -> None:
        process = self._shutdown_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._shutdown_process = None
        process.deleteLater()
        self._set_status("error", "Could not start shutdown SSH command")
        self._append_log(
            "Could not start the 'ssh' executable for Jetson shutdown.",
            error=True,
        )
        self._update_connection_controls()
        QMessageBox.warning(
            self,
            "Jetson shutdown failed",
            "Could not start the local OpenSSH client. Install "
            "openssh-client and try again.",
        )

    def _start_network_diagnostics(self) -> None:
        if not self._ssh_connected:
            return
        if (
            self._diagnostic_local_process is not None
            or self._diagnostic_remote_process is not None
        ):
            return
        try:
            command = local_diagnostic_probe_command(self._wifi_settings())
        except ValueError as error:
            QMessageBox.warning(self, "Cannot diagnose network", str(error))
            return

        self._diagnostics_log.setPlainText(
            "Running development-machine diagnostics…\n"
        )
        self._log_tabs.setCurrentWidget(self._diagnostics_log)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._local_diagnostics_finished)
        process.errorOccurred.connect(self._local_diagnostics_error)
        self._diagnostic_local_process = process
        self._update_connection_controls()
        process.start("bash", ["-lc", command])

    def _local_diagnostics_finished(self, exit_code: int, _exit_status) -> None:
        process = self._diagnostic_local_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._diagnostic_local_process = None
        self._diagnostic_local_output = output
        self._diagnostics_log.setPlainText(
            "DEVELOPMENT MACHINE\n{}\n\n"
            "Running Jetson diagnostics over {} SSH…\n".format(
                output or "Probe produced no output (exit {}).".format(exit_code),
                self._route_label(self._active_route),
            )
        )

        local_values = parse_probe_output(output)
        local_wifi_ip = local_values.get("SOURCE_IP", "")
        if local_wifi_ip == "unknown":
            local_wifi_ip = ""
        try:
            command = diagnostic_probe_command(local_wifi_ip)
            arguments = remote_command_arguments(
                self._current_settings(), command
            )
        except ValueError as error:
            self._diagnostics_log.appendPlainText(str(error))
            self._update_connection_controls()
            return

        remote_process = QProcess(self)
        remote_process.setProcessChannelMode(QProcess.MergedChannels)
        remote_process.finished.connect(self._remote_diagnostics_finished)
        remote_process.errorOccurred.connect(self._remote_diagnostics_error)
        self._diagnostic_remote_process = remote_process
        remote_process.start("ssh", arguments)

    def _remote_diagnostics_finished(self, exit_code: int, _exit_status) -> None:
        process = self._diagnostic_remote_process
        if process is None:
            return
        remote_output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._diagnostic_remote_process = None

        summary = diagnostic_summary(
            self._diagnostic_local_output,
            remote_output,
            self._route_label(self._active_route),
        )
        report = (
            "DEVELOPMENT MACHINE\n{}\n\n"
            "JETSON NANO\n{}\n\n"
            "DIAGNOSIS\n- {}\n\n"
            "These probes are read-only. A network that blocks ICMP ping may "
            "produce an internet-IP false negative; compare it with DNS and "
            "the printed routes."
        ).format(
            self._diagnostic_local_output or "No output",
            remote_output or "Probe failed with exit {}".format(exit_code),
            "\n- ".join(summary),
        )
        self._diagnostics_log.setPlainText(report)
        self._diagnostic_local_output = ""
        self._update_connection_controls()

    def _local_diagnostics_error(self, _process_error) -> None:
        process = self._diagnostic_local_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._diagnostic_local_process = None
        process.deleteLater()
        self._diagnostics_log.setPlainText(
            "Could not start the local bash diagnostic process."
        )
        self._update_connection_controls()

    def _remote_diagnostics_error(self, _process_error) -> None:
        process = self._diagnostic_remote_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._diagnostic_remote_process = None
        process.deleteLater()
        self._diagnostics_log.appendPlainText(
            "Could not start the SSH diagnostic process."
        )
        self._update_connection_controls()

    def _set_auto_monitoring(self, enabled: bool) -> None:
        if not hasattr(self, "_monitor_timer"):
            return
        if enabled:
            self._monitor_timer.start()
        else:
            self._monitor_timer.stop()
        self._save_settings()

    def _set_status(self, state: str, text: str) -> None:
        colours = {
            "connected": "#1b8a3c",
            "checking": "#d18b00",
            "disconnected": "#c62828",
            "error": "#c62828",
        }
        self._status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._status_text.setText(text)

    def _set_bringup_status(self, state: str, text: str) -> None:
        colours = {
            "running": "#1b8a3c",
            "checking": "#d18b00",
            "stopped": "#777",
            "unknown": "#777",
            "error": "#c62828",
        }
        self._bringup_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._bringup_status_text.setText(text)

    def _session_operation_in_progress(self) -> bool:
        """Return True while any managed remote session is changing state."""
        return any((
            self._bringup_operation_process is not None,
            self._localization_operation_process is not None,
            self._mapping_operation_process is not None,
            self._navigation_operation_process is not None,
        ))

    def _update_bringup_controls(self) -> None:
        busy = self._session_operation_in_progress()
        self._start_bringup_button.setEnabled(
            self._ssh_connected
            and self._bringup_state_known
            and not self._bringup_running
            and not busy
        )
        self._stop_bringup_button.setEnabled(
            self._ssh_connected
            and self._bringup_state_known
            and self._bringup_running
            and not busy
        )

    def _robot_command_settings(self):
        workspace = self._remote_workspace.text().strip()
        domain_id = self._domain_id.value()
        rmw_implementation = self._rmw_implementation.text().strip()
        return workspace, domain_id, rmw_implementation

    def _poll_bringup(self) -> None:
        if not self._ssh_connected:
            return
        if self._bringup_status_process is not None:
            return

        try:
            arguments = remote_command_arguments(
                self._current_settings(), bringup_status_command()
            )
        except ValueError as error:
            self._set_bringup_status("error", "Invalid remote configuration")
            self._append_log(str(error), error=True)
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._bringup_status_finished)
        process.errorOccurred.connect(self._bringup_status_process_error)
        self._bringup_status_process = process
        process.start("ssh", arguments)

    def _bringup_status_finished(self, exit_code: int, _exit_status) -> None:
        process = self._bringup_status_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        process.deleteLater()
        self._bringup_status_process = None

        if exit_code != 0:
            self._bringup_running = False
            self._bringup_state_known = False
            self._set_bringup_status("error", "Bringup status check failed")
            if output.strip():
                self._bringup_log.setPlainText(output.rstrip())
            self._update_bringup_controls()
            self._update_localization_controls()
            self._update_mapping_controls()
            return

        lines = output.splitlines()
        marker = lines[0].strip() if lines else ""
        log_output = "\n".join(lines[1:]).rstrip()
        if marker == RUNNING_MARKER:
            was_running = self._bringup_running
            self._bringup_running = True
            self._bringup_state_known = True
            self._set_bringup_status("running", "Robot bringup running")
            self._observe_launch_state("bringup", True)
            if (
                not was_running
                and self._launch_rviz_with_bringup.isChecked()
                and self._rviz_process is None
            ):
                QTimer.singleShot(0, self._launch_rviz)
        elif marker == STOPPED_MARKER:
            self._bringup_running = False
            self._bringup_state_known = True
            self._set_bringup_status("stopped", "Robot bringup stopped")
            self._observe_launch_state("bringup", False)
        elif marker == TMUX_MISSING_MARKER:
            self._bringup_running = False
            self._bringup_state_known = False
            self._set_bringup_status("error", "tmux missing on Jetson")
            if not log_output:
                log_output = "Install it on the Jetson: sudo apt install tmux"
        else:
            self._bringup_running = False
            self._bringup_state_known = False
            self._set_bringup_status("error", "Unexpected bringup response")
            log_output = output.rstrip()

        if log_output:
            at_bottom = (
                self._bringup_log.verticalScrollBar().value()
                == self._bringup_log.verticalScrollBar().maximum()
            )
            self._bringup_log.setPlainText(log_output)
            if self._follow_bringup_log.isChecked() or at_bottom:
                scrollbar = self._bringup_log.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        elif not self._bringup_running:
            self._bringup_log.setPlainText(
                "No saved bringup log yet. Start robot bringup to create one."
            )
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()

    def _bringup_status_process_error(self, _process_error) -> None:
        process = self._bringup_status_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._bringup_status_process = None
        self._bringup_state_known = False
        process.deleteLater()
        self._set_bringup_status("error", "Could not run SSH status check")
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()

    def _set_localization_status(self, state: str, text: str) -> None:
        colours = {
            "running": "#1b8a3c",
            "checking": "#d18b00",
            "stopped": "#777",
            "unknown": "#777",
            "error": "#c62828",
        }
        self._localization_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._localization_status_text.setText(text)

    def _update_localization_controls(self) -> None:
        busy = self._session_operation_in_progress()
        map_available = bool(self._map_selector.currentText())
        self._refresh_maps_button.setEnabled(
            self._ssh_connected and self._map_list_process is None
        )
        self._map_selector.setEnabled(not self._localization_running and not busy)
        self._start_localization_button.setEnabled(
            self._ssh_connected
            and self._bringup_running
            and self._localization_state_known
            and not self._localization_running
            and self._mapping_state_known
            and not self._mapping_running
            and self._navigation_state_known
            and not self._navigation_running
            and map_available
            and not busy
        )
        self._stop_localization_button.setEnabled(
            self._ssh_connected
            and self._localization_state_known
            and self._localization_running
            and not busy
        )

    def _refresh_maps(self) -> None:
        if not self._ssh_connected or self._map_list_process is not None:
            return
        try:
            command = map_list_command(self._remote_workspace.text().strip())
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot list maps", str(error))
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._map_list_finished)
        process.errorOccurred.connect(self._map_list_process_error)
        self._map_list_process = process
        self._update_localization_controls()
        process.start("ssh", arguments)

    def _map_list_finished(self, exit_code: int, _exit_status) -> None:
        process = self._map_list_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        process.deleteLater()
        self._map_list_process = None

        if exit_code != 0:
            self._append_log(
                "Map discovery failed:\n{}".format(output.rstrip()), error=True
            )
            self._update_localization_controls()
            return

        map_names = sorted({
            line.strip()
            for line in output.splitlines()
            if line.strip().endswith(".yaml")
        })
        current_map = self._map_selector.currentText() or self._saved_map_name
        self._map_selector.clear()
        self._map_selector.addItems(map_names)
        if current_map in map_names:
            self._map_selector.setCurrentText(current_map)
        elif "LakecityFlat4AMap.yaml" in map_names:
            self._map_selector.setCurrentText("LakecityFlat4AMap.yaml")
        self._update_localization_controls()

    def _map_list_process_error(self, _process_error) -> None:
        process = self._map_list_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._map_list_process = None
        process.deleteLater()
        self._append_log("Could not start SSH map discovery.", error=True)
        self._update_localization_controls()

    def _poll_localization(self) -> None:
        if not self._ssh_connected:
            return
        if self._localization_status_process is not None:
            return
        try:
            arguments = remote_command_arguments(
                self._current_settings(), localization_status_command()
            )
        except ValueError as error:
            self._set_localization_status(
                "error", "Invalid localization configuration"
            )
            self._append_log(str(error), error=True)
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._localization_status_finished)
        process.errorOccurred.connect(self._localization_status_process_error)
        self._localization_status_process = process
        process.start("ssh", arguments)

    def _localization_status_finished(self, exit_code: int, _exit_status) -> None:
        process = self._localization_status_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        process.deleteLater()
        self._localization_status_process = None

        if exit_code != 0:
            self._localization_running = False
            self._localization_state_known = False
            self._set_localization_status(
                "error", "Localization status check failed"
            )
            if output.strip():
                self._localization_log.setPlainText(output.rstrip())
            self._sync_tf_probe()
            self._update_localization_controls()
            self._update_bringup_controls()
            self._update_mapping_controls()
            return

        lines = output.splitlines()
        marker = lines[0].strip() if lines else ""
        log_output = "\n".join(lines[1:]).rstrip()
        if marker == LOCALIZATION_RUNNING_MARKER:
            self._localization_running = True
            self._localization_state_known = True
            self._set_localization_status("running", "Localization running")
            self._observe_launch_state("localization", True)
            self._start_tf_probe()
        elif marker == LOCALIZATION_STOPPED_MARKER:
            self._localization_running = False
            self._localization_state_known = True
            self._set_localization_status("stopped", "Localization stopped")
            self._observe_launch_state("localization", False)
            self._sync_tf_probe()
        elif marker == LOCALIZATION_TMUX_MISSING_MARKER:
            self._localization_running = False
            self._localization_state_known = False
            self._set_localization_status("error", "tmux missing on Jetson")
            self._sync_tf_probe()
            if not log_output:
                log_output = "Install it on the Jetson: sudo apt install tmux"
        else:
            self._localization_running = False
            self._localization_state_known = False
            self._set_localization_status(
                "error", "Unexpected localization response"
            )
            self._sync_tf_probe()
            log_output = output.rstrip()

        if log_output:
            at_bottom = (
                self._localization_log.verticalScrollBar().value()
                == self._localization_log.verticalScrollBar().maximum()
            )
            self._localization_log.setPlainText(log_output)
            if self._follow_bringup_log.isChecked() or at_bottom:
                scrollbar = self._localization_log.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        elif not self._localization_running:
            self._localization_log.setPlainText(
                "No saved localization log yet. Select a map and start "
                "localization to create one."
            )
        self._update_localization_controls()
        self._update_bringup_controls()
        self._update_mapping_controls()

    def _localization_status_process_error(self, _process_error) -> None:
        process = self._localization_status_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._localization_status_process = None
        self._localization_state_known = False
        process.deleteLater()
        self._set_localization_status(
            "error", "Could not run localization status check"
        )
        self._sync_tf_probe()
        self._update_localization_controls()
        self._update_bringup_controls()
        self._update_mapping_controls()

    def _start_localization(self) -> None:
        map_filename = self._map_selector.currentText()
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = start_localization_command(
                workspace,
                map_filename,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid localization settings", str(error))
            return
        self._save_settings()
        self._run_localization_operation(
            command, "Starting localization…", action="start"
        )

    def _stop_localization(self) -> None:
        status = (
            "Stopping Nav2 first, then localization…"
            if self._navigation_running
            else "Stopping localization…"
        )
        self._run_localization_operation(
            stop_localization_command(), status, action="stop_stack"
        )

    def _run_localization_operation(
        self, command: str, status_text: str, action: str
    ) -> None:
        if self._localization_operation_process is not None:
            return
        try:
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid SSH settings", str(error))
            return

        process = QProcess(self)
        process.setProperty("action", action)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._localization_operation_finished)
        process.errorOccurred.connect(self._localization_operation_error)
        self._localization_operation_process = process
        if action == "stop_stack":
            self._set_launch_intent("nav2", False)
            self._set_launch_intent("localization", False)
            if self._navigation_running:
                self._navigation_state_known = False
                self._set_navigation_status(
                    "checking", "Stopping Nav2 before localization…"
                )
        else:
            self._set_launch_intent("localization", action == "start")
        self._localization_state_known = False
        self._set_localization_status("checking", status_text)
        self._update_all_session_controls()
        process.start("ssh", arguments)

    def _localization_operation_finished(
        self, exit_code: int, _exit_status
    ) -> None:
        process = self._localization_operation_process
        if process is None:
            return
        action = process.property("action")
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._localization_operation_process = None
        if output:
            self._append_log(output, error=exit_code != 0)
        if exit_code != 0:
            self._clear_launch_intent("localization")
            if action == "stop_stack":
                self._clear_launch_intent("nav2")
            QMessageBox.warning(
                self,
                "Remote localization command failed",
                output or "SSH command exited with code {}.".format(exit_code),
            )
        self._update_all_session_controls()
        QTimer.singleShot(500, self._poll_localization)
        if action == "stop_stack":
            QTimer.singleShot(500, self._poll_navigation)

    def _localization_operation_error(self, _process_error) -> None:
        process = self._localization_operation_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        action = process.property("action")
        self._localization_operation_process = None
        self._clear_launch_intent("localization")
        if action == "stop_stack":
            self._clear_launch_intent("nav2")
        self._localization_state_known = False
        process.deleteLater()
        self._set_localization_status(
            "error", "Could not run remote localization command"
        )
        self._update_all_session_controls()

    def _set_navigation_status(self, state: str, text: str) -> None:
        colours = {
            "running": "#1b8a3c",
            "checking": "#d18b00",
            "stopped": "#777",
            "unknown": "#777",
            "error": "#c62828",
        }
        self._navigation_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._navigation_status_text.setText(text)

    def _set_nav_action_status(self, state: str, text: str) -> None:
        colours = {
            "ready": "#1b8a3c",
            "waiting": "#d18b00",
            "unknown": "#777",
            "error": "#c62828",
        }
        self._nav_action_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._nav_action_status_text.setText(text)

    def _global_tf_ready(self) -> bool:
        return bool(
            self._tf_last_transform_time
            and time.monotonic() - self._tf_last_transform_time <= 3.0
        )

    def _update_navigation_controls(self) -> None:
        busy = self._session_operation_in_progress()
        self._start_navigation_button.setEnabled(
            self._ssh_connected
            and self._bringup_running
            and self._localization_running
            and self._mapping_state_known
            and not self._mapping_running
            and self._navigation_state_known
            and not self._navigation_running
            and self._global_tf_ready()
            and not busy
        )
        self._stop_navigation_button.setEnabled(
            self._ssh_connected
            and self._navigation_state_known
            and self._navigation_running
            and not busy
        )

    def _poll_navigation(self) -> None:
        if not self._ssh_connected:
            return
        if self._navigation_status_process is not None:
            return
        try:
            arguments = remote_command_arguments(
                self._current_settings(), navigation_status_command()
            )
        except ValueError as error:
            self._set_navigation_status("error", "Invalid Nav2 configuration")
            self._append_log(str(error), error=True)
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._navigation_status_finished)
        process.errorOccurred.connect(self._navigation_status_process_error)
        self._navigation_status_process = process
        process.start("ssh", arguments)

    def _navigation_status_finished(self, exit_code: int, _exit_status) -> None:
        process = self._navigation_status_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        process.deleteLater()
        self._navigation_status_process = None

        if exit_code != 0:
            self._navigation_running = False
            self._navigation_state_known = False
            self._set_navigation_status("error", "Nav2 status check failed")
            if output.strip():
                self._navigation_log.setPlainText(output.rstrip())
            self._stop_nav_health_probe()
            self._update_all_session_controls()
            return

        lines = output.splitlines()
        marker = lines[0].strip() if lines else ""
        log_output = "\n".join(lines[1:]).rstrip()
        if marker == NAVIGATION_RUNNING_MARKER:
            was_running = self._navigation_running
            self._navigation_running = True
            self._navigation_state_known = True
            self._set_navigation_status("running", "Nav2 process running")
            self._observe_launch_state("nav2", True)
            self._start_nav_health_probe()
            if (
                not was_running
                and self._launch_rviz_with_bringup.isChecked()
            ):
                QTimer.singleShot(0, self._launch_rviz)
        elif marker == NAVIGATION_STOPPED_MARKER:
            self._navigation_running = False
            self._navigation_state_known = True
            self._set_navigation_status("stopped", "Nav2 stopped")
            self._observe_launch_state("nav2", False)
            self._stop_nav_health_probe()
        elif marker == NAVIGATION_TMUX_MISSING_MARKER:
            self._navigation_running = False
            self._navigation_state_known = False
            self._set_navigation_status("error", "tmux missing on Jetson")
            self._stop_nav_health_probe()
            if not log_output:
                log_output = "Install it on the Jetson: sudo apt install tmux"
        else:
            self._navigation_running = False
            self._navigation_state_known = False
            self._set_navigation_status("error", "Unexpected Nav2 response")
            self._stop_nav_health_probe()
            log_output = output.rstrip()

        if log_output:
            at_bottom = (
                self._navigation_log.verticalScrollBar().value()
                == self._navigation_log.verticalScrollBar().maximum()
            )
            self._navigation_log.setPlainText(log_output)
            if self._follow_bringup_log.isChecked() or at_bottom:
                scrollbar = self._navigation_log.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        elif not self._navigation_running:
            self._navigation_log.setPlainText(
                "No saved Nav2 log yet. Start Nav2 after localization is ready."
            )
        self._update_all_session_controls()

    def _navigation_status_process_error(self, _process_error) -> None:
        process = self._navigation_status_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._navigation_status_process = None
        self._navigation_state_known = False
        process.deleteLater()
        self._set_navigation_status("error", "Could not run Nav2 status check")
        self._stop_nav_health_probe()
        self._update_all_session_controls()

    def _start_navigation(self) -> None:
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = start_navigation_command(
                workspace,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid Nav2 settings", str(error))
            return
        self._run_navigation_operation(
            command, "Starting Nav2 lifecycle nodes…", action="start"
        )

    def _stop_navigation(self) -> None:
        answer = QMessageBox.question(
            self,
            "Stop Nav2?",
            "Any active navigation goal will be canceled. Stop Nav2?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_navigation_operation(
            stop_navigation_command(), "Stopping Nav2…", action="stop"
        )

    def _run_navigation_operation(
        self, command: str, status_text: str, action: str
    ) -> None:
        if self._navigation_operation_process is not None:
            return
        try:
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid SSH settings", str(error))
            return

        process = QProcess(self)
        process.setProperty("action", action)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._navigation_operation_finished)
        process.errorOccurred.connect(self._navigation_operation_error)
        self._navigation_operation_process = process
        self._set_launch_intent("nav2", action in {"start", "restart"})
        self._navigation_state_known = False
        self._set_navigation_status("checking", status_text)
        self._update_all_session_controls()
        process.start("ssh", arguments)

    def _navigation_operation_finished(
        self, exit_code: int, _exit_status
    ) -> None:
        process = self._navigation_operation_process
        if process is None:
            return
        action = process.property("action")
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._navigation_operation_process = None
        if output:
            self._append_log(output, error=exit_code != 0)
        if exit_code != 0:
            self._clear_launch_intent("nav2")
            QMessageBox.warning(
                self,
                "Remote Nav2 command failed",
                output or "SSH command exited with code {}.".format(exit_code),
            )
        elif action == "start" and self._launch_rviz_with_bringup.isChecked():
            self._launch_rviz()
        self._update_all_session_controls()
        QTimer.singleShot(500, self._poll_navigation)

    def _navigation_operation_error(self, _process_error) -> None:
        process = self._navigation_operation_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._navigation_operation_process = None
        self._clear_launch_intent("nav2")
        self._navigation_state_known = False
        process.deleteLater()
        self._set_navigation_status("error", "Could not run remote Nav2 command")
        self._update_all_session_controls()

    def _start_nav_health_probe(self) -> None:
        self._start_system_health_probe()
        self._set_nav_action_status("waiting", "NavigateToPose starting…")

    def _update_nav_health(self) -> None:
        if not self._navigation_running:
            self._set_nav_action_status("unknown", "NavigateToPose unavailable")
            return
        snapshot_fresh = bool(
            self._system_health_last_snapshot_time
            and time.monotonic() - self._system_health_last_snapshot_time <= 6.0
        )
        action_ready = bool(
            snapshot_fresh
            and self._health_snapshot
            and self._health_snapshot.get("actions", {}).get(
                "navigate_to_pose", False
            )
        )
        if action_ready:
            self._set_nav_action_status("ready", "NavigateToPose ready")
        else:
            self._set_nav_action_status("waiting", "NavigateToPose waiting")

    def _stop_nav_health_probe(self) -> None:
        self._nav_action_last_ready_time = 0.0
        self._set_nav_action_status("unknown", "NavigateToPose unavailable")

    def _set_mapping_status(self, state: str, text: str) -> None:
        colours = {
            "running": "#1b8a3c",
            "checking": "#d18b00",
            "stopped": "#777",
            "unknown": "#777",
            "error": "#c62828",
        }
        self._mapping_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._mapping_status_text.setText(text)

    def _update_mapping_controls(self) -> None:
        busy = self._session_operation_in_progress()
        self._start_mapping_button.setEnabled(
            self._ssh_connected
            and self._bringup_running
            and self._mapping_state_known
            and not self._mapping_running
            and self._localization_state_known
            and not self._localization_running
            and self._navigation_state_known
            and not self._navigation_running
            and not busy
        )
        self._stop_mapping_button.setEnabled(
            self._ssh_connected
            and self._mapping_state_known
            and self._mapping_running
            and not busy
        )
        self._save_map_button.setEnabled(
            self._ssh_connected
            and self._mapping_running
            and bool(self._map_name.text().strip())
            and not busy
        )
        self._map_name.setEnabled(not busy)

    def _poll_mapping(self) -> None:
        if not self._ssh_connected:
            return
        if self._mapping_status_process is not None:
            return
        try:
            arguments = remote_command_arguments(
                self._current_settings(), mapping_status_command()
            )
        except ValueError as error:
            self._set_mapping_status("error", "Invalid mapping configuration")
            self._append_log(str(error), error=True)
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._mapping_status_finished)
        process.errorOccurred.connect(self._mapping_status_process_error)
        self._mapping_status_process = process
        process.start("ssh", arguments)

    def _mapping_status_finished(self, exit_code: int, _exit_status) -> None:
        process = self._mapping_status_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        process.deleteLater()
        self._mapping_status_process = None

        if exit_code != 0:
            self._mapping_running = False
            self._mapping_state_known = False
            self._set_mapping_status("error", "Mapping status check failed")
            if output.strip():
                self._mapping_log.setPlainText(output.rstrip())
            self._sync_tf_probe()
            self._update_all_session_controls()
            return

        lines = output.splitlines()
        marker = lines[0].strip() if lines else ""
        log_output = "\n".join(lines[1:]).rstrip()
        if marker == MAPPING_RUNNING_MARKER:
            was_running = self._mapping_running
            self._mapping_running = True
            self._mapping_state_known = True
            self._set_mapping_status("running", "SLAM mapping running")
            self._observe_launch_state("mapping", True)
            self._sync_tf_probe()
            if (
                not was_running
                and self._launch_rviz_with_bringup.isChecked()
            ):
                QTimer.singleShot(0, self._launch_rviz)
        elif marker == MAPPING_STOPPED_MARKER:
            self._mapping_running = False
            self._mapping_state_known = True
            self._set_mapping_status("stopped", "SLAM mapping stopped")
            self._observe_launch_state("mapping", False)
            self._sync_tf_probe()
        elif marker == MAPPING_TMUX_MISSING_MARKER:
            self._mapping_running = False
            self._mapping_state_known = False
            self._set_mapping_status("error", "tmux missing on Jetson")
            self._sync_tf_probe()
            if not log_output:
                log_output = "Install it on the Jetson: sudo apt install tmux"
        else:
            self._mapping_running = False
            self._mapping_state_known = False
            self._set_mapping_status("error", "Unexpected mapping response")
            self._sync_tf_probe()
            log_output = output.rstrip()

        if log_output:
            at_bottom = (
                self._mapping_log.verticalScrollBar().value()
                == self._mapping_log.verticalScrollBar().maximum()
            )
            self._mapping_log.setPlainText(log_output)
            if self._follow_bringup_log.isChecked() or at_bottom:
                scrollbar = self._mapping_log.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        elif not self._mapping_running:
            self._mapping_log.setPlainText(
                "No saved mapping log yet. Start a new map to create one."
            )
        self._update_all_session_controls()

    def _mapping_status_process_error(self, _process_error) -> None:
        process = self._mapping_status_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._mapping_status_process = None
        self._mapping_state_known = False
        process.deleteLater()
        self._set_mapping_status("error", "Could not run mapping status check")
        self._sync_tf_probe()
        self._update_all_session_controls()

    def _start_mapping(self) -> None:
        if self._navigation_running:
            QMessageBox.information(
                self,
                "Nav2 is still running",
                "Stop Nav2 and localization before starting a new map.",
            )
            return
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = start_mapping_command(
                workspace,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid mapping settings", str(error))
            return
        self._run_mapping_operation(
            command, "Starting Slam Toolbox…", action="start"
        )

    def _stop_mapping(self) -> None:
        answer = QMessageBox.question(
            self,
            "Stop mapping?",
            "Any unsaved map changes will be lost. Save the map first if you "
            "want to keep this mapping session. Stop anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_mapping_operation(
            stop_mapping_command(), "Stopping Slam Toolbox…", action="stop"
        )

    def _save_map(self) -> None:
        map_name = self._map_name.text().strip()
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = save_map_command(
                workspace,
                map_name,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid map name", str(error))
            return

        answer = QMessageBox.question(
            self,
            "Save current map?",
            "Save the current SLAM map as {}.yaml and {}.pgm?".format(
                map_name, map_name
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self._save_settings()
        self._run_mapping_operation(command, "Saving map…", action="save")

    def _run_mapping_operation(
        self, command: str, status_text: str, action: str
    ) -> None:
        if self._mapping_operation_process is not None:
            return
        try:
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid SSH settings", str(error))
            return

        process = QProcess(self)
        process.setProperty("action", action)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._mapping_operation_finished)
        process.errorOccurred.connect(self._mapping_operation_error)
        self._mapping_operation_process = process
        if action in {"start", "stop"}:
            self._set_launch_intent("mapping", action == "start")
        self._mapping_state_known = False
        self._set_mapping_status("checking", status_text)
        self._update_all_session_controls()
        process.start("ssh", arguments)

    def _mapping_operation_finished(self, exit_code: int, _exit_status) -> None:
        process = self._mapping_operation_process
        if process is None:
            return
        action = process.property("action")
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._mapping_operation_process = None
        if output:
            self._append_log(output, error=exit_code != 0)
        if exit_code != 0:
            if action in {"start", "stop"}:
                self._clear_launch_intent("mapping")
            QMessageBox.warning(
                self,
                "Remote mapping command failed",
                output or "SSH command exited with code {}.".format(exit_code),
            )
        elif action == "start" and self._launch_rviz_with_bringup.isChecked():
            self._launch_rviz()
        elif action == "save":
            QMessageBox.information(
                self,
                "Map saved",
                "The map was saved in amr_slam/maps on the Jetson.",
            )
            self._refresh_maps()
        self._update_all_session_controls()
        QTimer.singleShot(500, self._poll_mapping)

    def _mapping_operation_error(self, _process_error) -> None:
        process = self._mapping_operation_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        action = process.property("action")
        self._mapping_operation_process = None
        if action in {"start", "stop"}:
            self._clear_launch_intent("mapping")
        self._mapping_state_known = False
        process.deleteLater()
        self._set_mapping_status("error", "Could not run remote mapping command")
        self._update_all_session_controls()

    def _update_all_session_controls(self) -> None:
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()
        self._update_navigation_controls()
        self._update_parameter_controls()

    def _sync_tf_probe(self) -> None:
        if self._localization_running or self._mapping_running:
            self._start_tf_probe()
        else:
            self._stop_tf_probe()

    def _start_tf_probe(self) -> None:
        self._start_system_health_probe()
        self._set_tf_status("waiting", "Waiting for map → base_link")

    def _update_tf_health(self) -> None:
        if not (self._localization_running or self._mapping_running):
            self._set_tf_status("unknown", "map → base_link unavailable")
            return
        snapshot_fresh = bool(
            self._system_health_last_snapshot_time
            and time.monotonic() - self._system_health_last_snapshot_time <= 6.0
        )
        map_base = (
            self._health_snapshot.get("transforms", {}).get("map_base", {})
            if snapshot_fresh and self._health_snapshot
            else {}
        )
        if map_base.get("available"):
            self._tf_last_transform_time = time.monotonic()
            self._set_tf_status("ready", "map → base_link available")
        else:
            self._tf_last_transform_time = 0.0
            self._set_tf_status("waiting", "Waiting for map → base_link")

    def _set_tf_status(self, state: str, text: str) -> None:
        colours = {
            "ready": "#1b8a3c",
            "waiting": "#d18b00",
            "unknown": "#777",
            "error": "#c62828",
        }
        self._tf_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colours.get(state, "#777"))
        )
        self._tf_status_text.setText("Global TF: {}".format(text))
        if hasattr(self, "_start_navigation_button"):
            self._update_navigation_controls()

    def _stop_tf_probe(self) -> None:
        self._tf_last_transform_time = 0.0
        self._set_tf_status("unknown", "map → base_link unavailable")

    def _start_robot_bringup(self) -> None:
        if self._show_start_confirmation.isChecked():
            answer = QMessageBox.question(
                self,
                "Start physical robot?",
                "This starts the motor driver, lidar, camera, joystick, twist "
                "mux, and LCD on the Jetson. The wheels can move if a joystick "
                "command is received. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = start_bringup_command(
                workspace,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid robot settings", str(error))
            return
        self._save_settings()
        self._run_bringup_operation(
            command, "Starting robot bringup…", action="start"
        )

    def _stop_robot_bringup(self) -> None:
        dependents = []
        if self._navigation_running:
            dependents.append("Nav2")
        if self._localization_running:
            dependents.append("localization")
        if self._mapping_running:
            dependents.append("SLAM mapping (unsaved map changes will be lost)")
        dependency_text = ""
        if dependents:
            dependency_text = (
                "\n\nThe app will first stop: {}."
                .format(", ".join(dependents))
            )
        answer = QMessageBox.question(
            self,
            "Stop physical robot bringup?",
            "This will stop dependent processes in safe reverse-startup order, "
            "then stop physical robot bringup.{} Continue?".format(
                dependency_text
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_bringup_operation(
            stop_bringup_command(),
            "Stopping dependent sessions, then robot bringup…",
            action="stop_stack",
        )

    def _run_bringup_operation(
        self, command: str, status_text: str, action: str
    ) -> None:
        if self._bringup_operation_process is not None:
            return
        try:
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid SSH settings", str(error))
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.finished.connect(self._bringup_operation_finished)
        process.errorOccurred.connect(self._bringup_operation_error)
        self._bringup_operation_process = process
        self._bringup_operation_action = action
        if action == "stop_stack":
            for subsystem in ("nav2", "localization", "mapping", "bringup"):
                self._set_launch_intent(subsystem, False)
            if self._navigation_running:
                self._navigation_state_known = False
                self._set_navigation_status("checking", "Stopping Nav2…")
            if self._localization_running:
                self._localization_state_known = False
                self._set_localization_status(
                    "checking", "Waiting to stop localization…"
                )
            if self._mapping_running:
                self._mapping_state_known = False
                self._set_mapping_status("checking", "Stopping SLAM mapping…")
        else:
            self._set_launch_intent("bringup", action in {"start", "restart"})
        self._bringup_state_known = False
        self._set_bringup_status("checking", status_text)
        self._update_all_session_controls()
        process.start("ssh", arguments)

    def _bringup_operation_finished(self, exit_code: int, _exit_status) -> None:
        process = self._bringup_operation_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        action = self._bringup_operation_action
        process.deleteLater()
        self._bringup_operation_process = None
        self._bringup_operation_action = ""

        if output:
            self._append_log(output, error=exit_code != 0)
        if exit_code != 0:
            affected = (
                ("nav2", "localization", "mapping", "bringup")
                if action == "stop_stack"
                else ("bringup",)
            )
            for subsystem in affected:
                self._clear_launch_intent(subsystem)
            QMessageBox.warning(
                self,
                "Remote bringup command failed",
                output or "SSH command exited with code {}.".format(exit_code),
            )
        elif action == "start" and self._launch_rviz_with_bringup.isChecked():
            self._launch_rviz()
        self._update_all_session_controls()
        QTimer.singleShot(500, self._poll_bringup)
        if action == "stop_stack":
            QTimer.singleShot(500, self._poll_navigation)
            QTimer.singleShot(500, self._poll_localization)
            QTimer.singleShot(500, self._poll_mapping)

    def _bringup_operation_error(self, _process_error) -> None:
        process = self._bringup_operation_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        action = self._bringup_operation_action
        self._bringup_operation_process = None
        affected = (
            ("nav2", "localization", "mapping", "bringup")
            if action == "stop_stack"
            else ("bringup",)
        )
        for subsystem in affected:
            self._clear_launch_intent(subsystem)
        self._bringup_operation_action = ""
        process.deleteLater()
        self._set_bringup_status("error", "Could not run remote command")
        self._update_all_session_controls()

    def _set_rviz_status(self, running: bool, text: str) -> None:
        colour = "#1b8a3c" if running else "#777"
        self._rviz_status_dot.setStyleSheet(
            "font-size: 22px; color: {};".format(colour)
        )
        self._rviz_status_text.setText(text)

    def _open_vscode(self) -> None:
        try:
            arguments = vscode_remote_arguments(
                self._current_settings(),
                self._remote_workspace.text().strip(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot open VS Code", str(error))
            return

        self._save_settings()
        result = QProcess.startDetached("code", arguments)
        started = result[0] if isinstance(result, tuple) else result
        if not started:
            QMessageBox.warning(
                self,
                "Cannot open VS Code",
                "The 'code' command could not be started. Install VS Code, "
                "enable its shell command, and install Remote - SSH.",
            )
            return

        self._append_log(
            "Opening the Jetson repository in VS Code Remote-SSH. "
            "Codex is configured to focus when the remote window loads."
        )

    def _update_rviz_controls(self) -> None:
        running = self._rviz_process is not None
        self._launch_rviz_button.setEnabled(not running)
        self._close_rviz_button.setEnabled(running)

    def _launch_rviz(self, _checked=False) -> None:
        if self._rviz_process is not None:
            return
        try:
            command = rviz_launch_command(
                self._local_workspace.text().strip(),
                domain_id=self._domain_id.value(),
                rmw_implementation=self._rmw_implementation.text().strip(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot launch RViz", str(error))
            return

        self._save_settings()
        self._rviz_log.clear()
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_rviz_output)
        process.finished.connect(self._rviz_finished)
        process.errorOccurred.connect(self._rviz_process_error)
        self._rviz_process = process
        self._set_rviz_status(True, "RViz unified view starting…")
        self._update_rviz_controls()
        process.start("bash", ["-lc", command])

    def _read_rviz_output(self) -> None:
        if self._rviz_process is None:
            return
        output = bytes(self._rviz_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if output:
            cursor = self._rviz_log.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertText(output)
            self._rviz_log.setTextCursor(cursor)
            self._rviz_log.ensureCursorVisible()
        if self._rviz_process.state() == QProcess.Running:
            self._set_rviz_status(True, "RViz unified view running")

    def _rviz_finished(self, exit_code: int, _exit_status) -> None:
        process = self._rviz_process
        if process is None:
            return
        self._read_rviz_output()
        process.deleteLater()
        self._rviz_process = None
        self._set_rviz_status(False, "RViz stopped")
        self._update_rviz_controls()
        if exit_code != 0:
            self._log_tabs.setCurrentWidget(self._rviz_log)

    def _rviz_process_error(self, _process_error) -> None:
        process = self._rviz_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._rviz_process = None
        process.deleteLater()
        self._set_rviz_status(False, "RViz failed to start")
        self._rviz_log.setPlainText("Could not start the local bash process.")
        self._update_rviz_controls()

    def _close_rviz(self) -> None:
        if self._rviz_process is None:
            return
        self._rviz_process.terminate()
        if not self._rviz_process.waitForFinished(3000):
            self._rviz_process.kill()

    def _append_log(self, message: str, error: bool = False) -> None:
        cursor = self._connection_log.textCursor()
        cursor.movePosition(cursor.End)
        char_format = QTextCharFormat()
        if error:
            char_format.setForeground(QColor("#c62828"))
        cursor.insertText(message + "\n", char_format)
        self._connection_log.setTextCursor(cursor)
        self._connection_log.ensureCursorVisible()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API name)
        if not self._allow_close and self._parameter_document is not None:
            for identifier in list(self._parameter_value_edits):
                self._parameter_value_edited(identifier)
            if self._parameter_invalid_edits:
                answer = QMessageBox.warning(
                    self,
                    "Invalid staged parameter values",
                    "Some red values cannot be saved. Discard those invalid "
                    "edits and continue closing?",
                    QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Cancel,
                )
                if answer != QMessageBox.Discard:
                    event.ignore()
                    return
                for identifier in self._parameter_invalid_edits:
                    entry = self._parameter_document.entry(identifier)
                    self._parameter_value_edits[identifier].setText(
                        entry.display_text
                    )
                self._parameter_invalid_edits.clear()
            if self._parameter_document.dirty:
                if self._parameter_write_process is not None:
                    self._close_after_parameter_save = True
                    self._parameter_status.setText(
                        "Waiting for the YAML save before closing…"
                    )
                    event.ignore()
                    return
                answer = QMessageBox.warning(
                    self,
                    "Unsaved parameter tuning",
                    "Save staged changes to {} before closing? Discard leaves "
                    "any values already sent live active only until that "
                    "process restarts.".format(self._parameter_current_file),
                    QMessageBox.Save
                    | QMessageBox.Discard
                    | QMessageBox.Cancel,
                    QMessageBox.Save,
                )
                if answer == QMessageBox.Cancel:
                    event.ignore()
                    return
                if answer == QMessageBox.Save:
                    if not self._ssh_connected:
                        QMessageBox.warning(
                            self,
                            "Cannot save while disconnected",
                            "Reconnect to the Jetson to save the YAML, or "
                            "select Discard when closing.",
                        )
                        event.ignore()
                        return
                    self._close_after_parameter_save = True
                    self._save_parameter_yaml()
                    event.ignore()
                    return
        self._save_settings()
        if self._ssh_process is not None:
            self._ssh_process.kill()
            self._ssh_process.waitForFinished(1000)
        if self._bringup_status_process is not None:
            self._bringup_status_process.kill()
            self._bringup_status_process.waitForFinished(1000)
        if self._bringup_operation_process is not None:
            self._bringup_operation_process.kill()
            self._bringup_operation_process.waitForFinished(1000)
        if self._map_list_process is not None:
            self._map_list_process.kill()
            self._map_list_process.waitForFinished(1000)
        if self._localization_status_process is not None:
            self._localization_status_process.kill()
            self._localization_status_process.waitForFinished(1000)
        if self._localization_operation_process is not None:
            self._localization_operation_process.kill()
            self._localization_operation_process.waitForFinished(1000)
        if self._mapping_status_process is not None:
            self._mapping_status_process.kill()
            self._mapping_status_process.waitForFinished(1000)
        if self._mapping_operation_process is not None:
            self._mapping_operation_process.kill()
            self._mapping_operation_process.waitForFinished(1000)
        if self._navigation_status_process is not None:
            self._navigation_status_process.kill()
            self._navigation_status_process.waitForFinished(1000)
        if self._navigation_operation_process is not None:
            self._navigation_operation_process.kill()
            self._navigation_operation_process.waitForFinished(1000)
        if self._diagnostic_local_process is not None:
            self._diagnostic_local_process.kill()
            self._diagnostic_local_process.waitForFinished(1000)
        if self._diagnostic_remote_process is not None:
            self._diagnostic_remote_process.kill()
            self._diagnostic_remote_process.waitForFinished(1000)
        if self._shutdown_process is not None:
            self._shutdown_process.kill()
            self._shutdown_process.waitForFinished(1000)
        for process in (
            self._parameter_file_list_process,
            self._parameter_read_process,
            self._parameter_write_process,
            self._parameter_live_process,
        ):
            if process is not None:
                process.kill()
                process.waitForFinished(1000)
        self._stop_system_health_probe()
        self._stop_nav_health_probe()
        self._stop_tf_probe()
        if self._rviz_process is not None:
            self._close_rviz()
        event.accept()


def main() -> int:
    """Launch the desktop GUI."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    app.setApplicationName("AMR Operator")
    app.setOrganizationName("AMR")
    app.setDesktopFileName("amr-operator-gui")
    app.setWindowIcon(QIcon(str(APPLICATION_ICON_PATH)))
    window = OperatorWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
