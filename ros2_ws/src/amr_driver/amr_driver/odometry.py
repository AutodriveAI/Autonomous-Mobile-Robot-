"""Encoder-rate odometry and wheel-joint state for the AMR."""

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


class DifferentialDriveOdometry:
    """Integrate signed wheel tick rates into planar pose and wheel angles."""

    def __init__(self, kinematics: DifferentialDriveKinematics):
        self._kinematics = kinematics
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.left_wheel_angle = 0.0
        self.right_wheel_angle = 0.0
        self.left_wheel_joint = LEFT_WHEEL_JOINT
        self.right_wheel_joint = RIGHT_WHEEL_JOINT
        self._last_stamp = None

    def update(self, left_ticks_per_s: int, right_ticks_per_s: int,
               stamp: float) -> OdometryUpdate:
        """Use one telemetry reading; integrate only for a plausible interval."""
        left_mps = self._kinematics.ticks_to_meters_per_second(left_ticks_per_s)
        right_mps = self._kinematics.ticks_to_meters_per_second(right_ticks_per_s)
        linear, angular = self._kinematics.wheel_speeds_to_twist(left_mps, right_mps)

        if self._last_stamp is not None:
            dt = stamp - self._last_stamp
            # Avoid a false position jump after delayed serial data.
            if 0.0 < dt < 1.0:
                delta_theta = angular * dt
                mid_theta = self.theta + delta_theta / 2.0
                self.x += linear * math.cos(mid_theta) * dt
                self.y += linear * math.sin(mid_theta) * dt
                self.theta = math.atan2(
                    math.sin(self.theta + delta_theta),
                    math.cos(self.theta + delta_theta))
                ticks_per_rev = self._kinematics.ticks_per_revolution
                if ticks_per_rev > 0:
                    self.left_wheel_angle += (
                        2.0 * math.pi * left_ticks_per_s * dt / ticks_per_rev)
                    # The exported right joint uses the opposite axis.
                    self.right_wheel_angle -= (
                        2.0 * math.pi * right_ticks_per_s * dt / ticks_per_rev)
        self._last_stamp = stamp
        return OdometryUpdate(linear, angular)

    def orientation_quaternion(self) -> Quaternion:
        """Return the planar orientation in the quaternion form ROS requires."""
        quaternion = Quaternion()
        quaternion.z = math.sin(self.theta / 2.0)
        quaternion.w = math.cos(self.theta / 2.0)
        return quaternion
