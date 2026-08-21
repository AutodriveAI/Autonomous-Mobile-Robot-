"""Tests for VS Code Remote-SSH argument construction."""

import pytest

from amr_operator_gui.local_vscode import vscode_remote_arguments
from amr_operator_gui.ssh_connection import SshSettings


def test_vscode_opens_remote_repository_parent():
    settings = SshSettings(host="10.206.146.161", username="jetson")

    arguments = vscode_remote_arguments(
        settings,
        "/home/jetson/Autonomous_Mobile_Robot/"
        "Autonomous-Mobile-Robot-/ros2_ws",
    )

    assert arguments == [
        "--new-window",
        "--remote",
        "ssh-remote+jetson@10.206.146.161",
        "/home/jetson/Autonomous_Mobile_Robot/Autonomous-Mobile-Robot-",
    ]


def test_vscode_rejects_relative_remote_workspace():
    settings = SshSettings(host="nano", username="jetson")

    with pytest.raises(ValueError, match="absolute"):
        vscode_remote_arguments(settings, "relative/ros2_ws")


def test_vscode_explains_nonstandard_port_requirement():
    settings = SshSettings(host="nano", username="jetson", port=2222)

    with pytest.raises(ValueError, match="SSH config alias"):
        vscode_remote_arguments(settings, "/home/jetson/repository/ros2_ws")
