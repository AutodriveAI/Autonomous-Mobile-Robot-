"""Safe SSH-side commands for parameter-file tuning and live application."""

import base64
import hashlib
from pathlib import PurePosixPath
import re
import shlex


PARAMETER_FILE_MARKER = "__AMR_PARAMETER_FILE__"
PARAMETER_SAVE_MARKER = "__AMR_PARAMETER_SAVED__"
PARAMETER_CONFLICT_MARKER = "__AMR_PARAMETER_CONFLICT__"

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+\.ya?ml$")
_SAFE_NODE = re.compile(r"^/[A-Za-z0-9_/.-]+$")
_SAFE_PARAMETER = re.compile(r"^[A-Za-z0-9_.]+$")
_SAFE_RMW = re.compile(r"^[A-Za-z0-9_]+$")


def _config_path(workspace: str, filename: str) -> PurePosixPath:
    workspace = workspace.strip()
    if not workspace or not PurePosixPath(workspace).is_absolute():
        raise ValueError("Remote workspace must be an absolute path.")
    if any(character in workspace for character in "\x00\n\r"):
        raise ValueError("Remote workspace path is invalid.")
    if not _SAFE_FILENAME.fullmatch(filename):
        raise ValueError("Parameter filename must be a simple .yaml name.")
    return (
        PurePosixPath(workspace)
        / "src"
        / "amr_navigation"
        / "config"
        / filename
    )


def parameter_file_list_command(workspace: str) -> str:
    """List YAML files in the remote navigation config directory."""
    placeholder = _config_path(workspace, "placeholder.yaml")
    directory = shlex.quote(str(placeholder.parent))
    return (
        "find {directory} -maxdepth 1 -type f "
        "\\( -name '*.yaml' -o -name '*.yml' \\) -printf '%f\\n' | sort"
    ).format(directory=directory)


def parameter_file_read_command(workspace: str, filename: str) -> str:
    """Return a marker followed by one base64-encoded parameter file."""
    path = shlex.quote(str(_config_path(workspace, filename)))
    return (
        "if [ ! -f {path} ]; then printf '%s\\n' 'File not found: {name}'; "
        "exit 44; fi; printf '%s\\n' '{marker}'; base64 -w 0 {path}; "
        "printf '\\n'"
    ).format(path=path, name=filename, marker=PARAMETER_FILE_MARKER)


def parameter_file_write_command(
    workspace: str,
    filename: str,
    content: str,
    expected_sha256: str,
) -> str:
    """Validate and atomically replace a parameter file with conflict checks."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Expected SHA-256 is invalid.")
    path_value = str(_config_path(workspace, filename))
    path = shlex.quote(path_value)
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    python_check = (
        "import sys, yaml; yaml.safe_load(open(sys.argv[1], encoding='utf-8'))"
    )
    return (
        "current=$(sha256sum {path} | awk '{{print $1}}'); "
        "if [ \"$current\" != {expected} ]; then printf '%s\\n' "
        "'{conflict}'; exit 73; fi; "
        "tmp={path}.amr-tuning.$$; trap 'rm -f \"$tmp\"' EXIT; "
        "printf '%s' {encoded} | base64 -d > \"$tmp\" && "
        "python3 -c {python_check} \"$tmp\" && "
        "cp -p {path} {path}.amr_operator_gui.bak && "
        "mv \"$tmp\" {path} && trap - EXIT && "
        "printf '%s\\n' '{saved}'"
    ).format(
        path=path,
        expected=shlex.quote(expected_sha256),
        conflict=PARAMETER_CONFLICT_MARKER,
        encoded=shlex.quote(encoded),
        python_check=shlex.quote(python_check),
        saved=PARAMETER_SAVE_MARKER,
    )


def live_parameter_command(
    workspace: str,
    node: str,
    parameter: str,
    value_text: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Set and read back one scalar parameter on a running ROS node."""
    placeholder = _config_path(workspace, "placeholder.yaml")
    if not _SAFE_NODE.fullmatch(node):
        raise ValueError("ROS node name is invalid.")
    if not _SAFE_PARAMETER.fullmatch(parameter):
        raise ValueError("ROS parameter name is invalid.")
    if not 0 <= domain_id <= 232:
        raise ValueError("ROS domain ID must be between 0 and 232.")
    if not _SAFE_RMW.fullmatch(rmw_implementation):
        raise ValueError("RMW implementation name is invalid.")
    if not value_text.strip() or any(c in value_text for c in "\x00\n\r"):
        raise ValueError("Live parameter value must be one YAML scalar.")
    parts = [
        "cd {}".format(shlex.quote(str(placeholder.parents[3]))),
        "source /opt/ros/foxy/setup.bash",
        "source install/setup.bash",
        "export ROS_LOCALHOST_ONLY=0",
        "export ROS_DOMAIN_ID={}".format(domain_id),
        "export RMW_IMPLEMENTATION={}".format(rmw_implementation),
        "ros2 param set --no-daemon {} {} {}".format(
            shlex.quote(node),
            shlex.quote(parameter),
            shlex.quote(value_text.strip()),
        ),
        "ros2 param get --no-daemon {} {}".format(
            shlex.quote(node), shlex.quote(parameter)
        ),
    ]
    return " && ".join(parts)


def content_sha256(content: str) -> str:
    """Return the hash used for optimistic file-write concurrency checks."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
