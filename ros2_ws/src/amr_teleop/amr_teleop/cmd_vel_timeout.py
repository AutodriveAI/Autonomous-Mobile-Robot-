"""Safety timeout for velocity commands.

This node sits between a velocity-command source, such as keyboard teleop, and
the robot/simulator driver.

Normal simulation path:

  teleop publishes       /cmd_vel_raw
  this node subscribes   /cmd_vel_raw
  this node publishes    /cmd_vel
  Gazebo listens to      /cmd_vel

Why this exists:

  The real STM32 firmware stops the motors when fresh serial commands stop
  arriving. The classic Gazebo diff-drive plugin does not automatically behave
  exactly like that, so this node gives the simulator the same safety idea.

Behavior:

  - Every received Twist command is forwarded immediately.
  - If no fresh command arrives for timeout_s seconds, one zero Twist is sent.
  - After that single stop message, the node stays quiet until a fresh command
    arrives again.
"""

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node


class CmdVelTimeout(Node):
    """Forward Twist commands, but publish zero after a silence timeout."""

    def __init__(self) -> None:
        super().__init__('cmd_vel_timeout')

        self.declare_parameter('input_topic', '/cmd_vel_raw')
        self.declare_parameter('output_topic', '/cmd_vel')
        self.declare_parameter('timeout_s', 0.2)
        self.declare_parameter('check_period_s', 0.02)

        input_topic = (
            self.get_parameter('input_topic').get_parameter_value().string_value
        )
        output_topic = (
            self.get_parameter('output_topic').get_parameter_value().string_value
        )
        self._timeout_s = (
            self.get_parameter('timeout_s').get_parameter_value().double_value
        )
        check_period_s = (
            self.get_parameter('check_period_s').get_parameter_value().double_value
        )

        self._last_command_time = self.get_clock().now()
        self._timed_out = True

        self._publisher = self.create_publisher(Twist, output_topic, 10)
        self._subscription = self.create_subscription(
            Twist,
            input_topic,
            self._cmd_vel_callback,
            10,
        )
        self._timer = self.create_timer(check_period_s, self._timeout_callback)

        self.get_logger().info(
            f'Forwarding {input_topic} -> {output_topic} with '
            f'{self._timeout_s:.3f} s timeout'
        )

    def _cmd_vel_callback(self, msg: Twist) -> None:
        """Forward each fresh command immediately."""
        self._last_command_time = self.get_clock().now()
        self._timed_out = False
        self._publisher.publish(msg)

    def _timeout_callback(self) -> None:
        """Publish zero velocity when command input has gone stale."""
        elapsed_s = (
            self.get_clock().now() - self._last_command_time
        ).nanoseconds / 1_000_000_000.0

        if elapsed_s < self._timeout_s:
            return

        if self._timed_out:
            return

        stop_msg = Twist()
        self._publisher.publish(stop_msg)
        self.get_logger().warn(
            f'No fresh velocity command for {elapsed_s:.3f} s; '
            'publishing one stop command'
        )
        self._timed_out = True


def main(args=None) -> None:
    """Run the command timeout node."""
    rclpy.init(args=args)
    node = CmdVelTimeout()

    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
