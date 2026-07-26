# AMR Driver

`amr_driver` is the ROS 2 hardware-driver package for the physical
differential-drive robot. It connects ROS 2 running on the Jetson Nano (or a
development computer) to the STM32 motor-controller firmware over USB serial.

It is not a Gazebo plugin. It controls the real motors and publishes feedback
from the real encoders.

## What the package does

```text
teleop / navigation
        │ publishes geometry_msgs/Twist
        ▼
      /cmd_vel
        │
        ▼
   amr_driver_node
        │ inverse differential-drive kinematics
        │ serial: V,<left_ticks/s>,<right_ticks/s>
        ▼
 STM32 firmware + wheel PID
        │ PWM signals
        ▼
 L298N motor driver → motors → physical wheels
        │                     ▲
        │ encoder pulses      │
        ▼                     │
 STM32 telemetry ─────────────┘
        │ serial: LTicks, LPWM, LCTPS, RTicks, RPWM, RCTPS
        ▼
   amr_driver_node
        ├── publishes /odom and optional odom → base_link TF
        └── publishes /joint_states for RViz wheel animation
```

The STM32 is responsible for the time-critical work: counting encoder pulses,
running each wheel PID controller, producing PWM, and stopping the motors if
its command watchdog expires. The computer is responsible for ROS messages,
robot-level kinematics, odometry, TF, and visualization.

## Package layout

| File | Responsibility |
|---|---|
| `amr_driver_node.py` | ROS-facing node: parameters, `/cmd_vel` subscriber, timer, publishers, TF, and lifecycle. |
| `stm32_transport.py` | Serial port connection, STM32 command formatting, background line reader, and telemetry parsing. |
| `differential_drive.py` | Pure wheel/robot kinematic equations; it does not import ROS. |
| `odometry.py` | Integrates encoder speed feedback into `x`, `y`, heading, and RViz wheel-joint angles. |
| `config/amr_driver.yaml` | Port, geometry, frames, command rate, and safety-timeout parameters. |
| `launch/amr_driver.launch.py` | Starts `amr_driver_node` using the YAML configuration. |

Keeping transport, kinematics, and odometry separate makes the equations
testable and prevents the ROS node from becoming one large file.

## Command path

A teleoperation node normally publishes a `geometry_msgs/Twist` on `/cmd_vel`:

```text
linear.x   = desired forward speed [m/s]
angular.z  = desired turning speed [rad/s]
```

`DifferentialDriveKinematics` converts this desired robot motion into left and
right wheel rim speeds:

```text
left_wheel_speed  = linear.x - angular.z × wheel_separation / 2
right_wheel_speed = linear.x + angular.z × wheel_separation / 2
```

It converts each wheel speed into encoder ticks per second using the measured
wheel circumference and `ticks_per_revolution`. The command is clamped to
`max_ticks_per_second`, converted to integers, then sent repeatedly at
`publish_rate_hz` as:

```text
V,<left_ticks_per_second>,<right_ticks_per_second>\n
```

For example:

```text
V,200,200
V,-100,100
V,0,0
```

Repeated transmission is deliberate: it refreshes the STM32 command timeout.
If ROS stops publishing `/cmd_vel` for longer than `cmd_vel_timeout_s`, the
driver sends `V,0,0` as a Jetson-side safety stop. The STM32 has its own
independent watchdog as a second safety layer.

## Feedback and odometry path

The STM32 periodically sends a human-readable telemetry line containing:

```text
LTicks:<count>  LPWM:<pwm>  LCTPS:<ticks/s>
RTicks:<count>  RPWM:<pwm>  RCTPS:<ticks/s>
```

`stm32_transport.py` parses the values into a `Telemetry` object.

- `LTicks` and `RTicks` are the raw single-channel encoder counts.
- `LCTPS` and `RCTPS` are the wheel PID controller's measured signed tick
  rates. They are used for velocity and odometry.
- `LPWM` and `RPWM` help diagnose PID and motor behavior.

The raw encoders are currently single-channel, so they do not independently
report direction. The STM32 assigns the sign of its measured rate from the
current commanded direction. This is adequate for controlled operation, but
true direction sensing later requires quadrature encoders or another direction
source.

`odometry.py` converts ticks/s back into wheel m/s, applies differential-drive
forward kinematics, and integrates the result over each received telemetry
interval. It publishes:

- `/odom` (`nav_msgs/Odometry`): estimated pose and velocity.
- `odom → base_link` TF, when `publish_tf: true`.
- `/joint_states` (`sensor_msgs/JointState`): wheel angles used by
  `robot_state_publisher` to animate the real wheels in RViz.

The exported Onshape right-wheel joint has the opposite axis direction, so the
right visual wheel angle is negated in `odometry.py`. This changes only RViz
animation; it does not change physical motor direction.

## Configuration

Edit [`config/amr_driver.yaml`](config/amr_driver.yaml) for the actual robot.
The most important values are:

| Parameter | Meaning |
|---|---|
| `serial_port` | STM32 ST-LINK virtual serial port, commonly `/dev/ttyACM0`. |
| `baud_rate` | Must match STM32 USART2: `115200`. |
| `wheel_radius_m` | Measured loaded wheel radius in metres. |
| `wheel_separation_m` | Distance between left/right wheel contact-center lines in metres. |
| `ticks_per_revolution` | `100` for the present 100-slot encoder disk on the wheel axle. |
| `max_ticks_per_second` | ROS-side target limit; must not exceed the STM32's accepted limit. |
| `publish_rate_hz` | Rate for refreshing wheel target commands. |
| `cmd_vel_timeout_s` | ROS-side duration without `/cmd_vel` before commanding a stop. |

Accurate wheel radius and separation are necessary for correct speed scaling
and odometry. They should be measured and then refined through straight-line
and in-place-turn tests.

## Running

On the Foxy target machine:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/foxy/setup.bash
colcon build --packages-select amr_driver --symlink-install
source install/setup.bash
ros2 launch amr_driver amr_driver.launch.py
```

The STM32 must already be powered, flashed, and visible at the configured
serial port. Check ports with:

```bash
ls /dev/ttyACM* /dev/ttyUSB*
```

For RViz with live wheel motion, start the description package without its demo
joint-state publisher, then start this driver:

```bash
ros2 launch robot_description display.launch.py use_joint_state_publisher:=false
ros2 launch amr_driver amr_driver.launch.py
```

## What this package does not do yet

- It does not simulate the robot; Gazebo needs a separate simulation model,
  collision shapes, inertias, and a differential-drive simulation controller.
- It does not provide `ros2_control`; the present custom serial protocol and
  STM32 PID loop are simpler while the hardware is being developed.
- It does not perform SLAM, navigation, lidar processing, or battery handling.
  Those are separate ROS packages/nodes.
