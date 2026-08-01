# AMR Teleoperation

`amr_teleop` provides project-specific keyboard and Logitech-style joystick
teleoperation for the AMR.

```text
keyboard
   ↓
teleop_twist_keyboard
   ↓  /cmd_vel (geometry_msgs/Twist)
amr_driver
   ↓  V,<left_ticks_per_second>,<right_ticks_per_second>
STM32
   ↓
motors
```

For keyboard control there is no custom keyboard reader, desktop keyboard hook,
or `command_hold_s` timer. The keyboard wrapper uses the standard node
unchanged.

For joystick control, `joy_node` reads the Linux gamepad device and our
`joy_teleop` node converts stick axes into `/cmd_vel`. The joystick speed
parameters are expressed in wheel encoder ticks/s so they match the STM32
mental model:

```text
Logitech gamepad
   ↓
joy_node
   ↓  /joy
joy_teleop
   ↓  /cmd_vel
amr_driver
   ↓  V,<left_ticks_per_second>,<right_ticks_per_second>
STM32
```

## Install the standard teleop package

On the current Ubuntu 22.04 / ROS 2 Humble development computer:

```bash
sudo apt update
sudo apt install -y ros-humble-teleop-twist-keyboard ros-humble-joy
```

On the target Ubuntu 20.04 / ROS 2 Foxy computer:

```bash
sudo apt update
sudo apt install -y ros-foxy-teleop-twist-keyboard ros-foxy-joy
```

## Build

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select amr_teleop --symlink-install
source install/setup.bash
```

## Run

Run this directly in an interactive terminal. Do not start it through
`ros2 launch`, because the node must read keystrokes from that terminal.

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run amr_teleop keyboard_teleop --ros-args \
  -p speed:=1.021 -p turn:=11.669
```

The command above is an alias for:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -p speed:=1.021 -p turn:=11.669
```

The `amr_teleop keyboard_teleop` wrapper uses these AMR defaults automatically,
so this shorter command is equivalent:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run amr_teleop keyboard_teleop
```

Those defaults are equivalent to about `100 ticks/s` forward on both wheels and
about `+/-100 ticks/s` for in-place turning with:

- wheel radius: `0.0325 m`
- wheel separation: `0.175 m`
- encoder resolution: `20 ticks/rev`

## Run joystick teleop directly

Terminal 1 — start the standard joystick driver:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run joy joy_node --ros-args \
  -p dev:=/dev/input/js0 \
  -p deadzone:=0.08 \
  -p autorepeat_rate:=20.0
```

Terminal 2 — start AMR joystick teleop:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run amr_teleop joy_teleop --ros-args \
  -p speed_ticks_per_second:=100.0 \
  -p turn_ticks_per_second:=100.0
```

Default joystick mapping:

| Control | Meaning |
|---|---|
| Left stick vertical | Forward/backward |
| Left stick horizontal | Rotate left/right |
| Centered stick | Publish zero velocity |

If your Logitech mode switch reverses an axis, override the sign:

```bash
ros2 run amr_teleop joy_teleop --ros-args -p linear_axis_sign:=-1.0
```

## Standard controls

```text
   u    i    o
   j    k    l
   m    ,    .
```

| Key | Command |
|---|---|
| `i` | Drive forward |
| `,` | Drive backward |
| `j` | Rotate left |
| `l` | Rotate right |
| `u` / `o` | Forward-left / forward-right |
| `m` / `.` | Backward-left / backward-right |
| `k` | Stop |
| `q` / `z` | Increase / decrease both speeds by 10% |
| `w` / `x` | Increase / decrease linear speed by 10% |
| `e` / `c` | Increase / decrease angular speed by 10% |
| Ctrl+C | Stop and exit |

In this standard teleop, `w` does **not** mean forward. Press `i` to drive
forward. A movement key sets the current command; press `k` to stop. It is not
a physical key-release controller.

## Start the physical robot

Terminal 1 — start the STM32 driver:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_driver amr_driver.launch.py
```

Terminal 2 — start keyboard teleop:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run amr_teleop keyboard_teleop --ros-args \
  -p speed:=1.021 -p turn:=11.669
```

For the first physical test, lift the drive wheels off the ground and keep
`k` ready as the stop key.
