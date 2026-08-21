"""Tests for remote Slam Toolbox and map-save commands."""

import pytest

from amr_operator_gui.remote_mapping import (
    MAPPING_RUNNING_MARKER,
    MAPPING_STOPPED_MARKER,
    mapping_launch_command,
    mapping_status_command,
    save_map_command,
    start_mapping_command,
    stop_mapping_command,
)


def test_mapping_launch_is_real_robot_without_remote_rviz():
    command = mapping_launch_command("/home/jetson/robot/ros2_ws")

    assert "amr_slam mapping.launch.py" in command
    assert "use_sim_time:=false" in command
    assert "use_rviz:=false" in command


def test_mapping_start_rejects_parallel_amcl_and_slam():
    command = start_mapping_command("/home/jetson/robot/ros2_ws")

    assert "pgrep -f '[/]nav2_amcl/amcl'" in command
    assert "pgrep -f '[/]nav2_map_server/map_server'" in command
    assert "pgrep -f '[/]nav2_controller/controller_server'" in command
    assert "pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node'" in command
    assert "tmux new-session -d -s amr_mapping" in command
    assert "amr_mapping.log" in command


def test_mapping_status_has_markers_and_log():
    command = mapping_status_command()

    assert MAPPING_RUNNING_MARKER in command
    assert MAPPING_STOPPED_MARKER in command
    assert "tail -n 800" in command


def test_mapping_stop_is_graceful():
    command = stop_mapping_command()

    assert "send-keys" in command
    assert "C-c" in command
    assert "kill-session" not in command


def test_save_map_targets_source_map_directory_without_extension():
    command = save_map_command(
        "/home/jetson/robot/ros2_ws", "NewRestaurantMap"
    )

    assert "/src/amr_slam/maps/NewRestaurantMap" in command
    assert "map_saver_cli -f" in command
    assert "Map files already exist" in command


@pytest.mark.parametrize(
    "name",
    ["", "123map", "map with spaces", "../map", "map.yaml", "a" * 65],
)
def test_save_map_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        save_map_command("/home/jetson/robot/ros2_ws", name)
