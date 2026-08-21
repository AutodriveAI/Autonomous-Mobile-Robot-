"""Tests for local RViz command construction."""

from pathlib import Path

import pytest

from amr_operator_gui.local_rviz import rviz_launch_command


def test_rviz_command_uses_saved_config(tmp_path):
    config = (
        tmp_path
        / "src"
        / "amr_navigation"
        / "rviz"
        / "nav2_real_robot.rviz"
    )
    config.parent.mkdir(parents=True)
    config.touch()

    command = rviz_launch_command(str(tmp_path), domain_id=7)

    assert "source /opt/ros/humble/setup.bash" in command
    assert "export ROS_DOMAIN_ID=7" in command
    assert "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" in command
    assert "exec rviz2 -d {}".format(config) in command


def test_rviz_command_requires_saved_config(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        rviz_launch_command(str(tmp_path))


def test_rviz_command_rejects_relative_workspace():
    with pytest.raises(ValueError, match="absolute"):
        rviz_launch_command(str(Path("relative/ros2_ws")))
