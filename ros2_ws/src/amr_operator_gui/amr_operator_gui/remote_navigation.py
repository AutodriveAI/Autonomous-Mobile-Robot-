"""Remote tmux commands for the physical robot Nav2 session."""

from pathlib import PurePosixPath
import re
import shlex


NAVIGATION_SESSION = "amr_nav2"
NAVIGATION_RUNNING_MARKER = "__AMR_NAV2_RUNNING__"
NAVIGATION_STOPPED_MARKER = "__AMR_NAV2_STOPPED__"
TMUX_MISSING_MARKER = "__AMR_TMUX_MISSING__"
NAVIGATION_LOG_FILE = "$HOME/.local/state/amr_operator_gui/amr_nav2.log"

_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_RMW = re.compile(r"^[A-Za-z0-9_]+$")


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


def navigation_launch_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return the real-robot Nav2 launch command using source-tree params."""
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    params_file = (
        PurePosixPath(workspace)
        / "src"
        / "amr_navigation"
        / "config"
        / "nav2_params_real.yaml"
    )
    parts.append(
        "ros2 launch amr_navigation nav2.launch.py "
        "params_file:={} use_sim_time:=false autostart:=true "
        "use_rviz:=false".format(shlex.quote(str(params_file)))
    )
    return " && ".join(parts)


def start_navigation_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
    session: str = NAVIGATION_SESSION,
) -> str:
    """Return a guarded tmux start command for the Nav2 servers."""
    session = _validate_session(session)
    launch = navigation_launch_command(
        workspace,
        domain_id=domain_id,
        rmw_implementation=rmw_implementation,
    )
    logged_launch = (
        'mkdir -p "$HOME/.local/state/amr_operator_gui" && '
        "set -o pipefail && {launch} 2>&1 | tee \"{log_file}\""
    ).format(launch=launch, log_file=NAVIGATION_LOG_FILE)
    tmux_shell = "bash -lc {}".format(shlex.quote(logged_launch))
    return (
        "if ! command -v tmux >/dev/null 2>&1; then "
        "printf '%s\\n' 'tmux is not installed on the Jetson.'; exit 19; "
        "fi; "
        "if tmux has-session -t {session} 2>/dev/null; then "
        "printf '%s\\n' 'Nav2 session is already running.'; exit 17; "
        "fi; "
        "if ! pgrep -f '[/]nav2_amcl/amcl' >/dev/null; then "
        "printf '%s\\n' 'AMCL is not running; start localization first.'; "
        "exit 18; fi; "
        "if pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node' >/dev/null; then "
        "printf '%s\\n' 'Slam Toolbox is running; stop mapping first.'; "
        "exit 20; fi; "
        "if pgrep -f '[/]nav2_controller/controller_server' >/dev/null || "
        "pgrep -f '[/]nav2_bt_navigator/bt_navigator' >/dev/null; then "
        "printf '%s\\n' 'Nav2 processes are already running.'; exit 21; "
        "fi; "
        "tmux new-session -d -s {session} -x 220 -y 60 {command} && "
        "tmux set-option -t {session} history-limit 10000 && "
        "printf '%s\\n' 'Nav2 session started.'"
    ).format(session=session, command=shlex.quote(tmux_shell))


def navigation_status_command(session: str = NAVIGATION_SESSION) -> str:
    """Return Nav2 session state and retained output."""
    session = _validate_session(session)
    return (
        "if ! command -v tmux >/dev/null 2>&1; then "
        "printf '%s\\n' '{tmux_missing}'; "
        "elif tmux has-session -t {session} 2>/dev/null; then "
        "printf '%s\\n' '{running}'; "
        "else printf '%s\\n' '{stopped}'; fi; "
        "if [ -f \"{log_file}\" ]; then tail -n 900 \"{log_file}\"; fi"
    ).format(
        session=session,
        running=NAVIGATION_RUNNING_MARKER,
        stopped=NAVIGATION_STOPPED_MARKER,
        tmux_missing=TMUX_MISSING_MARKER,
        log_file=NAVIGATION_LOG_FILE,
    )


def stop_navigation_command(session: str = NAVIGATION_SESSION) -> str:
    """Return a graceful Ctrl-C request for the Nav2 launch session."""
    session = _validate_session(session)
    return (
        "if tmux has-session -t {session} 2>/dev/null; then "
        "tmux send-keys -t {session}:0.0 C-c; "
        "printf '%s\\n' 'Sent Ctrl-C to Nav2.'; "
        "else printf '%s\\n' 'Nav2 session is already stopped.'; fi"
    ).format(session=session)


def restart_navigation_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
    session: str = NAVIGATION_SESSION,
) -> str:
    """Gracefully stop Nav2, wait for cleanup, and start it again."""
    session = _validate_session(session)
    stop = stop_navigation_command(session)
    start = start_navigation_command(
        workspace,
        domain_id=domain_id,
        rmw_implementation=rmw_implementation,
        session=session,
    )
    return (
        "{stop}; stop_status=$?; [ \"$stop_status\" -eq 0 ] || "
        "exit \"$stop_status\"; count=0; "
        "while {{ tmux has-session -t {session} 2>/dev/null || "
        "pgrep -f '[/]nav2_controller/controller_server' >/dev/null || "
        "pgrep -f '[/]nav2_bt_navigator/bt_navigator' >/dev/null; }} && "
        "[ \"$count\" -lt 20 ]; do sleep 1; count=$((count + 1)); done; "
        "if tmux has-session -t {session} 2>/dev/null || "
        "pgrep -f '[/]nav2_controller/controller_server' >/dev/null || "
        "pgrep -f '[/]nav2_bt_navigator/bt_navigator' >/dev/null; then "
        "printf '%s\\n' 'Nav2 did not stop within 20 seconds.'; exit 25; fi; "
        "{start}"
    ).format(stop=stop, session=session, start=start)


def navigation_health_probe_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return the continuous NavigateToPose action health probe command."""
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    parts.append("exec ros2 run amr_operator_gui nav2_health_probe")
    return " && ".join(parts)
