"""Keyboard teleoperation using true key-down and key-up events."""

import threading

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy

try:
    from pynput import keyboard
except ImportError as error:
    raise ImportError(
        'amr_teleop needs pynput. Install it with: sudo apt install python3-pynput'
    ) from error


HELP_TEXT = """
AMR keyboard teleoperation

  Hold w             forward; release to stop forward motion
  Hold s             reverse; release to stop reverse motion
  Hold a / d         rotate left / rotate right; release to stop turning
  space or x         stop immediately
  q                  stop and quit

Key-down starts a command. Key-up stops that part of the command immediately.
You may hold w+a or w+d to drive in an arc.
"""


class KeyboardTeleop(Node):
    """Publish /cmd_vel from real desktop keyboard press/release events."""

    def __init__(self):
        super().__init__('keyboard_teleop')

        self.declare_parameter('cmd_vel_topic', 'cmd_vel')
        self.declare_parameter('linear_speed_mps', 0.10)
        self.declare_parameter('angular_speed_radps', 0.80)
        self.declare_parameter('publish_rate_hz', 20.0)

        self._topic = self.get_parameter('cmd_vel_topic').value
        self._linear_speed = self.get_parameter('linear_speed_mps').value
        self._angular_speed = self.get_parameter('angular_speed_radps').value
        rate_hz = self.get_parameter('publish_rate_hz').value
        if rate_hz <= 0.0:
            raise ValueError('publish_rate_hz must be greater than zero')

        # Only the newest desired motion is useful. Depth 1 prevents a stale
        # key command from being delivered after a newer stop command.
        cmd_vel_qos = QoSProfile(
            depth=1, reliability=QoSReliabilityPolicy.RELIABLE)
        self._publisher = self.create_publisher(Twist, self._topic, cmd_vel_qos)

        # pynput calls the two callbacks on its listener thread, while this
        # ROS node publishes from its timer thread. Protect shared key state.
        self._key_lock = threading.Lock()
        self._pressed_motion_keys = set()
        self._quit_requested = False

        # Unlike a terminal reader, pynput receives both press and release
        # events. It therefore knows whether w/a/s/d is down right now.
        self._listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release)
        self._listener.start()

        # Re-publish while a key remains down. This refreshes the command
        # timeout in amr_driver and then the independent STM32 timeout.
        self._timer = self.create_timer(1.0 / rate_hz, self._publish_current_command)

        print(HELP_TEXT)
        self.get_logger().info(
            f'Publishing press/release teleop commands on /{self._topic.lstrip("/")}')

    @staticmethod
    def _key_character(key):
        """Return a lower-case printable key, or None for special keys."""
        try:
            return key.char.lower() if key.char is not None else None
        except AttributeError:
            return None

    def _on_key_press(self, key):
        """Record a key-down event; auto-repeat does not change the set."""
        character = self._key_character(key)
        with self._key_lock:
            if character in ('w', 'a', 's', 'd'):
                self._pressed_motion_keys.add(character)
            elif character == 'q':
                self._pressed_motion_keys.clear()
                self._quit_requested = True
            elif character == 'x' or key == keyboard.Key.space:
                # An explicit stop disarms all directions. A direction still
                # physically held must be released and pressed again to move.
                self._pressed_motion_keys.clear()
        self._publish_current_command()

    def _on_key_release(self, key):
        """Remove a released direction immediately, then publish the result."""
        character = self._key_character(key)
        if character in ('w', 'a', 's', 'd'):
            with self._key_lock:
                self._pressed_motion_keys.discard(character)
            self._publish_current_command()

    def _current_command(self):
        """Build the Twist represented by the keys currently held down."""
        with self._key_lock:
            keys = self._pressed_motion_keys.copy()

        command = Twist()
        if 'w' in keys:
            command.linear.x += self._linear_speed
        if 's' in keys:
            command.linear.x -= self._linear_speed
        if 'a' in keys:
            command.angular.z += self._angular_speed
        if 'd' in keys:
            command.angular.z -= self._angular_speed
        return command

    def _publish_current_command(self):
        """Publish from the current key state and handle a requested exit."""
        with self._key_lock:
            quit_requested = self._quit_requested
        if quit_requested:
            self._publisher.publish(Twist())
            self.get_logger().info('Quit requested; stop command sent.')
            rclpy.shutdown()
            return
        self._publisher.publish(self._current_command())

    def destroy_node(self):
        """Stop the robot and stop the desktop keyboard listener on exit."""
        try:
            if rclpy.ok():
                self._publisher.publish(Twist())
            self._listener.stop()
            self._listener.join(timeout=1.0)
        finally:
            return super().destroy_node()


def main(args=None):
    """Console-script entry point declared by setup.py."""
    rclpy.init(args=args)
    node = KeyboardTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
