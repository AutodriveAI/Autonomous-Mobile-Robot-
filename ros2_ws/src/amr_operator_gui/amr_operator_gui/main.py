"""Entry point for the AMR operator GUI."""

import sys
import time
from pathlib import Path

from PyQt5.QtCore import QProcess, QSettings, QTimer, Qt
from PyQt5.QtGui import QColor, QIcon, QTextCharFormat
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from amr_operator_gui.local_rviz import (
    DEFAULT_LOCAL_WORKSPACE,
    rviz_launch_command,
)
from amr_operator_gui.local_vscode import vscode_remote_arguments
from amr_operator_gui.nav2_health_probe import (
    READY_MARKER as NAV2_ACTION_READY_MARKER,
    WAITING_MARKER as NAV2_ACTION_WAITING_MARKER,
)
from amr_operator_gui.remote_bringup import (
    DEFAULT_REMOTE_WORKSPACE,
    RUNNING_MARKER,
    STOPPED_MARKER,
    TMUX_MISSING_MARKER,
    bringup_status_command,
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
    tf_probe_command,
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
from amr_operator_gui.remote_navigation import (
    NAVIGATION_RUNNING_MARKER,
    NAVIGATION_STOPPED_MARKER,
    TMUX_MISSING_MARKER as NAVIGATION_TMUX_MISSING_MARKER,
    navigation_health_probe_command,
    navigation_status_command,
    start_navigation_command,
    stop_navigation_command,
)
from amr_operator_gui.ssh_connection import (
    SshSettings,
    connection_test_arguments,
    remote_command_arguments,
)


DARK_STYLESHEET = """
QWidget {
    background-color: #20252b;
    color: #e4e9ee;
    font-size: 10pt;
}
QMainWindow, QMessageBox { background-color: #20252b; }
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
    background-color: #14181d;
    color: #edf2f7;
    border: 1px solid #46515d;
    border-radius: 4px;
    padding: 4px;
    selection-background-color: #315f82;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #65a6d8;
}
QPushButton {
    background-color: #3a444f;
    color: #f4f7fa;
    border: 1px solid #566473;
    border-radius: 5px;
    padding: 6px 11px;
}
QPushButton:hover { background-color: #485563; }
QPushButton:pressed { background-color: #2b333c; }
QPushButton:disabled {
    background-color: #2a3036;
    color: #707b85;
    border-color: #343c44;
}
QPushButton[role="start"] {
    background-color: #286044;
    border-color: #3d8a64;
}
QPushButton[role="start"]:hover { background-color: #347a57; }
QPushButton[role="stop"] {
    background-color: #713333;
    border-color: #a44c4c;
}
QPushButton[role="stop"]:hover { background-color: #8c4040; }
QPushButton[role="action"] {
    background-color: #285780;
    border-color: #4383b8;
}
QPushButton[role="action"]:hover { background-color: #326d9f; }
QTabWidget::pane { border: 1px solid #46515d; }
QTabBar::tab {
    background-color: #2a3138;
    color: #bdc7d0;
    padding: 7px 13px;
    border: 1px solid #3d4650;
}
QTabBar::tab:selected { background-color: #3b4651; color: #ffffff; }
QToolButton { color: #dce4eb; padding: 3px; }
QToolTip {
    background-color: #101419;
    color: #f0f4f8;
    border: 1px solid #637180;
    padding: 4px;
}
QScrollBar:vertical { background: #181c21; width: 12px; }
QScrollBar::handle:vertical { background: #4a5662; min-height: 24px; }
"""

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
        self.resize(1080, 760)

        self._settings = QSettings("AMR", "AMR Operator")
        self._ssh_process = None
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
        self._check_was_manual = False
        self._ssh_connected = False
        self._bringup_running = False
        self._bringup_state_known = False
        self._localization_running = False
        self._localization_state_known = False
        self._saved_map_name = "LakecityFlat4AMap.yaml"

        self._build_ui()
        self._load_settings()

        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(self.MONITOR_INTERVAL_MS)
        self._monitor_timer.timeout.connect(self._automatic_connection_test)
        self._auto_monitor.toggled.connect(self._set_auto_monitoring)
        self._set_auto_monitoring(self._auto_monitor.isChecked())

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
        self._tf_health_timer.start()

        QTimer.singleShot(
            400, lambda: self._start_connection_test(manual=False)
        )

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        title = QLabel("Autonomous Mobile Robot")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)

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
        connection_layout.addRow("Host", self._host)

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

        self._test_button = QPushButton("Test SSH connection")
        self._test_button.setProperty("role", "action")
        self._test_button.clicked.connect(self._manual_connection_test)
        status_row.addWidget(self._test_button)
        layout.addLayout(status_row)

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

        self._connection_log = QPlainTextEdit()
        self._connection_log.setReadOnly(True)
        self._connection_log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._connection_log.document().setMaximumBlockCount(500)
        self._log_tabs.addTab(self._connection_log, "Connection")

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

    def _load_settings(self) -> None:
        self._host.setText(
            self._settings.value("ssh/host", "10.206.146.161", type=str)
        )
        self._username.setText(
            self._settings.value("ssh/username", "jetson", type=str)
        )
        self._port.setValue(self._settings.value("ssh/port", 22, type=int))
        self._identity_file.setText(
            self._settings.value("ssh/identity_file", "", type=str)
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

    def _save_settings(self) -> None:
        self._settings.setValue("ssh/host", self._host.text().strip())
        self._settings.setValue("ssh/username", self._username.text().strip())
        self._settings.setValue("ssh/port", self._port.value())
        self._settings.setValue(
            "ssh/identity_file", self._identity_file.text().strip()
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
        self._settings.sync()

    def _current_settings(self) -> SshSettings:
        return SshSettings(
            host=self._host.text().strip(),
            username=self._username.text().strip(),
            port=self._port.value(),
            identity_file=self._identity_file.text().strip(),
        )

    def _manual_connection_test(self) -> None:
        self._start_connection_test(manual=True)

    def _automatic_connection_test(self) -> None:
        if self._auto_monitor.isChecked():
            self._start_connection_test(manual=False)

    def _start_connection_test(self, manual: bool) -> None:
        if self._ssh_process is not None:
            return

        try:
            settings = self._current_settings()
            arguments = connection_test_arguments(settings)
        except ValueError as error:
            self._set_status("error", "Invalid connection settings")
            self._append_log(str(error), error=True)
            return

        self._save_settings()
        self._check_was_manual = manual
        self._set_status("checking", "Checking {}…".format(settings.target))
        if manual:
            self._append_log("Testing SSH connection to {}".format(settings.target))

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_process_output)
        process.finished.connect(self._connection_test_finished)
        process.errorOccurred.connect(self._connection_process_error)
        self._ssh_process = process
        self._test_button.setEnabled(False)
        process.start("ssh", arguments)

    def _read_process_output(self) -> None:
        if self._ssh_process is None:
            return
        output = bytes(self._ssh_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if output.strip():
            self._append_log(output.rstrip())

    def _connection_test_finished(self, exit_code: int, _exit_status) -> None:
        process = self._ssh_process
        if process is not None:
            self._read_process_output()
            process.deleteLater()
        self._ssh_process = None
        self._test_button.setEnabled(True)

        if exit_code == 0:
            self._ssh_connected = True
            self._set_status("connected", "SSH connected")
            if self._check_was_manual:
                self._append_log("Connection test passed.")
            self._poll_bringup()
            self._poll_localization()
            self._poll_mapping()
            self._poll_navigation()
            if self._map_selector.count() == 0:
                self._refresh_maps()
        else:
            self._ssh_connected = False
            self._bringup_running = False
            self._localization_running = False
            self._mapping_running = False
            self._navigation_running = False
            self._bringup_state_known = False
            self._localization_state_known = False
            self._mapping_state_known = False
            self._navigation_state_known = False
            self._set_status("disconnected", "SSH unavailable")
            self._set_bringup_status("unknown", "Bringup status unavailable")
            self._set_localization_status(
                "unknown", "Localization status unavailable"
            )
            self._set_mapping_status("unknown", "Mapping status unavailable")
            self._set_navigation_status("unknown", "Nav2 status unavailable")
            self._stop_tf_probe()
            self._stop_nav_health_probe()
            if self._check_was_manual:
                self._append_log(
                    "Connection test failed with exit code {}.".format(exit_code),
                    error=True,
                )
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()
        self._update_navigation_controls()

    def _connection_process_error(self, _process_error) -> None:
        if self._ssh_process is None:
            return
        if self._ssh_process.error() == QProcess.FailedToStart:
            process = self._ssh_process
            self._ssh_process = None
            self._ssh_connected = False
            self._bringup_running = False
            self._localization_running = False
            self._mapping_running = False
            self._navigation_running = False
            self._bringup_state_known = False
            self._localization_state_known = False
            self._mapping_state_known = False
            self._navigation_state_known = False
            self._test_button.setEnabled(True)
            self._set_status("error", "OpenSSH client not found")
            self._set_bringup_status("unknown", "Bringup status unavailable")
            self._set_localization_status(
                "unknown", "Localization status unavailable"
            )
            self._set_mapping_status("unknown", "Mapping status unavailable")
            self._set_navigation_status("unknown", "Nav2 status unavailable")
            self._stop_tf_probe()
            self._stop_nav_health_probe()
            self._append_log(
                "Could not start the 'ssh' executable. Install openssh-client.",
                error=True,
            )
            process.deleteLater()
            self._update_bringup_controls()
            self._update_localization_controls()
            self._update_mapping_controls()
            self._update_navigation_controls()

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

    def _update_bringup_controls(self) -> None:
        busy = self._bringup_operation_process is not None
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
            and self._localization_state_known
            and not self._localization_running
            and self._mapping_state_known
            and not self._mapping_running
            and self._navigation_state_known
            and not self._navigation_running
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
        busy = self._localization_operation_process is not None
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
            and not self._navigation_running
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
            self._start_tf_probe()
        elif marker == LOCALIZATION_STOPPED_MARKER:
            self._localization_running = False
            self._localization_state_known = True
            self._set_localization_status("stopped", "Localization stopped")
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
        if self._navigation_running:
            QMessageBox.information(
                self,
                "Nav2 is still running",
                "Stop Nav2 before stopping localization.",
            )
            return
        self._run_localization_operation(
            stop_localization_command(), "Stopping localization…", action="stop"
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
        self._localization_state_known = False
        self._set_localization_status("checking", status_text)
        self._update_localization_controls()
        self._update_bringup_controls()
        self._update_mapping_controls()
        process.start("ssh", arguments)

    def _localization_operation_finished(
        self, exit_code: int, _exit_status
    ) -> None:
        process = self._localization_operation_process
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        ).strip()
        process.deleteLater()
        self._localization_operation_process = None
        if output:
            self._append_log(output, error=exit_code != 0)
        if exit_code != 0:
            QMessageBox.warning(
                self,
                "Remote localization command failed",
                output or "SSH command exited with code {}.".format(exit_code),
            )
        self._update_localization_controls()
        self._update_bringup_controls()
        self._update_mapping_controls()
        QTimer.singleShot(500, self._poll_localization)

    def _localization_operation_error(self, _process_error) -> None:
        process = self._localization_operation_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._localization_operation_process = None
        self._localization_state_known = False
        process.deleteLater()
        self._set_localization_status(
            "error", "Could not run remote localization command"
        )
        self._update_localization_controls()
        self._update_bringup_controls()
        self._update_mapping_controls()

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
        busy = self._navigation_operation_process is not None
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
        self._navigation_state_known = False
        process.deleteLater()
        self._set_navigation_status("error", "Could not run remote Nav2 command")
        self._update_all_session_controls()

    def _start_nav_health_probe(self) -> None:
        if self._nav_health_process is not None or not self._navigation_running:
            return
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = navigation_health_probe_command(
                workspace,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            self._set_nav_action_status("error", str(error))
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_nav_health_output)
        process.finished.connect(self._nav_health_finished)
        process.errorOccurred.connect(self._nav_health_process_error)
        self._nav_health_buffer = ""
        self._nav_action_last_ready_time = 0.0
        self._nav_health_process = process
        self._set_nav_action_status("waiting", "NavigateToPose starting…")
        process.start("ssh", arguments)

    def _read_nav_health_output(self) -> None:
        if self._nav_health_process is None:
            return
        output = bytes(self._nav_health_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._nav_health_buffer = (self._nav_health_buffer + output)[-4096:]
        if NAV2_ACTION_READY_MARKER in output:
            self._nav_action_last_ready_time = time.monotonic()
            self._set_nav_action_status("ready", "NavigateToPose ready")
        elif NAV2_ACTION_WAITING_MARKER in output:
            self._nav_action_last_ready_time = 0.0
            self._set_nav_action_status("waiting", "NavigateToPose waiting")

    def _update_nav_health(self) -> None:
        if not self._navigation_running:
            self._set_nav_action_status("unknown", "NavigateToPose unavailable")
            return
        if self._nav_health_process is None:
            self._start_nav_health_probe()
            return
        if (
            self._nav_action_last_ready_time
            and time.monotonic() - self._nav_action_last_ready_time <= 2.5
        ):
            self._set_nav_action_status("ready", "NavigateToPose ready")
        else:
            self._set_nav_action_status("waiting", "NavigateToPose waiting")

    def _stop_nav_health_probe(self) -> None:
        process = self._nav_health_process
        self._nav_health_process = None
        self._nav_health_buffer = ""
        self._nav_action_last_ready_time = 0.0
        if process is not None:
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()
        self._set_nav_action_status("unknown", "NavigateToPose unavailable")

    def _nav_health_finished(self, _exit_code: int, _exit_status) -> None:
        process = self._nav_health_process
        if process is None:
            return
        self._read_nav_health_output()
        process.deleteLater()
        self._nav_health_process = None
        if self._navigation_running:
            self._set_nav_action_status("waiting", "Action probe reconnecting…")

    def _nav_health_process_error(self, _process_error) -> None:
        process = self._nav_health_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._nav_health_process = None
        process.deleteLater()
        self._set_nav_action_status("error", "Could not start action probe")

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
        busy = self._mapping_operation_process is not None
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
        self._mapping_operation_process = None
        self._mapping_state_known = False
        process.deleteLater()
        self._set_mapping_status("error", "Could not run remote mapping command")
        self._update_all_session_controls()

    def _update_all_session_controls(self) -> None:
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()
        self._update_navigation_controls()

    def _sync_tf_probe(self) -> None:
        if self._localization_running or self._mapping_running:
            self._start_tf_probe()
        else:
            self._stop_tf_probe()

    def _start_tf_probe(self) -> None:
        if self._tf_probe_process is not None or not (
            self._localization_running or self._mapping_running
        ):
            return
        workspace, domain_id, rmw_implementation = self._robot_command_settings()
        try:
            command = tf_probe_command(
                workspace,
                domain_id=domain_id,
                rmw_implementation=rmw_implementation,
            )
            arguments = remote_command_arguments(self._current_settings(), command)
        except ValueError as error:
            self._set_tf_status("error", str(error))
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_tf_probe_output)
        process.finished.connect(self._tf_probe_finished)
        process.errorOccurred.connect(self._tf_probe_process_error)
        self._tf_probe_buffer = ""
        self._tf_last_transform_time = 0.0
        self._tf_probe_process = process
        self._set_tf_status("waiting", "Waiting for map → base_link")
        process.start("ssh", arguments)

    def _read_tf_probe_output(self) -> None:
        if self._tf_probe_process is None:
            return
        output = bytes(self._tf_probe_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._tf_probe_buffer = (self._tf_probe_buffer + output)[-8192:]
        if "Translation:" in output or "Translation:" in self._tf_probe_buffer:
            self._tf_last_transform_time = time.monotonic()
            self._tf_probe_buffer = self._tf_probe_buffer[-512:]
            self._set_tf_status("ready", "map → base_link available")

    def _update_tf_health(self) -> None:
        if not (self._localization_running or self._mapping_running):
            self._set_tf_status("unknown", "map → base_link unavailable")
            return
        if self._tf_probe_process is None:
            self._start_tf_probe()
            return
        if (
            self._tf_last_transform_time
            and time.monotonic() - self._tf_last_transform_time <= 3.0
        ):
            self._set_tf_status("ready", "map → base_link available")
        else:
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
        process = self._tf_probe_process
        self._tf_probe_process = None
        self._tf_probe_buffer = ""
        self._tf_last_transform_time = 0.0
        if process is not None:
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()
        self._set_tf_status("unknown", "map → base_link unavailable")

    def _tf_probe_finished(self, _exit_code: int, _exit_status) -> None:
        process = self._tf_probe_process
        if process is None:
            return
        self._read_tf_probe_output()
        process.deleteLater()
        self._tf_probe_process = None
        if self._localization_running or self._mapping_running:
            self._set_tf_status("waiting", "TF probe reconnecting…")

    def _tf_probe_process_error(self, _process_error) -> None:
        process = self._tf_probe_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._tf_probe_process = None
        process.deleteLater()
        self._set_tf_status("error", "Could not start TF probe")

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
        if self._navigation_running:
            QMessageBox.information(
                self,
                "Nav2 is still running",
                "Stop Nav2 before stopping localization or physical bringup.",
            )
            return
        if self._localization_running:
            QMessageBox.information(
                self,
                "Localization is still running",
                "Stop localization before stopping physical robot bringup.",
            )
            return
        if self._mapping_running:
            QMessageBox.information(
                self,
                "Mapping is still running",
                "Save or discard the current map, then stop mapping before "
                "stopping physical robot bringup.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Stop physical robot bringup?",
            "This sends Ctrl-C to the remote ROS launch process. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_bringup_operation(
            stop_bringup_command(), "Stopping robot bringup…", action="stop"
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
        self._bringup_state_known = False
        self._set_bringup_status("checking", status_text)
        self._update_bringup_controls()
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
            QMessageBox.warning(
                self,
                "Remote bringup command failed",
                output or "SSH command exited with code {}.".format(exit_code),
            )
        elif action == "start" and self._launch_rviz_with_bringup.isChecked():
            self._launch_rviz()
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()
        QTimer.singleShot(500, self._poll_bringup)

    def _bringup_operation_error(self, _process_error) -> None:
        process = self._bringup_operation_process
        if process is None or process.error() != QProcess.FailedToStart:
            return
        self._bringup_operation_process = None
        process.deleteLater()
        self._set_bringup_status("error", "Could not run remote command")
        self._update_bringup_controls()
        self._update_localization_controls()
        self._update_mapping_controls()

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
