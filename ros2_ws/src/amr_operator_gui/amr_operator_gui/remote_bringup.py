"""Remote tmux commands for the physical robot bringup session."""

from pathlib import PurePosixPath
import re
import shlex


BRINGUP_SESSION = "amr_bringup"
RUNNING_MARKER = "__AMR_BRINGUP_RUNNING__"
STOPPED_MARKER = "__AMR_BRINGUP_STOPPED__"
TMUX_MISSING_MARKER = "__AMR_TMUX_MISSING__"
DEFAULT_REMOTE_WORKSPACE = (
    "/home/jetson/Autonomous_Mobile_Robot/Autonomous-Mobile-Robot-/ros2_ws"
)
BRINGUP_LOG_FILE = "$HOME/.local/state/amr_operator_gui/amr_bringup.log"

_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_RMW = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_workspace(workspace: str) -> str:
    value = workspace.strip()
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("Remote workspace path is invalid.")
    if not PurePosixPath(value).is_absolute():
        raise ValueError("Remote workspace must be an absolute path.")
    return value


def _validate_session(session: str) -> str:
    if not _SAFE_SESSION.fullmatch(session):
        raise ValueError("tmux session name contains unsupported characters.")
    return session


def _validate_domain_id(domain_id: int) -> int:
    if not 0 <= domain_id <= 232:
        raise ValueError("ROS domain ID must be between 0 and 232.")
    return domain_id


def _validate_rmw(rmw_implementation: str) -> str:
    if not _SAFE_RMW.fullmatch(rmw_implementation):
        raise ValueError("RMW implementation name contains unsupported characters.")
    return rmw_implementation


def robot_bringup_launch_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return the hardware-only ROS launch command run inside tmux."""
    workspace = _validate_workspace(workspace)
    domain_id = _validate_domain_id(domain_id)
    rmw_implementation = _validate_rmw(rmw_implementation)

    launch_arguments = [
        "use_rviz:=false",
        "use_lcd:=true",
        "use_lidar:=true",
        "use_realsense:=true",
        "start_joy_teleop:=true",
        "start_keyboard_teleop:=false",
        "start_localisation:=false",
        "start_nav2:=false",
        "bypass_twist_mux:=false",
    ]
    parts = [
        "cd {}".format(shlex.quote(workspace)),
        "source /opt/ros/foxy/setup.bash",
        "source install/setup.bash",
        "export ROS_LOCALHOST_ONLY=0",
        "export ROS_DOMAIN_ID={}".format(domain_id),
        "export RMW_IMPLEMENTATION={}".format(rmw_implementation),
        "ros2 launch amr_bringup robot_bringup.launch.py {}".format(
            " ".join(launch_arguments)
        ),
    ]
    return " && ".join(parts)


def start_bringup_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
    session: str = BRINGUP_SESSION,
) -> str:
    """Return a guarded command that starts bringup in persistent tmux."""
    session = _validate_session(session)
    launch = robot_bringup_launch_command(
        workspace, domain_id=domain_id, rmw_implementation=rmw_implementation
    )
    logged_launch = (
        'mkdir -p "$HOME/.local/state/amr_operator_gui" && '
        "set -o pipefail && {launch} 2>&1 | tee \"{log_file}\""
    ).format(launch=launch, log_file=BRINGUP_LOG_FILE)
    tmux_shell = "bash -lc {}".format(shlex.quote(logged_launch))
    return (
        "if ! command -v tmux >/dev/null 2>&1; then "
        "printf '%s\\n' 'tmux is not installed on the Jetson.'; exit 19; "
        "fi; "
        "if tmux has-session -t {session} 2>/dev/null; then "
        "printf '%s\\n' 'Bringup session is already running.'; exit 17; "
        "fi; "
        "if pgrep -f '[a]mr_driver_node' >/dev/null; then "
        "printf '%s\\n' 'An AMR driver process is already running.'; exit 18; "
        "fi; "
        "tmux new-session -d -s {session} -x 220 -y 60 {command} && "
        "tmux set-option -t {session} history-limit 10000 && "
        "printf '%s\\n' 'Bringup session started.'"
    ).format(session=session, command=shlex.quote(tmux_shell))


def bringup_status_command(session: str = BRINGUP_SESSION) -> str:
    """Return a command that reports state and returns recent launch output."""
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
        running=RUNNING_MARKER,
        stopped=STOPPED_MARKER,
        tmux_missing=TMUX_MISSING_MARKER,
        log_file=BRINGUP_LOG_FILE,
    )


def stop_bringup_command(session: str = BRINGUP_SESSION) -> str:
    """Return a graceful Ctrl-C request for the bringup tmux pane."""
    session = _validate_session(session)
    return (
        "if pgrep -f '[/]nav2_controller/controller_server' >/dev/null; then "
        "printf '%s\\n' 'Stop Nav2 before bringup.'; exit 22; fi; "
        "if pgrep -f '[/]nav2_amcl/amcl' >/dev/null; then "
        "printf '%s\\n' 'Stop localization before bringup.'; exit 23; fi; "
        "if pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node' >/dev/null; then "
        "printf '%s\\n' 'Stop mapping before bringup.'; exit 24; fi; "
        "if tmux has-session -t {session} 2>/dev/null; then "
        "tmux send-keys -t {session}:0.0 C-c; "
        "printf '%s\\n' 'Sent Ctrl-C to bringup.'; "
        "else printf '%s\\n' 'Bringup session is already stopped.'; fi"
    ).format(session=session)
