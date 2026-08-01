"""ROS 2 node connecting the AMR's ROS topics to its STM32 firmware.

Responsibilities
-----------------
1. Subscribe to geometry_msgs/Twist on `cmd_vel_topic`, convert to per-wheel
   ticks/s using standard differential-drive kinematics, and stream `V,l,r`
   commands to the STM32 at `publish_rate_hz`.
2. Enforce a Jetson-side watchdog (`cmd_vel_timeout_s`) independent of the
   firmware's own 20 s command timeout -- this one is meant to actually be
   tight enough to matter if the driving process dies or the topic stalls.
3. Parse signed total encoder ticks from the firmware and republish them as
   nav_msgs/Odometry (+ TF) and sensor_msgs/JointState.

The STM32 currently has single-channel encoders, so it signs each new tick
using the active wheel command direction. ROS receives signed total tick
positions and calculates deltas between samples; this gives correct wheel
joint positions for RViz and more stable odometry than integrating rounded
ticks/s telemetry.
"""

import rclpy
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster

from amr_driver.differential_drive import DifferentialDriveKinematics
from amr_driver.odometry import DifferentialDriveOdometry
from amr_driver.stm32_transport import Stm32Transport, Telemetry


class AmrDriverNode(Node):

    def __init__(self):
        # The ROS node name appears in `ros2 node list` and log messages.
        super().__init__('amr_driver_node')

        # Parameters make dimensions/ports configurable without editing Python.
        self._declare_parameters()
        p = self._read_parameters()
        self._p = p

        if p['wheel_radius_m'] <= 0.0 or p['wheel_separation_m'] <= 0.0:
            self.get_logger().warn(
                'wheel_radius_m / wheel_separation_m have not been set to '
                'real measured values (see config/amr_driver.yaml). '
                'Odometry and cmd_vel scaling will be wrong until you do.'
            )

        # cmd_vel -> target ticks/s. The subscription stores the newest desired
        # wheel rates; a periodic timer sends them at a steady rate. Separating
        # these jobs prevents a bursty cmd_vel publisher from flooding UART.
        self._target_left_ticks = 0
        self._target_right_ticks = 0
        self._last_cmd_vel_time = self.get_clock().now()
        # Used only for readable diagnostics: log a V command when its value
        # changes, not every 1 / publish_rate_hz timer tick.
        self._last_logged_velocity_command = None
        self._last_logged_cmd_vel_command = None
        # Used for the actual serial link: do not send identical V commands
        # repeatedly.  The STM32 firmware holds the last wheel target, so once
        # V,0,0 has been sent, sending the same stop command again only clogs
        # the serial link and hides useful replies/telemetry.
        self._last_sent_velocity_command = None

        # Keep robot geometry and pose integration outside this ROS-facing
        # class. That makes the mathematical parts independently testable.
        self._kinematics = DifferentialDriveKinematics(
            p['wheel_radius_m'], p['wheel_separation_m'], p['ticks_per_revolution'])
        self._odometry = DifferentialDriveOdometry(self._kinematics)

        # Wheel feedback is frequent and becomes obsolete quickly. BEST_EFFORT
        # avoids retransmitting stale odometry if a message is missed.
        best_effort_qos = QoSProfile(
            depth=10, reliability=QoSReliabilityPolicy.BEST_EFFORT)
        # Velocity commands are state, not a history to replay. If several
        # arrive before this callback runs, discard the older ones and retain
        # only the newest desired robot motion.
        cmd_vel_qos = QoSProfile(
            depth=1, reliability=QoSReliabilityPolicy.RELIABLE)

        self._cmd_vel_sub = self.create_subscription(
            Twist, p['cmd_vel_topic'], self._cmd_vel_callback, cmd_vel_qos)
        self._odom_pub = self.create_publisher(
            Odometry, p['odom_topic'], best_effort_qos)
        self._joint_state_pub = self.create_publisher(
            JointState, 'joint_states', best_effort_qos)
        self._tf_broadcaster = (
            TransformBroadcaster(self) if p['publish_tf'] else None)

        # Open serial only after all publishers/subscribers used by telemetry
        # callbacks exist. Stm32Transport starts a background reader thread
        # immediately, and the STM32 may send telemetry before __init__ returns.
        self._transport = Stm32Transport(
            port=p['serial_port'],
            baud=p['baud_rate'],
            on_telemetry=self._on_telemetry,
            on_reply=self._on_reply,
        )

        # This timer continually refreshes the STM32's command watchdog.
        period_s = 1.0 / p['publish_rate_hz']
        self._command_timer = self.create_timer(period_s, self._command_timer_callback)

        self.get_logger().info(
            f"amr_driver connected on {p['serial_port']} @ {p['baud_rate']} baud"
        )

    # -- parameters -----------------------------------------------------

    def _declare_parameters(self) -> None:
        """Declare every launch/YAML configurable value with a safe default."""
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('cmd_vel_topic', 'cmd_vel')
        self.declare_parameter('odom_topic', 'odom')
        self.declare_parameter('odom_frame_id', 'odom')
        self.declare_parameter('base_frame_id', 'base_link')
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('cmd_vel_timeout_s', 0.5)
        # TODO: replace with your robot's real measured values.
        self.declare_parameter('wheel_radius_m', 0.0)
        self.declare_parameter('wheel_separation_m', 0.0)
        # HC-020K single-channel encoder with a 20-slit disk. The old
        self.declare_parameter('ticks_per_revolution', 20)
        self.declare_parameter('max_ticks_per_second', 200.0)

    def _read_parameters(self) -> dict:
        """Copy ROS parameter values into one convenient immutable-by-convention dict."""
        g = self.get_parameter
        return {
            'serial_port': g('serial_port').value,
            'baud_rate': g('baud_rate').value,
            'cmd_vel_topic': g('cmd_vel_topic').value,
            'odom_topic': g('odom_topic').value,
            'odom_frame_id': g('odom_frame_id').value,
            'base_frame_id': g('base_frame_id').value,
            'publish_tf': g('publish_tf').value,
            'publish_rate_hz': g('publish_rate_hz').value,
            'cmd_vel_timeout_s': g('cmd_vel_timeout_s').value,
            'wheel_radius_m': g('wheel_radius_m').value,
            'wheel_separation_m': g('wheel_separation_m').value,
            'ticks_per_revolution': g('ticks_per_revolution').value,
            'max_ticks_per_second': g('max_ticks_per_second').value,
        }

    # -- cmd_vel -> firmware ---------------------------------------------

    def _cmd_vel_callback(self, msg: Twist) -> None:
        """Turn ROS linear/angular velocity into left/right wheel targets."""
        p = self._p
        # This module owns the standard differential-drive equations; this
        # callback only connects a ROS Twist to the STM32 command protocol.
        targets = self._kinematics.cmd_vel_to_ticks(msg.linear.x, msg.angular.z)
        left_ticks = targets.left
        right_ticks = targets.right

        # Keep the ROS-side request inside the firmware's accepted V-command
        # range. This is a second layer of protection, not a replacement for
        # the STM32's own clamp.
        limit = p['max_ticks_per_second']
        left_ticks = max(-limit, min(limit, left_ticks))
        right_ticks = max(-limit, min(limit, right_ticks))

        # Firmware protocol carries integers. int() truncates fractional
        # ticks/s, which is acceptable at the current 20 ticks/revolution.
        self._target_left_ticks = int(left_ticks)
        self._target_right_ticks = int(right_ticks)
        self._last_cmd_vel_time = self.get_clock().now()
        command = (self._target_left_ticks, self._target_right_ticks)
        if command != self._last_logged_cmd_vel_command:
            self.get_logger().info(
                'cmd_vel linear.x=%.3f m/s angular.z=%.3f rad/s -> '
                'raw ticks L=%.1f R=%.1f -> command V,%d,%d' % (
                    msg.linear.x,
                    msg.angular.z,
                    targets.left,
                    targets.right,
                    self._target_left_ticks,
                    self._target_right_ticks,
                )
            )
            self._last_logged_cmd_vel_command = command

    def _command_timer_callback(self) -> None:
        """Refresh the MCU command or send a stop after cmd_vel goes stale."""
        elapsed = (self.get_clock().now() - self._last_cmd_vel_time).nanoseconds / 1e9
        if elapsed > self._p['cmd_vel_timeout_s']:
            # No fresh cmd_vel recently: fail safe rather than trust the
            # firmware's currently much longer 10 s timeout.
            self._send_velocity_command(0, 0)
            return
        self._send_velocity_command(
            self._target_left_ticks, self._target_right_ticks)

    def _send_velocity_command(self, left_ticks: int, right_ticks: int) -> None:
        """Send a V command only when the requested value changes."""
        command = (left_ticks, right_ticks)
        if command == self._last_sent_velocity_command:
            return

        if command != self._last_logged_velocity_command:
            self.get_logger().info(
                f'Sending STM32 command: V,{left_ticks},{right_ticks} ticks/s')
            self._last_logged_velocity_command = command
        self._transport.send_velocity(left_ticks, right_ticks)
        self._last_sent_velocity_command = command

    # -- firmware -> odometry / joint states -----------------------------

    def _on_reply(self, line: str) -> None:
        """Forward human-readable STM32 replies (PID, OK, ERR) to ROS logs."""
        self.get_logger().info(f'STM32: {line}')

    def _on_telemetry(self, telemetry: Telemetry) -> None:
        # NOTE: runs on the Stm32Transport reader thread, not the executor thread.
        # rclpy Publisher.publish() and TransformBroadcaster.sendTransform()
        # are safe to call directly from another thread.
        state = self._odometry.update(
            telemetry.left_ticks, telemetry.right_ticks,
            telemetry.time_ms, telemetry.stamp)
        self._publish_odometry(state.linear_velocity, state.angular_velocity)
        self._publish_joint_states()

    def _publish_odometry(self, linear_v: float, angular_v: float) -> None:
        """Publish nav_msgs/Odometry and, optionally, the matching odom->base TF."""
        p = self._p
        now = self.get_clock().now().to_msg()
        quat = self._odometry.orientation_quaternion()

        # ROS convention: pose is odom_frame -> base_frame; twist is the base
        # velocity expressed in the child/base frame.
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = p['odom_frame_id']
        odom.child_frame_id = p['base_frame_id']
        odom.pose.pose.position.x = self._odometry.x
        odom.pose.pose.position.y = self._odometry.y
        odom.pose.pose.orientation = quat
        odom.twist.twist.linear.x = linear_v
        odom.twist.twist.angular.z = angular_v
        self._odom_pub.publish(odom)

        if self._tf_broadcaster is not None:
            tf_msg = TransformStamped()
            tf_msg.header.stamp = now
            tf_msg.header.frame_id = p['odom_frame_id']
            tf_msg.child_frame_id = p['base_frame_id']
            tf_msg.transform.translation.x = self._odometry.x
            tf_msg.transform.translation.y = self._odometry.y
            tf_msg.transform.rotation = quat
            self._tf_broadcaster.sendTransform(tf_msg)

    def _publish_joint_states(self) -> None:
        """Publish wheel rotation angles for robot_state_publisher and RViz."""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        # These names must exactly match <joint name="..."> in the URDF.
        # Otherwise robot_state_publisher receives the positions but has no
        # matching joints to animate in RViz.
        msg.name = [self._odometry.left_wheel_joint, self._odometry.right_wheel_joint]
        msg.position = [self._odometry.left_wheel_angle, self._odometry.right_wheel_angle]
        msg.velocity = [
            self._odometry.left_wheel_velocity,
            self._odometry.right_wheel_velocity,
        ]
        self._joint_state_pub.publish(msg)

    # -- lifecycle --------------------------------------------------------

    def destroy_node(self) -> bool:
        """Ask the MCU to stop before closing serial during ROS shutdown."""
        try:
            self._transport.stop()
        finally:
            self._transport.close()
        return super().destroy_node()


def main(args=None):
    """ROS 2 console-script entry point declared by setup.py."""
    rclpy.init(args=args)
    node = AmrDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
