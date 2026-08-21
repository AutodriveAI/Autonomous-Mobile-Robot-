"""Tests for remote physical-bringup command construction."""

import pytest

from amr_operator_gui.remote_bringup import (
    RUNNING_MARKER,
    STOPPED_MARKER,
    TMUX_MISSING_MARKER,
    bringup_status_command,
    robot_bringup_launch_command,
    start_bringup_command,
    stop_bringup_command,
)


def test_hardware_launch_keeps_localization_and_nav2_off():
    command = robot_bringup_launch_command("/home/jetson/robot/ros2_ws")

    assert "start_localisation:=false" in command
    assert "start_nav2:=false" in command
    assert "start_joy_teleop:=true" in command
    assert "start_keyboard_teleop:=false" in command
    assert "bypass_twist_mux:=false" in command
    assert "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" in command


def test_workspace_path_is_shell_quoted():
    command = robot_bringup_launch_command("/home/jetson/robot workspace/ros2_ws")

    assert "cd '/home/jetson/robot workspace/ros2_ws'" in command


def test_start_is_guarded_against_duplicate_session():
    command = start_bringup_command("/home/jetson/robot/ros2_ws")

    assert "tmux has-session -t amr_bringup" in command
    assert "pgrep -f '[a]mr_driver_node'" in command
    assert "tmux new-session -d -s amr_bringup" in command
    assert "history-limit 10000" in command


def test_status_has_machine_readable_markers_and_log_capture():
    command = bringup_status_command()

    assert RUNNING_MARKER in command
    assert STOPPED_MARKER in command
    assert TMUX_MISSING_MARKER in command
    assert "tail -n 800" in command


def test_start_persists_launch_output():
    command = start_bringup_command("/home/jetson/robot/ros2_ws")

    assert "set -o pipefail" in command
    assert "amr_bringup.log" in command
    assert "tee" in command


def test_stop_sends_ctrl_c_instead_of_killing_session():
    command = stop_bringup_command()

    assert "send-keys" in command
    assert "C-c" in command
    assert "kill-session" not in command
    assert "Stop Nav2 before bringup" in command


@pytest.mark.parametrize(
    "workspace, domain_id",
    [
        ("relative/ros2_ws", 0),
        ("/home/jetson/robot\ncommand", 0),
        ("/home/jetson/robot", -1),
        ("/home/jetson/robot", 233),
    ],
)
def test_invalid_remote_configuration_is_rejected(workspace, domain_id):
    with pytest.raises(ValueError):
        robot_bringup_launch_command(workspace, domain_id=domain_id)
