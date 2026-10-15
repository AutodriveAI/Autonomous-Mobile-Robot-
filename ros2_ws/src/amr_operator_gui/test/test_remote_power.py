"""Tests for the guarded Jetson shutdown command."""

from amr_operator_gui.remote_power import (
    SHUTDOWN_AUTHORIZED_MARKER,
    SHUTDOWN_PERMISSION_DENIED_MARKER,
    shutdown_command,
)


def test_shutdown_uses_exact_non_interactive_systemctl_command():
    command = shutdown_command()

    assert "sudo -n -l /bin/systemctl poweroff" in command
    assert "exec sudo -n /bin/systemctl poweroff" in command
    assert SHUTDOWN_AUTHORIZED_MARKER in command
    assert SHUTDOWN_PERMISSION_DENIED_MARKER in command


def test_shutdown_command_does_not_offer_an_interactive_password_prompt():
    command = shutdown_command()

    assert "sudo /bin/systemctl" not in command
    assert "sudo -S" not in command


def test_operator_window_provides_shutdown_process_error_handler():
    from amr_operator_gui.main import OperatorWindow

    assert callable(OperatorWindow._shutdown_process_error)
