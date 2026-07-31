"""Encoder-position odometry and wheel-joint state for the AMR."""

import math
from dataclasses import dataclass

from geometry_msgs.msg import Quaternion

from amr_driver.differential_drive import DifferentialDriveKinematics

# Names used by the simplified robot-description URDF.
LEFT_WHEEL_JOINT = 'left_wheel_joint'
RIGHT_WHEEL_JOINT = 'right_wheel_joint'


@dataclass(frozen=True)
class OdometryUpdate:
    """Robot twist resulting from one received STM32 telemetry sample."""

    linear_velocity: float
    angular_velocity: float
    left_wheel_velocity: float
    right_wheel_velocity: float


class DifferentialDriveOdometry:
    """Integrate signed total wheel ticks into planar pose and wheel angles."""

    def __init__(self, kinematics: DifferentialDriveKinematics):
        self._kinematics = kinematics
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.left_wheel_angle = 0.0
        self.right_wheel_angle = 0.0
        self.left_wheel_joint = LEFT_WHEEL_JOINT
        self.right_wheel_joint = RIGHT_WHEEL_JOINT
        self.left_wheel_velocity = 0.0
        self.right_wheel_velocity = 0.0
        self._last_stamp = None
        self._last_time_ms = None
        self._last_left_ticks = None
        self._last_right_ticks = None

    def update(self, left_ticks: int, right_ticks: int, time_ms: int,
               stamp: float) -> OdometryUpdate:
        """Use one signed encoder-position sample from the STM32.

        The firmware sends total signed ticks, not a distance or velocity.  ROS
        subtracts the previous total from the current total:

            delta_ticks = current_total_ticks - previous_total_ticks

        Then each wheel distance is:

            wheel_distance = delta_ticks / ticks_per_rev * wheel_circumference

        This is the important fix for RViz wheel animation: one physical wheel
        revolution, about ``ticks_per_revolution`` ticks, becomes one full
        ``2*pi`` radian joint rotation.
        """
        if (self._last_left_ticks is None or self._last_right_ticks is None or
                self._last_time_ms is None or self._last_stamp is None):
            self._remember_sample(left_ticks, right_ticks, time_ms, stamp)
            return OdometryUpdate(0.0, 0.0, 0.0, 0.0)

        delta_left_ticks = left_ticks - self._last_left_ticks
        delta_right_ticks = right_ticks - self._last_right_ticks

        # STM32 HAL_GetTick() is normally uint32_t.  Masking gives the correct
        # positive elapsed time even when that millisecond counter wraps after
        # about 49.7 days.
        dt_ms = (time_ms - self._last_time_ms) & 0xFFFFFFFF
        dt = dt_ms / 1000.0
        if not (0.0 < dt < 1.0):
            # Fall back to local monotonic time if the firmware timestamp is
            # missing, stale, or implausibly delayed.
            dt = stamp - self._last_stamp

        linear = 0.0
        angular = 0.0
        left_wheel_velocity = 0.0
        right_wheel_velocity = 0.0

        # Avoid a false pose jump after delayed serial data or a reset.
        if 0.0 < dt < 1.0 and self._kinematics.ticks_per_revolution > 0:
            ticks_per_rev = self._kinematics.ticks_per_revolution
            circumference = self._kinematics.wheel_circumference_m

            left_distance = (
                delta_left_ticks * circumference / ticks_per_rev)
            right_distance = (
                delta_right_ticks * circumference / ticks_per_rev)

            linear_delta = (left_distance + right_distance) / 2.0
            delta_theta = (
                (right_distance - left_distance) /
                self._kinematics.wheel_separation_m)

            mid_theta = self.theta + delta_theta / 2.0
            self.x += linear_delta * math.cos(mid_theta)
            self.y += linear_delta * math.sin(mid_theta)
            self.theta = math.atan2(
                math.sin(self.theta + delta_theta),
                math.cos(self.theta + delta_theta))

            self.left_wheel_angle += (
                2.0 * math.pi * delta_left_ticks / ticks_per_rev)
            self.right_wheel_angle += (
                2.0 * math.pi * delta_right_ticks / ticks_per_rev)

            linear = linear_delta / dt
            angular = delta_theta / dt
            left_wheel_velocity = (
                2.0 * math.pi * delta_left_ticks / ticks_per_rev / dt)
            right_wheel_velocity = (
                2.0 * math.pi * delta_right_ticks / ticks_per_rev / dt)

        self.left_wheel_velocity = left_wheel_velocity
        self.right_wheel_velocity = right_wheel_velocity
        self._remember_sample(left_ticks, right_ticks, time_ms, stamp)
        return OdometryUpdate(
            linear, angular, left_wheel_velocity, right_wheel_velocity)

    def _remember_sample(self, left_ticks: int, right_ticks: int,
                         time_ms: int, stamp: float) -> None:
        """Save the current sample as the baseline for the next delta."""
        self._last_left_ticks = left_ticks
        self._last_right_ticks = right_ticks
        self._last_time_ms = time_ms
        self._last_stamp = stamp

    def orientation_quaternion(self) -> Quaternion:
        """Return the planar orientation in the quaternion form ROS requires."""
        quaternion = Quaternion()
        quaternion.z = math.sin(self.theta / 2.0)
        quaternion.w = math.cos(self.theta / 2.0)
        return quaternion
