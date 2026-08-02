# amr_navigation

This package owns the AMR navigation layer.

It has two jobs:

1. Run `twist_mux`, so autonomous Nav2, keyboard teleop, and joystick teleop do
   not fight each other.
2. Run the Nav2 path-planning/path-following stack.

Localization is intentionally kept in `amr_localisation`. That package loads
the saved map and runs AMCL. This package assumes localization is already
publishing:

```text
map -> odom
```

and that either Gazebo or the real robot driver is publishing:

```text
odom -> base_link
```

## Command topic flow

```text
Nav2 controller
    ↓
/cmd_vel_nav_raw
    ↓
Nav2 velocity_smoother
    ↓
/cmd_vel_nav

keyboard teleop
    ↓
/cmd_vel_keyboard

joystick teleop
    ↓
/cmd_vel_joy

all command sources
    ↓
twist_mux
    ↓
/cmd_vel
    ↓
Gazebo diff-drive plugin or real amr_driver
```

The important idea is that Nav2 does not directly command the robot. Nav2 is
only one candidate command source. `twist_mux` remains the final command gate.

## `twist_mux` priorities

Higher priority wins:

| Source | Topic | Priority |
|---|---:|---:|
| Joystick/gamepad | `/cmd_vel_joy` | 100 |
| Keyboard | `/cmd_vel_keyboard` | 80 |
| Nav2/autonomy | `/cmd_vel_nav` | 10 |

This means human control can override autonomous navigation.

Each source has a timeout. If a source stops publishing, `twist_mux` stops
using it and falls back to the next active lower-priority source.

## Nav2 nodes launched

`launch/nav2.launch.py` starts:

- `planner_server`
- `controller_server`
- `velocity_smoother`
- `smoother_server`
- `behavior_server`
- `bt_navigator`
- `waypoint_follower`
- `lifecycle_manager_navigation`

It does not start AMCL or the map server. Use `amr_localisation` for that.

## First Gazebo Nav2 test

Terminal 1, launch simulation + AMCL + Nav2 + Nav2 RViz:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py start_nav2:=true use_nav2_rviz:=true start_joy_teleop:=false
```

In RViz:

1. Confirm Fixed Frame is `map`.
2. Use **2D Pose Estimate** if the robot pose is wrong.
3. Use **Nav2 Goal** to send a navigation goal.

## Launch only the Nav2 navigation layer

Use this only if Gazebo/real robot bringup and localization are already running:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation nav2.launch.py
```

## Launch only `twist_mux`

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation twist_mux.launch.py
```

## Key parameters

The main Nav2 tuning file is:

```text
config/nav2_params.yaml
```

Important early tuning values:

- `controller_server.controller_frequency`: how often local velocity commands
  are computed.
- `FollowPath.max_vel_x`: maximum forward speed from Nav2.
- `FollowPath.max_vel_theta`: maximum turning speed from Nav2.
- `FollowPath.acc_lim_x`: forward acceleration limit.
- `FollowPath.acc_lim_theta`: angular acceleration limit.
- `local_costmap.local_costmap.robot_radius`: safety radius for local obstacle
  avoidance.
- `global_costmap.global_costmap.robot_radius`: safety radius for global
  planning.

Start conservative. Once the robot reliably navigates in Gazebo, then tune
speed, acceleration, inflation radius, and obstacle ranges.
