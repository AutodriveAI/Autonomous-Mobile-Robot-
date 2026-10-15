"""Tests for remote parameter tuning command construction."""

import pytest

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


WORKSPACE = "/home/jetson/robot/ros2_ws"


def test_list_and_read_are_scoped_to_navigation_config():
    listing = parameter_file_list_command(WORKSPACE)
    reading = parameter_file_read_command(WORKSPACE, "nav2_params_real.yaml")

    assert "/src/amr_navigation/config" in listing
    assert "*.yaml" in listing
    assert PARAMETER_FILE_MARKER in reading
    assert "base64 -w 0" in reading


def test_write_is_atomic_validated_and_conflict_checked():
    content = "node:\n  ros__parameters:\n    value: 1\n"
    command = parameter_file_write_command(
        WORKSPACE,
        "nav2_params_real.yaml",
        content,
        content_sha256(content),
    )

    assert "sha256sum" in command
    assert PARAMETER_CONFLICT_MARKER in command
    assert "yaml.safe_load" in command
    assert ".amr_operator_gui.bak" in command
    assert PARAMETER_SAVE_MARKER in command


def test_live_set_uses_foxy_environment_and_readback():
    command = live_parameter_command(
        WORKSPACE,
        "/controller_server",
        "FollowPath.max_vel_theta",
        "5.5",
    )

    assert "source /opt/ros/foxy/setup.bash" in command
    assert "ros2 param set --no-daemon" in command
    assert "ros2 param get --no-daemon" in command
    assert "FollowPath.max_vel_theta" in command


@pytest.mark.parametrize("filename", ["../params.yaml", "bad name.yaml", "x.txt"])
def test_unsafe_filenames_are_rejected(filename):
    with pytest.raises(ValueError):
        parameter_file_read_command(WORKSPACE, filename)
