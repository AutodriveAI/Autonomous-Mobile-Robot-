"""Local Humble RViz command construction."""

from pathlib import Path
import re
import shlex


DEFAULT_LOCAL_WORKSPACE = "~/Github/Autonomous-Mobile-Robot-/ros2_ws"

_SAFE_RMW = re.compile(r"^[A-Za-z0-9_]+$")


def rviz_launch_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return a local shell command for the unified real-robot RViz view."""
    expanded_workspace = Path(workspace.strip()).expanduser()
    if not expanded_workspace.is_absolute():
        raise ValueError("Local workspace must be an absolute path or start with ~.")
    if not 0 <= domain_id <= 232:
        raise ValueError("ROS domain ID must be between 0 and 232.")
    if not _SAFE_RMW.fullmatch(rmw_implementation):
        raise ValueError("RMW implementation name contains unsupported characters.")

    config = (
        expanded_workspace
        / "src"
        / "amr_navigation"
        / "rviz"
        / "nav2_real_robot.rviz"
    )
    if not config.is_file():
        raise ValueError("RViz configuration does not exist: {}".format(config))

    return " && ".join([
        "source /opt/ros/humble/setup.bash",
        "export ROS_LOCALHOST_ONLY=0",
        "export ROS_DOMAIN_ID={}".format(domain_id),
        "export RMW_IMPLEMENTATION={}".format(rmw_implementation),
        "exec rviz2 -d {}".format(shlex.quote(str(config))),
    ])
