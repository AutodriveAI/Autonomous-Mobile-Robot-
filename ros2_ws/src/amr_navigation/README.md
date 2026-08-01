# amr_navigation

This package owns navigation command arbitration for the AMR.

At this stage it does not launch the full Nav2 planner yet. First, it provides
`twist_mux`, so keyboard, joystick, and future Nav2 commands do not fight each
other on `/cmd_vel`.

## Command topic flow

```text
Nav2 planner later
    ↓
/cmd_vel_nav

keyboard teleop
    ↓
/cmd_vel_keyboard

joystick teleop
    ↓
/cmd_vel_joy

all three
    ↓
twist_mux
    ↓
/cmd_vel
    ↓
Gazebo diff drive or real amr_driver
```

## Priorities

Higher priority wins:

| Source | Topic | Priority |
|---|---:|---:|
| Joystick/gamepad | `/cmd_vel_joy` | 100 |
| Keyboard | `/cmd_vel_keyboard` | 80 |
| Nav2/autonomy | `/cmd_vel_nav` | 10 |

This means human control can override autonomous navigation.

## Timeouts

Each input has:

```text
timeout: 0.5
```

If one source stops publishing for 0.5 s, `twist_mux` stops considering that
source active and falls back to the next available lower-priority source.

## Launch twist_mux only

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation twist_mux.launch.py
```

## Test in Gazebo

The simulation bringup is wired so teleop publishes into mux input topics:

```text
keyboard -> /cmd_vel_keyboard
joystick -> /cmd_vel_joy
twist_mux -> /cmd_vel
Gazebo -> subscribes /cmd_vel
```

Launch Gazebo with joystick teleop enabled:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py
```

For keyboard testing, it is usually better to run keyboard teleop in its own
interactive terminal:

Terminal 1:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py start_joy_teleop:=false
```

Terminal 2:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run amr_teleop keyboard_teleop --ros-args -r cmd_vel:=/cmd_vel_keyboard
```

## Future Nav2 connection

When we add full Nav2, Nav2 should publish to:

```text
/cmd_vel_nav
```

not directly to `/cmd_vel`.

Then `twist_mux` remains the final authority that publishes `/cmd_vel`.
