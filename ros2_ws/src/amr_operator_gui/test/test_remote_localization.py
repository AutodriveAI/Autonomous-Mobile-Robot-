"""Tests for remote localization command construction."""

import pytest

from amr_operator_gui.remote_localization import (
    LOCALIZATION_RUNNING_MARKER,
    LOCALIZATION_STOPPED_MARKER,
    localization_launch_command,
    localization_status_command,
    map_list_command,
    start_localization_command,
    stop_localization_command,
    tf_probe_command,
)


def test_map_list_reads_source_map_directory():
    command = map_list_command("/home/jetson/robot/ros2_ws")

    assert "/src/amr_slam/maps" in command
    assert "*.yaml" in command


def test_localization_uses_selected_map_without_remote_rviz():
    command = localization_launch_command(
        "/home/jetson/robot/ros2_ws", "park.yaml"
    )

    assert "amr_slam/maps/park.yaml" in command
    assert "use_sim_time:=false" in command
    assert "use_rviz:=false" in command


def test_localization_rejects_unsafe_map_filename():
    with pytest.raises(ValueError):
        localization_launch_command(
            "/home/jetson/robot/ros2_ws", "../../other.yaml"
        )


def test_start_is_guarded_and_logged():
    command = start_localization_command(
        "/home/jetson/robot/ros2_ws", "LakecityFlat4AMap.yaml"
    )

    assert "tmux has-session -t amr_localisation" in command
    assert "pgrep -f '[/]nav2_amcl/amcl'" in command
    assert "pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node'" in command
    assert "pgrep -f '[/]nav2_controller/controller_server'" in command
    assert "amr_localisation.log" in command


def test_status_contains_markers_and_retained_log():
    command = localization_status_command()

    assert LOCALIZATION_RUNNING_MARKER in command
    assert LOCALIZATION_STOPPED_MARKER in command
    assert "tail -n 800" in command


def test_stop_is_graceful():
    command = stop_localization_command()

    assert "send-keys" in command
    assert "C-c" in command
    assert "kill-session" not in command
    assert "tmux has-session -t amr_nav2" in command
    assert "Stopping dependent Nav2 session first" in command
    assert "Nav2 did not stop within 20 seconds" in command
    assert command.index("amr_nav2") < command.index("amr_localisation")
    assert "Stop Nav2 before localization" in command


def test_localization_stop_can_keep_strict_non_cascading_guard():
    command = stop_localization_command(stop_dependents=False)

    assert "Stopping dependent Nav2 session first" not in command
    assert "Stop Nav2 before localization" in command


def test_tf_probe_targets_map_to_base_link():
    command = tf_probe_command("/home/jetson/robot/ros2_ws")

    assert "tf2_echo map base_link" in command
    assert "exec ros2 run tf2_ros" in command
