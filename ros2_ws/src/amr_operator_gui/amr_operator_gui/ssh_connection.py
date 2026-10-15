"""SSH connection settings and command construction."""

from dataclasses import dataclass
import os
import re
from typing import List


_SAFE_USER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SAFE_HOST = re.compile(r"^[A-Za-z0-9_.:\-\[\]]+$")


@dataclass(frozen=True)
class SshSettings:
    """Values needed to connect to the robot without an interactive shell."""

    host: str
    username: str = "jetson"
    port: int = 22
    identity_file: str = ""
    timeout_seconds: int = 5

    def validate(self) -> None:
        """Reject empty or malformed values before invoking OpenSSH."""
        if not self.host or not _SAFE_HOST.fullmatch(self.host):
            raise ValueError("Host must be an IP address or resolvable hostname.")
        if not self.username or not _SAFE_USER.fullmatch(self.username):
            raise ValueError("Username contains unsupported characters.")
        if not 1 <= self.port <= 65535:
            raise ValueError("SSH port must be between 1 and 65535.")
        if not 1 <= self.timeout_seconds <= 60:
            raise ValueError("Connection timeout must be between 1 and 60 seconds.")

    @property
    def target(self) -> str:
        """Return the OpenSSH destination string."""
        return "{}@{}".format(self.username, self.host)


def ssh_base_arguments(settings: SshSettings) -> List[str]:
    """Build common safe argv for a non-interactive OpenSSH process."""
    settings.validate()
    arguments = [
        "-T",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout={}".format(settings.timeout_seconds),
        "-o", "ServerAliveInterval=2",
        "-o", "ServerAliveCountMax=1",
        "-p", str(settings.port),
    ]
    if settings.identity_file.strip():
        arguments.extend([
            "-i", os.path.expanduser(settings.identity_file.strip()),
        ])
    arguments.append(settings.target)
    return arguments


def connection_test_arguments(settings: SshSettings) -> List[str]:
    """Build argv for a non-interactive SSH connectivity check."""
    return ssh_base_arguments(settings) + ["hostname"]


def remote_command_arguments(
    settings: SshSettings, remote_command: str
) -> List[str]:
    """Build argv for one fixed or safely quoted remote command."""
    if not remote_command or "\x00" in remote_command:
        raise ValueError("Remote command must not be empty or contain NUL bytes.")
    return ssh_base_arguments(settings) + [remote_command]
