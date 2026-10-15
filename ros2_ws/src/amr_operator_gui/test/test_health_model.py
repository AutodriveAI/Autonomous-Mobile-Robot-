from amr_operator_gui.health_model import evaluate_health, overall_health


def launch_state(desired, running, elapsed=100.0, known=True):
    return {
        "desired": desired,
        "running": running,
        "known": known,
        "elapsed": elapsed,
    }


def stopped_launches():
    return {
        name: launch_state(False, False)
        for name in ("bringup", "localization", "mapping", "nav2")
    }


def complete_bringup_snapshot():
    nodes = [
        "/amr_driver_node",
        "/robot_state_publisher",
        "/rplidar_node",
        "/joy_node",
        "/joy_teleop",
        "/twist_mux",
        "/camera/camera",
        "/lcd_status",
    ]
    publishers = {
        topic: 1
        for topic in (
            "/odom",
            "/scan",
            "/joint_states",
            "/robot_description",
            "/camera_rgb",
            "/cmd_vel",
        )
    }
    return {
        "nodes": nodes,
        "publishers": publishers,
        "topic_age": {
            "/odom": 0.1,
            "/scan": 0.1,
            "/joint_states": 0.1,
        },
        "lifecycle": {},
        "transforms": {
            "odom_base": {"available": True, "age": 0.1},
            "base_lidar": {"available": True, "age": None},
        },
        "actions": {},
    }


def test_intentionally_stopped_profiles_do_not_report_missing_resources():
    checks = evaluate_health({}, stopped_launches(), connected=True)

    assert len(checks) == 4
    assert {check.state for check in checks} == {"inactive"}


def test_unexpected_session_exit_is_an_error_after_grace_period():
    launches = stopped_launches()
    launches["bringup"] = launch_state(True, False, elapsed=30.0)

    checks = evaluate_health({}, launches, connected=True)

    session = next(
        check for check in checks
        if check.subsystem == "Bringup" and check.name == "Launch session"
    )
    assert session.state == "error"
    assert "unexpectedly" in session.detail


def test_missing_resources_are_starting_during_grace_not_errors():
    launches = stopped_launches()
    launches["bringup"] = launch_state(True, True, elapsed=3.0)

    checks = evaluate_health({}, launches, connected=True)

    assert not [check for check in checks if check.state == "error"]
    assert [check for check in checks if check.state == "starting"]


def test_complete_bringup_is_healthy():
    launches = stopped_launches()
    launches["bringup"] = launch_state(True, True)

    checks = evaluate_health(
        complete_bringup_snapshot(), launches, connected=True
    )

    bringup = [check for check in checks if check.subsystem == "Bringup"]
    assert bringup
    assert {check.state for check in bringup} == {"healthy"}


def test_localization_tf_waits_for_initial_pose_then_detects_loss():
    launches = stopped_launches()
    launches["localization"] = launch_state(True, True)
    snapshot = {
        "nodes": [
            "/map_server",
            "/amcl",
            "/lifecycle_manager_localization",
        ],
        "publishers": {"/map": 1, "/amcl_pose": 1},
        "lifecycle": {"map_server": "active", "amcl": "active"},
        "transforms": {"map_base": {"available": False, "age": None}},
    }

    checks = evaluate_health(snapshot, launches, connected=True)
    transform = next(
        check for check in checks if check.name == "map → base_link"
    )
    assert transform.state == "warning"

    checks = evaluate_health(
        snapshot,
        launches,
        connected=True,
        previously_healthy={"Localization/map → base_link"},
    )
    transform = next(
        check for check in checks if check.name == "map → base_link"
    )
    assert transform.state == "error"


def test_disconnected_state_is_unknown_without_false_component_errors():
    checks = evaluate_health(None, stopped_launches(), connected=False)
    state, counts = overall_health(checks)

    assert state == "unknown"
    assert counts["error"] == 0
