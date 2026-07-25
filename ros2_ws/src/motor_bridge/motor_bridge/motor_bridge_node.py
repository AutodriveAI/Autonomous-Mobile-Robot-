"""ROS 2 node bridging /cmd_vel <-> the STM32 differential-drive firmware.

Responsibilities
-----------------
1. Subscribe to geometry_msgs/Twist on `cmd_vel_topic`, convert to per-wheel
   ticks/s using standard differential-drive kinematics, and stream `V,l,r`
   commands to the STM32 at `publish_rate_hz`.
2. Enforce a Jetson-side watchdog (`cmd_vel_timeout_s`) independent of the
   firmware's own 20 s command timeout -- this one is meant to actually be
   tight enough to matter if the driving process dies or the topic stalls.
3. Parse telemetry lines from the firmware and republish them as
   nav_msgs/Odometry (+ TF) and sensor_msgs/JointState.

Firmware quirk this node relies on: LCTPS/RCTPS ("measured ticks per
second") already carry a direction sign, because robot_control.c derives
that sign from the *target* direction it was given (see wheel_pid.c,
WheelSpeedController_Update). The raw LTicks/RTicks counters do not have a
direction sign (single-channel capture). So position is integrated here from
the signed ticks/s values over locally-measured dt, not from raw tick deltas.
"""

import math

import rclpy
from geometry_msgs.msg import Quaternion, Twist, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster

from motor_bridge.stm32_link import Stm32Link, Telemetry


def yaw_to_quaternion(yaw: float) -> Quaternion:
    q = Quaternion()
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q


class MotorBridgeNode(Node):

    def __init__(self):
        super().__init__('motor_bridge_node')

        self._declare_parameters()
        p = self._read_parameters()
        self._p = p

        if p['wheel_radius_m'] <= 0.0 or p['wheel_separation_m'] <= 0.0:
            self.get_logger().warn(
                'wheel_radius_m / wheel_separation_m have not been set to '
                'real measured values (see config/motor_bridge.yaml). '
                'Odometry and cmd_vel scaling will be wrong until you do.'
            )

        # cmd_vel -> target ticks/s, updated by the subscription callback,
        # consumed by the timer that actually talks to the firmware.
        self._target_left_ticks = 0
        self._target_right_ticks = 0
        self._last_cmd_vel_time = self.get_clock().now()

        # Odometry integration state.
        self._x = 0.0
        self._y = 0.0
        self._theta = 0.0
        self._left_wheel_angle = 0.0
        self._right_wheel_angle = 0.0
        self._last_telemetry_stamp = None  # time.monotonic(), set on first sample

        self._link = Stm32Link(
            port=p['serial_port'],
            baud=p['baud_rate'],
            on_telemetry=self._on_telemetry,
            on_reply=self._on_reply,
        )

        best_effort_qos = QoSProfile(
            depth=10, reliability=QoSReliabilityPolicy.BEST_EFFORT)

        self._cmd_vel_sub = self.create_subscription(
            Twist, p['cmd_vel_topic'], self._cmd_vel_callback, 10)
        self._odom_pub = self.create_publisher(
            Odometry, p['odom_topic'], best_effort_qos)
        self._joint_state_pub = self.create_publisher(
            JointState, 'joint_states', best_effort_qos)
        self._tf_broadcaster = (
            TransformBroadcaster(self) if p['publish_tf'] else None)

        period_s = 1.0 / p['publish_rate_hz']
        self._command_timer = self.create_timer(period_s, self._command_timer_callback)

        self.get_logger().info(
            f"motor_bridge connected on {p['serial_port']} @ {p['baud_rate']} baud"
        )

    # -- parameters -----------------------------------------------------

    def _declare_parameters(self) -> None:
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
        # From robot_control.c / wheel_pid.c comments: 100 ticks/rev,
        # firmware clamps |V target| to 1000 ticks/s.
        self.declare_parameter('ticks_per_revolution', 100)
        self.declare_parameter('max_ticks_per_second', 1000.0)

    def _read_parameters(self) -> dict:
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

    def _mps_to_ticks_per_s(self, meters_per_second: float) -> float:
        p = self._p
        wheel_circumference = 2.0 * math.pi * p['wheel_radius_m']
        if wheel_circumference <= 0.0:
            return 0.0
        return (meters_per_second / wheel_circumference) * p['ticks_per_revolution']

    def _cmd_vel_callback(self, msg: Twist) -> None:
        p = self._p
        v_left_mps = msg.linear.x - (msg.angular.z * p['wheel_separation_m'] / 2.0)
        v_right_mps = msg.linear.x + (msg.angular.z * p['wheel_separation_m'] / 2.0)

        left_ticks = self._mps_to_ticks_per_s(v_left_mps)
        right_ticks = self._mps_to_ticks_per_s(v_right_mps)

        limit = p['max_ticks_per_second']
        left_ticks = max(-limit, min(limit, left_ticks))
        right_ticks = max(-limit, min(limit, right_ticks))

        self._target_left_ticks = int(left_ticks)
        self._target_right_ticks = int(right_ticks)
        self._last_cmd_vel_time = self.get_clock().now()

    def _command_timer_callback(self) -> None:
        elapsed = (self.get_clock().now() - self._last_cmd_vel_time).nanoseconds / 1e9
        if elapsed > self._p['cmd_vel_timeout_s']:
            # No fresh cmd_vel recently: fail safe rather than trust the
            # firmware's much longer 20 s timeout.
            self._link.send_velocity(0, 0)
            return
        self._link.send_velocity(self._target_left_ticks, self._target_right_ticks)

    # -- firmware -> odometry / joint states -----------------------------

    def _on_reply(self, line: str) -> None:
        self.get_logger().info(f'STM32: {line}')

    def _on_telemetry(self, telemetry: Telemetry) -> None:
        # NOTE: runs on the Stm32Link reader thread, not the executor thread.
        # rclpy Publisher.publish() and TransformBroadcaster.sendTransform()
        # are safe to call directly from another thread.
        p = self._p
        wheel_circumference = 2.0 * math.pi * p['wheel_radius_m']
        ticks_per_rev = p['ticks_per_revolution']

        v_left = (telemetry.left_ticks_per_s / ticks_per_rev) * wheel_circumference
        v_right = (telemetry.right_ticks_per_s / ticks_per_rev) * wheel_circumference

        linear_v = (v_left + v_right) / 2.0
        angular_v = 0.0
        if p['wheel_separation_m'] > 0.0:
            angular_v = (v_right - v_left) / p['wheel_separation_m']

        if self._last_telemetry_stamp is not None:
            dt = telemetry.stamp - self._last_telemetry_stamp
            if 0.0 < dt < 1.0:  # ignore first sample / clock jumps
                self._integrate_pose(linear_v, angular_v, dt)
                if ticks_per_rev > 0:
                    self._left_wheel_angle += (
                        2.0 * math.pi * telemetry.left_ticks_per_s * dt / ticks_per_rev)
                    self._right_wheel_angle += (
                        2.0 * math.pi * telemetry.right_ticks_per_s * dt / ticks_per_rev)
        self._last_telemetry_stamp = telemetry.stamp

        self._publish_odometry(linear_v, angular_v)
        self._publish_joint_states()

    def _integrate_pose(self, linear_v: float, angular_v: float, dt: float) -> None:
        # Midpoint integration: more accurate than forward Euler for a
        # turning robot without needing a closed-form arc solution.
        delta_theta = angular_v * dt
        mid_theta = self._theta + (delta_theta / 2.0)
        self._x += linear_v * math.cos(mid_theta) * dt
        self._y += linear_v * math.sin(mid_theta) * dt
        self._theta = math.atan2(
            math.sin(self._theta + delta_theta), math.cos(self._theta + delta_theta))

    def _publish_odometry(self, linear_v: float, angular_v: float) -> None:
        p = self._p
        now = self.get_clock().now().to_msg()
        quat = yaw_to_quaternion(self._theta)

        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = p['odom_frame_id']
        odom.child_frame_id = p['base_frame_id']
        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.pose.pose.orientation = quat
        odom.twist.twist.linear.x = linear_v
        odom.twist.twist.angular.z = angular_v
        self._odom_pub.publish(odom)

        if self._tf_broadcaster is not None:
            tf_msg = TransformStamped()
            tf_msg.header.stamp = now
            tf_msg.header.frame_id = p['odom_frame_id']
            tf_msg.child_frame_id = p['base_frame_id']
            tf_msg.transform.translation.x = self._x
            tf_msg.transform.translation.y = self._y
            tf_msg.transform.rotation = quat
            self._tf_broadcaster.sendTransform(tf_msg)

    def _publish_joint_states(self) -> None:
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['wheel_left_joint', 'wheel_right_joint']
        msg.position = [self._left_wheel_angle, self._right_wheel_angle]
        self._joint_state_pub.publish(msg)

    # -- lifecycle --------------------------------------------------------

    def destroy_node(self) -> bool:
        try:
            self._link.stop()
        finally:
            self._link.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MotorBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
