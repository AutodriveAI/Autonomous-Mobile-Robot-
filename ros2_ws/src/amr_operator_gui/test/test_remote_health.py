import pytest

from amr_operator_gui.remote_health import system_health_probe_command


def test_health_probe_uses_robot_ros_environment_and_one_long_lived_process():
    command = system_health_probe_command(
        "/home/jetson/robot/ros2_ws",
        domain_id=7,
        rmw_implementation="rmw_cyclonedds_cpp",
    )

    assert "source /opt/ros/foxy/setup.bash" in command
    assert "source install/setup.bash" in command
    assert "export ROS_DOMAIN_ID=7" in command
    assert "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" in command
    assert command.endswith("exec ros2 run amr_operator_gui system_health_probe")


def test_health_probe_rejects_invalid_workspace():
    with pytest.raises(ValueError):
        system_health_probe_command("relative/workspace")
