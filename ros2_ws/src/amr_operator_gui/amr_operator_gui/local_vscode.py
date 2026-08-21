"""Local VS Code Remote-SSH command construction."""

from pathlib import PurePosixPath
from typing import List

from amr_operator_gui.ssh_connection import SshSettings


def vscode_remote_arguments(
    settings: SshSettings, remote_workspace: str
) -> List[str]:
    """Return argv that opens the robot repository through Remote-SSH."""
    settings.validate()
    if settings.port != 22:
        raise ValueError(
            "VS Code Remote-SSH must use port 22 here. For another port, "
            "create an SSH config alias and enter that alias as the Host."
        )

    workspace = remote_workspace.strip()
    if not workspace or "\x00" in workspace:
        raise ValueError("Remote workspace must not be empty.")
    workspace_path = PurePosixPath(workspace)
    if not workspace_path.is_absolute():
        raise ValueError("Remote workspace must be an absolute Jetson path.")

    repository_path = workspace_path.parent
    authority = "ssh-remote+{}".format(settings.target)
    return [
        "--new-window",
        "--remote",
        authority,
        str(repository_path),
    ]
