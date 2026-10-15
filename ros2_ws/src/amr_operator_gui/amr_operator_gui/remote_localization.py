"""Remote tmux commands for AMCL localization on the physical robot."""

from pathlib import PurePosixPath
import re
import shlex

from amr_operator_gui.remote_navigation import NAVIGATION_SESSION


LOCALIZATION_SESSION = "amr_localisation"
LOCALIZATION_RUNNING_MARKER = "__AMR_LOCALIZATION_RUNNING__"
LOCALIZATION_STOPPED_MARKER = "__AMR_LOCALIZATION_STOPPED__"
TMUX_MISSING_MARKER = "__AMR_TMUX_MISSING__"
LOCALIZATION_LOG_FILE = (
    "$HOME/.local/state/amr_operator_gui/amr_localisation.log"
)

_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_RMW = re.compile(r"^[A-Za-z0-9_]+$")
_SAFE_MAP = re.compile(r"^[A-Za-z0-9_.-]+\.yaml$")


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


def map_list_command(workspace: str) -> str:
    """Return a command listing source-tree map YAML filenames."""
    workspace, _, _ = _validated_values(
        workspace, 0, "rmw_cyclonedds_cpp"
    )
    maps_directory = PurePosixPath(workspace) / "src" / "amr_slam" / "maps"
    return (
        "find {directory} -maxdepth 1 -type f -name '*.yaml' "
        "-printf '%f\\n' | sort"
    ).format(directory=shlex.quote(str(maps_directory)))


def localization_launch_command(
    workspace: str,
    map_filename: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return the Foxy AMCL launch command for a selected source map."""
    if not _SAFE_MAP.fullmatch(map_filename):
        raise ValueError("Select a valid map YAML filename.")
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    map_path = (
        PurePosixPath(workspace)
        / "src"
        / "amr_slam"
        / "maps"
        / map_filename
    )
    parts.append(
        "ros2 launch amr_localisation localisation.launch.py "
        "map:={} use_sim_time:=false use_rviz:=false".format(
            shlex.quote(str(map_path))
        )
    )
    return " && ".join(parts)


def start_localization_command(
    workspace: str,
    map_filename: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
    session: str = LOCALIZATION_SESSION,
) -> str:
    """Return a guarded tmux start command for AMCL and map_server."""
    session = _validate_session(session)
    launch = localization_launch_command(
        workspace,
        map_filename,
        domain_id=domain_id,
        rmw_implementation=rmw_implementation,
    )
    logged_launch = (
        'mkdir -p "$HOME/.local/state/amr_operator_gui" && '
        "set -o pipefail && {launch} 2>&1 | tee \"{log_file}\""
    ).format(launch=launch, log_file=LOCALIZATION_LOG_FILE)
    tmux_shell = "bash -lc {}".format(shlex.quote(logged_launch))
    return (
        "if ! command -v tmux >/dev/null 2>&1; then "
        "printf '%s\\n' 'tmux is not installed on the Jetson.'; exit 19; "
        "fi; "
        "if tmux has-session -t {session} 2>/dev/null; then "
        "printf '%s\\n' 'Localization session is already running.'; exit 17; "
        "fi; "
        "if pgrep -f '[/]nav2_amcl/amcl' >/dev/null; then "
        "printf '%s\\n' 'An AMCL process is already running.'; exit 18; "
        "fi; "
        "if pgrep -f '[/]slam_toolbox/sync_slam_toolbox_node' >/dev/null; then "
        "printf '%s\\n' 'Slam Toolbox is running; stop mapping first.'; "
        "exit 20; fi; "
        "if pgrep -f '[/]nav2_controller/controller_server' >/dev/null; then "
        "printf '%s\\n' 'Nav2 is already running; stop it first.'; exit 21; "
        "fi; "
        "tmux new-session -d -s {session} -x 220 -y 60 {command} && "
        "tmux set-option -t {session} history-limit 10000 && "
        "printf '%s\\n' 'Localization session started.'"
    ).format(session=session, command=shlex.quote(tmux_shell))


def localization_status_command(session: str = LOCALIZATION_SESSION) -> str:
    """Return localization session state and retained output."""
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
        running=LOCALIZATION_RUNNING_MARKER,
        stopped=LOCALIZATION_STOPPED_MARKER,
        tmux_missing=TMUX_MISSING_MARKER,
        log_file=LOCALIZATION_LOG_FILE,
    )


def stop_localization_command(
    session: str = LOCALIZATION_SESSION,
    navigation_session: str = NAVIGATION_SESSION,
    stop_dependents: bool = True,
) -> str:
    """Gracefully stop Nav2 when needed, then stop localization."""
    session = _validate_session(session)
    navigation_session = _validate_session(navigation_session)
    nav_running = (
        "tmux has-session -t {nav_session} 2>/dev/null || "
        "pgrep -f '[/]nav2_controller/controller_server' >/dev/null || "
        "pgrep -f '[/]nav2_bt_navigator/bt_navigator' >/dev/null"
    ).format(nav_session=navigation_session)
    dependent_stop = ""
    if stop_dependents:
        dependent_stop = (
            "if {nav_running}; then "
            "if ! tmux has-session -t {nav_session} 2>/dev/null; then "
            "printf '%s\\n' 'Nav2 is running outside the operator tmux session; "
            "stop that manual launch first.'; exit 26; fi; "
            "printf '%s\\n' 'Stopping dependent Nav2 session first...'; "
            "tmux send-keys -t {nav_session}:0.0 C-c; count=0; "
            "while {{ {nav_running}; }} && [ \"$count\" -lt 20 ]; do "
            "sleep 1; count=$((count + 1)); done; "
            "if {nav_running}; then printf '%s\\n' "
            "'Nav2 did not stop within 20 seconds; localization was left running.'; "
            "exit 25; fi; fi; "
        ).format(
            nav_running=nav_running,
            nav_session=navigation_session,
        )
    localization_running = (
        "tmux has-session -t {session} 2>/dev/null || "
        "pgrep -f '[/]nav2_amcl/amcl' >/dev/null || "
        "pgrep -f '[/]nav2_map_server/map_server' >/dev/null"
    ).format(session=session)
    return dependent_stop + (
        "if pgrep -f '[/]nav2_controller/controller_server' >/dev/null; then "
        "printf '%s\\n' 'Stop Nav2 before localization.'; exit 22; fi; "
        "if ! tmux has-session -t {session} 2>/dev/null && "
        "{{ pgrep -f '[/]nav2_amcl/amcl' >/dev/null || "
        "pgrep -f '[/]nav2_map_server/map_server' >/dev/null; }}; then "
        "printf '%s\\n' 'Localization is running outside the operator tmux "
        "session; stop that manual launch first.'; exit 29; fi; "
        "if tmux has-session -t {session} 2>/dev/null; then "
        "tmux send-keys -t {session}:0.0 C-c; "
        "printf '%s\\n' 'Sent Ctrl-C to localization.'; count=0; "
        "while {{ {localization_running}; }} && [ \"$count\" -lt 20 ]; do "
        "sleep 1; count=$((count + 1)); done; "
        "if {localization_running}; then printf '%s\\n' "
        "'Localization did not stop within 20 seconds.'; exit 30; fi; "
        "else printf '%s\\n' 'Localization session is already stopped.'; fi"
    ).format(
        session=session,
        localization_running=localization_running,
    )


def tf_probe_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return a continuous map-to-base_link transform probe."""
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    parts.append("exec ros2 run tf2_ros tf2_echo map base_link")
    return " && ".join(parts)
