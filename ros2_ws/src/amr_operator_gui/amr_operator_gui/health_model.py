"""State-aware interpretation of AMR ROS health snapshots."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set


HEALTH_MARKER = "__AMR_SYSTEM_HEALTH__"


@dataclass(frozen=True)
class HealthCheck:
    """One user-facing health result."""

    subsystem: str
    name: str
    state: str
    detail: str

    @property
    def key(self) -> str:
        """Return a stable identifier used for transition tracking."""
        return "{}/{}".format(self.subsystem, self.name)


PROFILE_GRACE_SECONDS = {
    "Bringup": 25.0,
    "Localization": 20.0,
    "Mapping": 20.0,
    "Nav2": 35.0,
}

PROFILE_NODES = {
    "Bringup": [
        "/amr_driver_node",
        "/robot_state_publisher",
        "/rplidar_node",
        "/joy_node",
        "/joy_teleop",
        "/twist_mux",
        "/camera/camera",
        "/lcd_status",
    ],
    "Localization": [
        "/map_server",
        "/amcl",
        "/lifecycle_manager_localization",
    ],
    "Mapping": ["/slam_toolbox"],
    "Nav2": [
        "/controller_server",
        "/planner_server",
        "/recoveries_server",
        "/bt_navigator",
        "/waypoint_follower",
        "/lifecycle_manager_navigation",
    ],
}

PROFILE_TOPICS = {
    "Bringup": [
        ("/odom", True),
        ("/scan", True),
        ("/joint_states", True),
        ("/robot_description", False),
        ("/camera_rgb", False),
        ("/cmd_vel", False),
    ],
    "Localization": [
        ("/map", False),
        ("/amcl_pose", False),
    ],
    "Mapping": [("/map", False)],
    "Nav2": [
        ("/global_costmap/costmap", False),
        ("/local_costmap/costmap", False),
        ("/plan", False),
        ("/cmd_vel_nav", False),
    ],
}

PROFILE_LIFECYCLE = {
    "Localization": ["map_server", "amcl"],
    "Nav2": [
        "controller_server",
        "planner_server",
        "recoveries_server",
        "bt_navigator",
        "waypoint_follower",
    ],
}


def _missing_state(in_grace: bool) -> str:
    return "starting" if in_grace else "error"


def _node_checks(
    subsystem: str,
    snapshot: Dict,
    in_grace: bool,
) -> Iterable[HealthCheck]:
    nodes = set(snapshot.get("nodes", []))
    for node_name in PROFILE_NODES.get(subsystem, []):
        if node_name in nodes:
            yield HealthCheck(subsystem, node_name, "healthy", "Node present")
        else:
            yield HealthCheck(
                subsystem,
                node_name,
                _missing_state(in_grace),
                "Required node is missing",
            )


def _topic_checks(
    subsystem: str,
    snapshot: Dict,
    in_grace: bool,
) -> Iterable[HealthCheck]:
    publishers = snapshot.get("publishers", {})
    topic_ages = snapshot.get("topic_age", {})
    for topic_name, must_be_fresh in PROFILE_TOPICS.get(subsystem, []):
        count = int(publishers.get(topic_name, 0) or 0)
        if count < 1:
            yield HealthCheck(
                subsystem,
                topic_name,
                _missing_state(in_grace),
                "No publisher",
            )
            continue
        if not must_be_fresh:
            yield HealthCheck(
                subsystem,
                topic_name,
                "healthy",
                "{} publisher(s)".format(count),
            )
            continue
        age = topic_ages.get(topic_name)
        if age is None:
            yield HealthCheck(
                subsystem,
                topic_name,
                _missing_state(in_grace),
                "Publisher exists; no message observed yet",
            )
        elif float(age) > 3.0:
            yield HealthCheck(
                subsystem,
                topic_name,
                _missing_state(in_grace),
                "Messages stale for {:.1f} s".format(float(age)),
            )
        else:
            yield HealthCheck(
                subsystem,
                topic_name,
                "healthy",
                "Latest message {:.1f} s ago".format(float(age)),
            )


def _lifecycle_checks(
    subsystem: str,
    snapshot: Dict,
    in_grace: bool,
) -> Iterable[HealthCheck]:
    lifecycle = snapshot.get("lifecycle", {})
    for node_name in PROFILE_LIFECYCLE.get(subsystem, []):
        state = lifecycle.get(node_name, "unavailable")
        if state == "active":
            yield HealthCheck(
                subsystem,
                "{} lifecycle".format(node_name),
                "healthy",
                "Active",
            )
        else:
            yield HealthCheck(
                subsystem,
                "{} lifecycle".format(node_name),
                _missing_state(in_grace),
                "State: {}".format(state),
            )


def _transform_check(
    subsystem: str,
    snapshot: Dict,
    key: str,
    label: str,
    in_grace: bool,
    previously_healthy: Set[str],
    initial_pose_wait: bool = False,
) -> HealthCheck:
    transform = snapshot.get("transforms", {}).get(key, {})
    available = bool(transform.get("available", False))
    check_key = "{}/{}".format(subsystem, label)
    if not available:
        if in_grace:
            state = "starting"
            detail = "Waiting for transform"
        elif initial_pose_wait and check_key not in previously_healthy:
            state = "warning"
            detail = "Waiting for the initial pose"
        else:
            state = "error"
            detail = "Required transform is missing"
        return HealthCheck(subsystem, label, state, detail)

    age = transform.get("age")
    if age is not None and float(age) > 3.0:
        return HealthCheck(
            subsystem,
            label,
            _missing_state(in_grace),
            "Transform stale for {:.1f} s".format(float(age)),
        )
    detail = "Transform available"
    if age is not None:
        detail = "Latest transform {:.1f} s ago".format(float(age))
    return HealthCheck(subsystem, label, "healthy", detail)


def _session_check(subsystem: str, launch: Dict) -> HealthCheck:
    desired = launch.get("desired")
    running = bool(launch.get("running", False))
    known = bool(launch.get("known", False))
    elapsed = float(launch.get("elapsed", 0.0) or 0.0)
    grace = PROFILE_GRACE_SECONDS[subsystem]

    if not known or desired is None:
        return HealthCheck(
            subsystem, "Launch session", "unknown", "State not known yet"
        )
    if desired and running:
        return HealthCheck(
            subsystem, "Launch session", "healthy", "Running as requested"
        )
    if desired and not running:
        if elapsed <= grace:
            return HealthCheck(
                subsystem, "Launch session", "starting", "Starting"
            )
        return HealthCheck(
            subsystem,
            "Launch session",
            "error",
            "Stopped unexpectedly",
        )
    if not desired and running:
        if elapsed <= grace:
            return HealthCheck(
                subsystem, "Launch session", "starting", "Stopping"
            )
        return HealthCheck(
            subsystem,
            "Launch session",
            "warning",
            "Still running after Stop; possible orphan session",
        )
    return HealthCheck(
        subsystem, "Launch session", "inactive", "Stopped intentionally"
    )


def evaluate_health(
    snapshot: Optional[Dict],
    launch_states: Dict[str, Dict],
    connected: bool,
    previously_healthy: Optional[Set[str]] = None,
) -> List[HealthCheck]:
    """Evaluate a probe snapshot against the GUI's requested launch state."""
    if not connected:
        return [
            HealthCheck(
                "Connection",
                "Jetson health probe",
                "unknown",
                "SSH unavailable; remote health cannot be determined",
            )
        ]
    if snapshot is None:
        return [
            HealthCheck(
                "Connection",
                "Jetson health probe",
                "starting",
                "Waiting for the first health snapshot",
            )
        ]

    previously_healthy = previously_healthy or set()
    checks: List[HealthCheck] = []
    for subsystem in ("Bringup", "Localization", "Mapping", "Nav2"):
        launch = launch_states.get(subsystem.lower(), {})
        session = _session_check(subsystem, launch)
        checks.append(session)
        if launch.get("desired") is not True:
            continue

        elapsed = float(launch.get("elapsed", 0.0) or 0.0)
        in_grace = elapsed <= PROFILE_GRACE_SECONDS[subsystem]
        checks.extend(_node_checks(subsystem, snapshot, in_grace))
        checks.extend(_topic_checks(subsystem, snapshot, in_grace))
        checks.extend(_lifecycle_checks(subsystem, snapshot, in_grace))

        if subsystem == "Bringup":
            checks.append(_transform_check(
                subsystem,
                snapshot,
                "odom_base",
                "odom → base_link",
                in_grace,
                previously_healthy,
            ))
            checks.append(_transform_check(
                subsystem,
                snapshot,
                "base_lidar",
                "base_link → lidar_scan_link",
                in_grace,
                previously_healthy,
            ))
        elif subsystem == "Localization":
            checks.append(_transform_check(
                subsystem,
                snapshot,
                "map_base",
                "map → base_link",
                in_grace,
                previously_healthy,
                initial_pose_wait=True,
            ))
        elif subsystem == "Mapping":
            checks.append(_transform_check(
                subsystem,
                snapshot,
                "map_base",
                "map → base_link",
                in_grace,
                previously_healthy,
            ))
        elif subsystem == "Nav2":
            action_ready = bool(snapshot.get("actions", {}).get(
                "navigate_to_pose", False
            ))
            checks.append(HealthCheck(
                subsystem,
                "NavigateToPose action",
                "healthy" if action_ready else _missing_state(in_grace),
                "Ready" if action_ready else "Action server unavailable",
            ))
    return checks


def overall_health(checks: Iterable[HealthCheck]):
    """Return overall state and compact counts for a set of checks."""
    checks = list(checks)
    counts = {
        state: sum(check.state == state for check in checks)
        for state in (
            "error", "warning", "starting", "healthy", "inactive", "unknown"
        )
    }
    if counts["error"]:
        state = "error"
    elif counts["warning"]:
        state = "warning"
    elif counts["starting"]:
        state = "starting"
    elif counts["unknown"] and not counts["healthy"]:
        state = "unknown"
    else:
        state = "healthy"
    return state, counts
