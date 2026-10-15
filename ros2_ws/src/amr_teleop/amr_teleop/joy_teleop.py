"""Logitech-style gamepad teleoperation for the AMR.

This node listens to ``sensor_msgs/Joy`` messages from the standard ROS 2
``joy_node`` driver and publishes ``geometry_msgs/Twist`` commands on
``/cmd_vel``.

The important design choice is that the user-facing speed parameters are in
encoder ticks per second, not meters per second.  Our STM32 ultimately receives:

    V,<left_ticks_per_second>,<right_ticks_per_second>

through ``amr_driver``.  So for manual driving it is easier to say:

    full-stick forward -> about 100 ticks/s on both wheels

This node converts that tick target into the equivalent Twist using the wheel
radius, wheel separation, and encoder ticks per revolution.
"""

import math
from typing import Optional, Sequence

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Joy


def _axis_value(axes: Sequence[float], index: int) -> float:
    """Return one joystick axis safely, or 0.0 if the index is not present."""
    if index < 0 or index >= len(axes):
        return 0.0
    return float(axes[index])


def _button_pressed(buttons: Sequence[int], index: int) -> bool:
    """Return True when a configured button exists and is pressed."""
    if index < 0 or index >= len(buttons):
        return False
    return bool(buttons[index])


def _apply_deadband(value: float, deadband: float) -> float:
    """Suppress tiny joystick noise around center position."""
    if abs(value) < deadband:
        return 0.0
    return value


class JoyTeleop(Node):
    """Convert Logitech gamepad axes into AMR velocity commands."""

    def __init__(self) -> None:
        super().__init__('joy_teleop')

        # Topics.  joy_node publishes /joy; amr_driver subscribes /cmd_vel.
        self.declare_parameter('joy_topic', 'joy')
        self.declare_parameter('cmd_vel_topic', 'cmd_vel')

        # Logitech-style default mapping:
        #   axes[1] = left stick vertical
        #   axes[0] = left stick horizontal
        # If your Logitech mode switch changes signs/axes, override these from
        # launch or the command line instead of editing code.
        self.declare_parameter('linear_axis', 1)
        self.declare_parameter('angular_axis', 0)
        self.declare_parameter('linear_axis_sign', 1.0)
        self.declare_parameter('angular_axis_sign', 1.0)

        # Optional buttons. Bringup configures the Logitech left bumper
        # (button 4) as the deadman; the standalone node keeps -1 as a safe,
        # backwards-compatible default unless explicitly configured.
        self.declare_parameter('enable_button', -1)
        self.declare_parameter('stop_button', -1)

        # Full stick deflection maps to these wheel target speeds.  The default
        # 100 ticks/s means:
        #   - forward stick: left and right wheels target about +100 ticks/s
        #   - turn stick: one wheel about +100 ticks/s, the other about -100
        self.declare_parameter('speed_ticks_per_second', 100.0)
        self.declare_parameter('turn_ticks_per_second', 100.0)

        # Same robot geometry used by amr_driver.  These let us convert the
        # tick-based human parameters into a standard Twist.
        self.declare_parameter('wheel_radius_m', 0.0325)
        self.declare_parameter('wheel_separation_m', 0.175)
        self.declare_parameter('ticks_per_revolution', 20.0)

        # Runtime behavior.
        self.declare_parameter('deadband', 0.08)
        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('joy_timeout_s', 0.5)

        self._joy_topic = self.get_parameter('joy_topic').value
        self._cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        self._linear_axis = int(self.get_parameter('linear_axis').value)
        self._angular_axis = int(self.get_parameter('angular_axis').value)
        self._linear_axis_sign = float(self.get_parameter('linear_axis_sign').value)
        self._angular_axis_sign = float(self.get_parameter('angular_axis_sign').value)
        self._enable_button = int(self.get_parameter('enable_button').value)
        self._stop_button = int(self.get_parameter('stop_button').value)
        self._speed_ticks_per_second = float(
            self.get_parameter('speed_ticks_per_second').value)
        self._turn_ticks_per_second = float(
            self.get_parameter('turn_ticks_per_second').value)
        self._wheel_radius_m = float(self.get_parameter('wheel_radius_m').value)
        self._wheel_separation_m = float(
            self.get_parameter('wheel_separation_m').value)
        self._ticks_per_revolution = float(
            self.get_parameter('ticks_per_revolution').value)
        self._deadband = float(self.get_parameter('deadband').value)
        self._joy_timeout_s = float(self.get_parameter('joy_timeout_s').value)

        publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        timer_period_s = 1.0 / publish_rate_hz if publish_rate_hz > 0.0 else 0.05

        # Store the latest joystick message.  The timer publishes at a steady
        # rate so serial/driver commands are smooth and predictable.
        self._latest_joy: Optional[Joy] = None
        self._last_joy_time = self.get_clock().now()
        self._last_published_zero = False

        qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
        )
        self._joy_sub = self.create_subscription(
            Joy, self._joy_topic, self._joy_callback, qos)
        self._cmd_pub = self.create_publisher(Twist, self._cmd_vel_topic, 1)
        self._timer = self.create_timer(timer_period_s, self._timer_callback)

        self.get_logger().info(
            'joy_teleop: /%s -> /%s, full stick = %.1f ticks/s straight, '
            '%.1f ticks/s turn, deadman button = %d' % (
                self._joy_topic,
                self._cmd_vel_topic,
                self._speed_ticks_per_second,
                self._turn_ticks_per_second,
                self._enable_button,
            )
        )

    def _joy_callback(self, msg: Joy) -> None:
        """Remember the newest gamepad state."""
        self._latest_joy = msg
        self._last_joy_time = self.get_clock().now()

    def _timer_callback(self) -> None:
        """Publish the latest joystick command, or one stop on timeout."""
        now = self.get_clock().now()
        age_s = (now - self._last_joy_time).nanoseconds / 1e9

        if self._latest_joy is None or age_s > self._joy_timeout_s:
            self._publish_stop_once()
            return

        twist = self._twist_from_joy(self._latest_joy)
        if self._is_zero_twist(twist):
            self._publish_stop_once()
            return

        self._cmd_pub.publish(twist)
        self._last_published_zero = False

    def _twist_from_joy(self, joy: Joy) -> Twist:
        """Convert joystick axes/buttons into a Twist command."""
        if _button_pressed(joy.buttons, self._stop_button):
            return Twist()

        if self._enable_button >= 0 and not _button_pressed(
                joy.buttons, self._enable_button):
            return Twist()

        linear_axis = _axis_value(joy.axes, self._linear_axis)
        angular_axis = _axis_value(joy.axes, self._angular_axis)

        linear_axis = _apply_deadband(
            linear_axis * self._linear_axis_sign, self._deadband)
        angular_axis = _apply_deadband(
            angular_axis * self._angular_axis_sign, self._deadband)

        twist = Twist()
        twist.linear.x = linear_axis * self._ticks_per_second_to_mps(
            self._speed_ticks_per_second)
        twist.angular.z = angular_axis * self._turn_ticks_per_second_to_radps(
            self._turn_ticks_per_second)
        return twist

    def _ticks_per_second_to_mps(self, ticks_per_second: float) -> float:
        """Convert wheel encoder ticks/s into wheel ground speed in m/s."""
        if self._ticks_per_revolution <= 0.0:
            return 0.0
        circumference_m = 2.0 * math.pi * self._wheel_radius_m
        return ticks_per_second * circumference_m / self._ticks_per_revolution

    def _turn_ticks_per_second_to_radps(self, ticks_per_second: float) -> float:
        """Convert opposite wheel tick targets into robot yaw rate."""
        if self._wheel_separation_m <= 0.0:
            return 0.0
        wheel_speed_mps = self._ticks_per_second_to_mps(ticks_per_second)
        return 2.0 * wheel_speed_mps / self._wheel_separation_m

    def _publish_stop_once(self) -> None:
        """Publish one zero command, then stay quiet until input changes."""
        if self._last_published_zero:
            return
        self._cmd_pub.publish(Twist())
        self._last_published_zero = True

    @staticmethod
    def _is_zero_twist(twist: Twist) -> bool:
        """Return True when the command contains no planar motion."""
        return twist.linear.x == 0.0 and twist.angular.z == 0.0


def main() -> None:
    rclpy.init()
    node = JoyTeleop()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
