# AMR Teleoperation

`amr_teleop` provides a project-specific command for ROS 2's standard
`teleop_twist_keyboard` node—the terminal teleop commonly used with TurtleBot
simulations.

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

There is no custom keyboard reader, desktop keyboard hook, or
`command_hold_s` timer in this package. It uses the standard node unchanged.

## Install the standard teleop package

On the current Ubuntu 22.04 / ROS 2 Humble development computer:

```bash
sudo apt update
sudo apt install -y ros-humble-teleop-twist-keyboard
```

On the target Ubuntu 20.04 / ROS 2 Foxy computer:

```bash
sudo apt update
sudo apt install -y ros-foxy-teleop-twist-keyboard
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
  -p speed:=0.3 -p turn:=0.8
```

The command above is an alias for:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -p speed:=0.3 -p turn:=0.8
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
  -p speed:=0.3 -p turn:=0.8
```

For the first physical test, lift the drive wheels off the ground and keep
`k` ready as the stop key.
