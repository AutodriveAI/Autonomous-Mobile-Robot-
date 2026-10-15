"""Remote tmux commands for Slam Toolbox mapping and map saving."""

from pathlib import PurePosixPath
import re
import shlex


MAPPING_SESSION = "amr_mapping"
MAPPING_RUNNING_MARKER = "__AMR_MAPPING_RUNNING__"
MAPPING_STOPPED_MARKER = "__AMR_MAPPING_STOPPED__"
TMUX_MISSING_MARKER = "__AMR_TMUX_MISSING__"
MAPPING_LOG_FILE = "$HOME/.local/state/amr_operator_gui/amr_mapping.log"

_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_RMW = re.compile(r"^[A-Za-z0-9_]+$")
_SAFE_MAP_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def _validated_values(
    workspace: str, domain_id: int, rmw_implementation: str
):
    workspace = workspace.strip()
    if (
        not workspace
        or "\x00" in workspace
        or "\n" in workspace
        or "\r" in workspace
        or not PurePosixPath(workspace).is_absolute()
    ):
        raise ValueError("Remote workspace must be a valid absolute path.")
    if not 0 <= domain_id <= 232:
        raise ValueError("ROS domain ID must be between 0 and 232.")
    if not _SAFE_RMW.fullmatch(rmw_implementation):
        raise ValueError("RMW implementation name contains unsupported characters.")
    return workspace, domain_id, rmw_implementation


def _validate_session(session: str) -> str:
    if not _SAFE_SESSION.fullmatch(session):
        raise ValueError("tmux session name contains unsupported characters.")
    return session


def _ros_environment_parts(
    workspace: str, domain_id: int, rmw_implementation: str
):
    workspace, domain_id, rmw_implementation = _validated_values(
        workspace, domain_id, rmw_implementation
    )
    return [
        "cd {}".format(shlex.quote(workspace)),
        "source /opt/ros/foxy/setup.bash",
        "source install/setup.bash",
        "export ROS_LOCALHOST_ONLY=0",
        "export ROS_DOMAIN_ID={}".format(domain_id),
        "export RMW_IMPLEMENTATION={}".format(rmw_implementation),
    ]


def mapping_launch_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return the physical-robot synchronous Slam Toolbox launch command."""
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    parts.append(
        "ros2 launch amr_slam mapping.launch.py "
        "use_sim_time:=false use_rviz:=false"
    )
    return " && ".join(parts)


def start_mapping_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
    session: str = MAPPING_SESSION,
) -> str:
    """Return a guarded tmux start command for Slam Toolbox."""
    session = _validate_session(session)
    launch = mapping_launch_command(
        workspace,
        domain_id=domain_id,
        rmw_implementation=rmw_implementation,
    )
    logged_launch = (
        'mkdir -p "$HOME/.local/state/amr_operator_gui" && '
        "set -o pipefail && {launch} 2>&1 | tee \"{log_file}\""
    ).format(launch=launch, log_file=MAPPING_LOG_FILE)
    tmux_shell = "bash -lc {}".format(shlex.quote(logged_launch))
    return (
        "if ! command -v tmux >/dev/null 2>&1; then "
        "printf '%s\\n' 'tmux is not installed on the Jetson.'; exit 19; "
        "fi; "
        "if tmux has-session -t {session} 2>/dev/null; then "
        "printf '%s\\n' 'Mapping session is already running.'; exit 17; "
        "fi; "
        "if pgrep -f '[/]nav2_amcl/amcl' >/dev/null; then "
        "printf '%s\\n' 'AMCL is running; stop localization first.'; exit 18; "
        "fi; "
        "if pgrep -f '[/]nav2_map_server/map_server' >/dev/null; then "
        "printf '%s\\n' 'map_server is running; stop localization first.'; "
        "exit 18; fi; "
        "if pgrep -f '[/]nav2_controller/controller_server' >/dev/null; then "
        "printf '%s\\n' 'Nav2 is running; stop navigation first.'; exit 21; "
        "fi; "
        "if pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node' >/dev/null; then "
        "printf '%s\\n' 'A Slam Toolbox process is already running.'; exit 20; "
        "fi; "
        "tmux new-session -d -s {session} -x 220 -y 60 {command} && "
        "tmux set-option -t {session} history-limit 10000 && "
        "printf '%s\\n' 'Mapping session started.'"
    ).format(session=session, command=shlex.quote(tmux_shell))


def mapping_status_command(session: str = MAPPING_SESSION) -> str:
    """Return mapping session state and retained output."""
    session = _validate_session(session)
    return (
        "if ! command -v tmux >/dev/null 2>&1; then "
        "printf '%s\\n' '{tmux_missing}'; "
        "elif tmux has-session -t {session} 2>/dev/null; then "
        "printf '%s\\n' '{running}'; "
        "else printf '%s\\n' '{stopped}'; fi; "
        "if [ -f \"{log_file}\" ]; then tail -n 800 \"{log_file}\"; fi"
    ).format(
        session=session,
        running=MAPPING_RUNNING_MARKER,
        stopped=MAPPING_STOPPED_MARKER,
        tmux_missing=TMUX_MISSING_MARKER,
        log_file=MAPPING_LOG_FILE,
    )


def stop_mapping_command(session: str = MAPPING_SESSION) -> str:
    """Return a graceful Ctrl-C request for Slam Toolbox."""
    session = _validate_session(session)
    return (
        "if tmux has-session -t {session} 2>/dev/null; then "
        "tmux send-keys -t {session}:0.0 C-c; "
        "printf '%s\\n' 'Sent Ctrl-C to mapping.'; "
        "else printf '%s\\n' 'Mapping session is already stopped.'; fi"
    ).format(session=session)


def save_map_command(
    workspace: str,
    map_name: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return a non-overwriting Nav2 map_saver_cli command."""
    if not _SAFE_MAP_NAME.fullmatch(map_name):
        raise ValueError(
            "Map name must start with a letter and contain only letters, "
            "numbers, underscores, or hyphens (maximum 64 characters)."
        )
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    map_prefix = (
        PurePosixPath(workspace) / "src" / "amr_slam" / "maps" / map_name
    )
    quoted_prefix = shlex.quote(str(map_prefix))
    parts.extend([
        (
            "if [ -e {prefix}.yaml ] || [ -e {prefix}.pgm ]; then "
            "printf '%s\\n' 'Map files already exist; choose another name.'; "
            "exit 21; fi"
        ).format(prefix=quoted_prefix),
        "ros2 run nav2_map_server map_saver_cli -f {}".format(quoted_prefix),
    ])
    return " && ".join(parts)
