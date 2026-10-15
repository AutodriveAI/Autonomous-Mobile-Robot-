"""Tests for comment-preserving parameter tuning documents."""

import pytest

from amr_operator_gui.parameter_tuning import ParameterDocument, apply_policy


SAMPLE = """controller_server:
  ros__parameters:
    # Main loop rate.
    controller_frequency: 10.0
    goal_checker:
      # Final heading tolerance.
      yaw_goal_tolerance: 0.15 # old value
    FollowPath:
      # Maximum turn speed.
      max_vel_theta: 6.0
      critics:
        - RotateToGoal
        - Oscillation
"""


def test_parser_preserves_yaml_order_sections_and_descriptions():
    document = ParameterDocument("nav2_params_real.yaml", SAMPLE)

    assert [entry.name for entry in document.entries] == [
        "controller_frequency",
        "goal_checker.yaw_goal_tolerance",
        "FollowPath.max_vel_theta",
        "FollowPath.critics",
    ]
    assert document.entries[1].section == "Goal checker"
    assert document.entries[2].section == "Path following (FollowPath)"
    assert document.entries[2].description == "Maximum turn speed."


def test_scalar_edit_preserves_comments_and_unrelated_formatting():
    document = ParameterDocument("nav2_params_real.yaml", SAMPLE)
    entry = document.entries[2]

    document.stage(entry.identifier, "5.5")
    rendered = document.render()

    assert "max_vel_theta: 5.5" in rendered
    assert "# Maximum turn speed." in rendered
    assert "yaw_goal_tolerance: 0.15 # old value" in rendered
    assert document.dirty


def test_wrong_scalar_type_is_rejected():
    document = ParameterDocument("nav2_params_real.yaml", SAMPLE)

    with pytest.raises(ValueError, match="numeric"):
        document.stage(document.entries[0].identifier, "false")


def test_complex_values_are_visible_but_read_only():
    document = ParameterDocument("nav2_params_real.yaml", SAMPLE)
    critics = document.entries[-1]

    assert not critics.editable
    with pytest.raises(ValueError, match="read-only"):
        document.stage(critics.identifier, "[]")


def test_foxy_live_policy_is_conservative():
    live = apply_policy(
        "nav2_params_real.yaml",
        "/controller_server",
        "FollowPath.max_vel_theta",
    )
    restart = apply_policy(
        "nav2_params_real.yaml",
        "/controller_server",
        "goal_checker.yaw_goal_tolerance",
    )

    assert live.mode == "live"
    assert restart.mode == "restart"
    assert restart.owner == "nav2"
