"""Remote command for the continuous Jetson ROS health probe."""

from amr_operator_gui.remote_navigation import _ros_environment_parts


def system_health_probe_command(
    workspace: str,
    domain_id: int = 0,
    rmw_implementation: str = "rmw_cyclonedds_cpp",
) -> str:
    """Return a command that runs one long-lived health probe over SSH."""
    parts = _ros_environment_parts(workspace, domain_id, rmw_implementation)
    parts.append("exec ros2 run amr_operator_gui system_health_probe")
    return " && ".join(parts)
