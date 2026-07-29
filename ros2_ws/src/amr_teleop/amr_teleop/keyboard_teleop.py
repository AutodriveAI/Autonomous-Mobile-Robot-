"""AMR defaults for the standard teleop_twist_keyboard node.

This wrapper intentionally does not implement custom keyboard handling.  It
only sets project-specific default parameters, then calls the standard ROS 2
``teleop_twist_keyboard`` main function.

Measured physical AMR bring-up values:
  - speed = 0.25 m/s: minimum useful forward/backward teleop speed
  - turn  = 2.27 rad/s: minimum useful turning teleop command

Both values can still be overridden from the command line with normal ROS
parameters, for example:

  ros2 run amr_teleop keyboard_teleop --ros-args -p speed:=0.15 -p turn:=1.0
"""

import sys

from teleop_twist_keyboard import main as teleop_twist_keyboard_main


def _has_parameter_override(parameter_name: str) -> bool:
    """Return True if sys.argv already contains ``-p name:=...``."""
    parameter_prefix = f'{parameter_name}:='
    return any(argument.startswith(parameter_prefix) for argument in sys.argv)


def _append_default_parameter(parameter_name: str, value: float) -> None:
    """Append a ROS parameter override only when the user did not provide one."""
    if _has_parameter_override(parameter_name):
        return

    if '--ros-args' not in sys.argv:
        sys.argv.append('--ros-args')

    sys.argv.extend(['-p', f'{parameter_name}:={value}'])


def main() -> None:
    """Run standard keyboard teleop with AMR-specific speed defaults."""
    _append_default_parameter('speed', 0.25)
    _append_default_parameter('turn', 2.27)
    teleop_twist_keyboard_main()
