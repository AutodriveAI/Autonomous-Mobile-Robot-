"""Safe remote power command construction for the Jetson Nano."""


SHUTDOWN_AUTHORIZED_MARKER = "__AMR_SHUTDOWN_AUTHORIZED__"
SHUTDOWN_PERMISSION_DENIED_MARKER = "__AMR_SHUTDOWN_PERMISSION_DENIED__"


def shutdown_command() -> str:
    """Return a non-interactive, command-specific Jetson power-off command."""
    return (
        "if sudo -n -l /bin/systemctl poweroff >/dev/null 2>&1; then "
        "printf '%s\\n' '" + SHUTDOWN_AUTHORIZED_MARKER + "'; "
        "exec sudo -n /bin/systemctl poweroff; "
        "else printf '%s\\n' '" + SHUTDOWN_PERMISSION_DENIED_MARKER + "'; "
        "exit 77; fi"
    )
