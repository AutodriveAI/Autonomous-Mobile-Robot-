"""Tests for remote Nav2 commands."""

from amr_operator_gui.remote_navigation import (
    NAVIGATION_RUNNING_MARKER,
    NAVIGATION_STOPPED_MARKER,
    navigation_health_probe_command,
    navigation_launch_command,
    navigation_status_command,
    start_navigation_command,
    stop_navigation_command,
)


def test_navigation_launch_uses_real_source_params():
    command = navigation_launch_command("/home/jetson/robot/ros2_ws")

    assert "/src/amr_navigation/config/nav2_params_real.yaml" in command
    assert "use_sim_time:=false" in command
    assert "autostart:=true" in command
    assert "use_rviz:=false" in command


def test_navigation_start_requires_localization_and_rejects_duplicates():
    command = start_navigation_command("/home/jetson/robot/ros2_ws")

    assert "! pgrep -f '[/]nav2_amcl/amcl'" in command
    assert "pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node'" in command
    assert "pgrep -f '[/]nav2_controller/controller_server'" in command
    assert "tmux new-session -d -s amr_nav2" in command
    assert "amr_nav2.log" in command


def test_navigation_status_has_markers_and_log():
    command = navigation_status_command()

    assert NAVIGATION_RUNNING_MARKER in command
    assert NAVIGATION_STOPPED_MARKER in command
    assert "tail -n 900" in command


def test_navigation_stop_is_graceful():
    command = stop_navigation_command()

    assert "send-keys" in command
    assert "C-c" in command
    assert "kill-session" not in command


def test_health_probe_uses_operator_package():
    command = navigation_health_probe_command("/home/jetson/robot/ros2_ws")

    assert "exec ros2 run amr_operator_gui nav2_health_probe" in command
