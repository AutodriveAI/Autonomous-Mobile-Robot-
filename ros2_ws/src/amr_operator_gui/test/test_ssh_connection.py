"""Tests for SSH argument construction."""

import os

import pytest

from amr_operator_gui.ssh_connection import (
    SshSettings,
    connection_test_arguments,
    remote_command_arguments,
)


def test_default_connection_arguments():
    arguments = connection_test_arguments(SshSettings(host="192.168.1.42"))

    assert arguments[-2:] == ["jetson@192.168.1.42", "hostname"]
    assert "BatchMode=yes" in arguments
    assert arguments[arguments.index("-p") + 1] == "22"


def test_custom_port_and_identity_file():
    arguments = connection_test_arguments(
        SshSettings(
            host="nano.local",
            username="robot",
            port=2222,
            identity_file="~/.ssh/amr_key",
        )
    )

    assert arguments[arguments.index("-p") + 1] == "2222"
    assert arguments[arguments.index("-i") + 1] == os.path.expanduser(
        "~/.ssh/amr_key"
    )
    assert arguments[-2] == "robot@nano.local"


def test_remote_command_is_one_argument_after_destination():
    arguments = remote_command_arguments(
        SshSettings(host="nano.local"), "tmux has-session -t amr_bringup"
    )

    assert arguments[-2:] == [
        "jetson@nano.local",
        "tmux has-session -t amr_bringup",
    ]


@pytest.mark.parametrize(
    "settings",
    [
        SshSettings(host=""),
        SshSettings(host="name with spaces"),
        SshSettings(host="nano", username="bad user"),
        SshSettings(host="nano", port=0),
    ],
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        connection_test_arguments(settings)
