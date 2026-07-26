"""Pure differential-drive kinematics; intentionally independent of ROS."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class WheelTicks:
    """A left/right STM32 wheel-speed target in encoder ticks per second."""

    left: float
    right: float


class DifferentialDriveKinematics:
    """Convert between robot twist, wheel speed, and encoder tick rate."""

    def __init__(self, wheel_radius_m: float, wheel_separation_m: float,
                 ticks_per_revolution: int):
        self.wheel_radius_m = wheel_radius_m
        self.wheel_separation_m = wheel_separation_m
        self.ticks_per_revolution = ticks_per_revolution

    @property
    def wheel_circumference_m(self) -> float:
        """Distance travelled by one wheel revolution, in metres."""
        return 2.0 * math.pi * self.wheel_radius_m

    def ticks_to_meters_per_second(self, ticks_per_second: float) -> float:
        """Convert an STM32 signed encoder rate to wheel rim speed."""
        if self.ticks_per_revolution <= 0 or self.wheel_circumference_m <= 0.0:
            return 0.0
        return ticks_per_second * self.wheel_circumference_m / self.ticks_per_revolution

    def cmd_vel_to_ticks(self, linear_mps: float, angular_radps: float) -> WheelTicks:
        """Apply inverse differential-drive kinematics to a ROS Twist."""
        left_mps = linear_mps - angular_radps * self.wheel_separation_m / 2.0
        right_mps = linear_mps + angular_radps * self.wheel_separation_m / 2.0
        circumference = self.wheel_circumference_m
        if circumference <= 0.0:
            return WheelTicks(0.0, 0.0)
        return WheelTicks(
            left_mps * self.ticks_per_revolution / circumference,
            right_mps * self.ticks_per_revolution / circumference,
        )

    def wheel_speeds_to_twist(self, left_mps: float, right_mps: float) -> tuple:
        """Apply forward differential-drive kinematics: wheel speeds -> twist."""
        linear_mps = (left_mps + right_mps) / 2.0
        angular_radps = 0.0
        if self.wheel_separation_m > 0.0:
            angular_radps = (right_mps - left_mps) / self.wheel_separation_m
        return linear_mps, angular_radps
