# AMR Bringup Launch Commands

This package contains the top-level launch files for starting the AMR in
simulation or on the physical robot.

Each command block is intentionally self-contained, so it can be copied into a
fresh terminal.

## Rebuild after changing bringup files

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select amr_bringup --symlink-install
source install/setup.bash
```

## Simulation bringup

Optional convenience launch: simulation bringup plus localization in one
terminal:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py \
  start_localisation:=true \
  start_nav2:=false \
  use_rviz:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false \
  map:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_slam/maps/LakecityFlat4AMap.yaml
```

Launch Nav2 for simulation:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation nav2.launch.py \
  use_sim_time:=true \
  use_rviz:=true \
  params_file:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_navigation/config/nav2_params.yaml
```

























Launch simulation headless, without RViz:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py \
  use_rviz:=false \
  gui:=false
```

Use a specific world:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py \
  world:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_description/worlds/simple_home.world
```


This starts Gazebo, robot description, twist mux, Nav2 RViz, map server, and
AMCL, but does not start Nav2.

Standalone simulation Nav2 launch, to run after simulation bringup and
simulation localization are already running:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation nav2.launch.py \
  use_sim_time:=true \
  use_rviz:=true \
  params_file:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_navigation/config/nav2_params.yaml
```

## Physical robot: plain bringup

Launch STM32 driver, LiDAR, robot description, and general RViz:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py \
  use_rviz:=true \
  use_lidar:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false
```

Launch without RViz:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py \
  use_rviz:=false \
  use_lidar:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false
```

Launch with joystick teleop enabled:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py \
  use_rviz:=true \
  use_lidar:=true \
  start_joy_teleop:=true \
  start_keyboard_teleop:=false
```

Optional convenience launch: physical robot bringup plus localization in one
terminal:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py \
  start_localisation:=true \
  use_rviz:=true \
  use_lidar:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false \
  map:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_slam/maps/LakecityFlat4AMap.yaml
```

## Simulation: localization and Nav2 as separate launches

Recommended workflow:

1. Start simulation bringup.
2. Start localization.
3. Start Nav2.

Terminal 1: simulation bringup only:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py \
  use_rviz:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false
```

Terminal 2: simulation localization:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_localisation localisation.launch.py \
  use_sim_time:=true \
  use_rviz:=false \
  map:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_slam/maps/LakecityFlat4AMap.yaml
```

Terminal 3: simulation Nav2:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation nav2.launch.py \
  use_sim_time:=true \
  use_rviz:=true \
  params_file:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_navigation/config/nav2_params.yaml
```

## Physical robot: localization and Nav2 as separate launches

Recommended workflow:

1. Start physical robot bringup.
2. Start localization.
3. Start Nav2.

Terminal 1: physical robot bringup only:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py \
  use_rviz:=true \
  use_lidar:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false
```

Terminal 2: physical robot localization:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_localisation localisation.launch.py \
  use_sim_time:=false \
  use_rviz:=false \
  map:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_slam/maps/LakecityFlat4AMap.yaml
```

Terminal 3: physical robot Nav2:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_navigation nav2.launch.py \
  use_sim_time:=false \
  use_rviz:=true \
  params_file:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_navigation/config/nav2_params_real.yaml
```

## Command flow

Normal command flow:

```text
/cmd_vel_nav -> twist_mux -> /cmd_vel -> simulator or amr_driver
```

The bringup launch starts `twist_mux`, so Nav2 can be started later and still
feed the same final `/cmd_vel` topic.

## Essential launch parameters

### `sim_bringup.launch.py`

| Parameter | Default | Purpose |
| --- | --- | --- |
| `start_joy_teleop` | `true` | Starts joystick teleop for simulation. Set `false` if you do not have a joystick connected. |
| `start_keyboard_teleop` | `false` | Starts keyboard teleop from the launch file. Usually keep `false` and run keyboard teleop manually in an interactive terminal. |
| `start_localisation` | `false` | Starts AMCL localization and map server from inside sim bringup, without starting Nav2. |
| `start_nav2` | `false` | Starts localization/Nav2 from inside sim bringup. For the cleaner workflow in this README, keep this `false` and launch Nav2 separately. |
| `use_rviz` | `true` | Opens RViz. Plain bringup uses the robot display config; `start_localisation:=true` or `start_nav2:=true` uses the Nav2 RViz config. |
| `world` | `simple_home.world` | Gazebo world file. Can be replaced with another `.world` path. |
| `extra_gazebo_model_path` | empty | Extra Gazebo model directory, useful for external worlds that reference `model://...` assets. |
| `map` | `LakecityFlat4AMap.yaml` | Map used if `start_localisation:=true` or `start_nav2:=true`. Not used when localization/Nav2 is launched separately. |
| `nav2_params_file` | `nav2_params.yaml` | Simulation Nav2 parameter file if `start_nav2:=true`. |
| `use_sim_time` | `true` | Uses Gazebo simulation clock. Keep `true` for simulation. |
| `gui` | `true` | Starts Gazebo client window. Set `false` for headless simulation. |
| `server` | `true` | Starts Gazebo server. Usually keep `true`. |
| `teleop_speed_ticks_per_second` | `100.0` | Full-stick forward command used by `joy_teleop`. |
| `teleop_turn_ticks_per_second` | `100.0` | Full-stick in-place turn command used by `joy_teleop`. |

Example:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup sim_bringup.launch.py \
  start_joy_teleop:=false \
  use_rviz:=true \
  world:=/home/shanto/Github/Autonomous-Mobile-Robot-/ros2_ws/src/amr_description/worlds/simple_home.world
```

### `robot_bringup.launch.py`

| Parameter | Default | Purpose |
| --- | --- | --- |
| `start_joy_teleop` | `true` | Starts joystick teleop for the physical robot. Set `false` during Nav2 testing unless you want joystick override. |
| `start_keyboard_teleop` | `false` | Starts keyboard teleop from the launch file. Usually keep `false` and run keyboard teleop manually if needed. |
| `start_localisation` | `false` | Starts localization from inside bringup. For the cleaner workflow in this README, keep this `false` and launch localization separately. |
| `start_nav2` | `false` | Starts localization and Nav2 from inside bringup. For the cleaner workflow in this README, keep this `false` and launch Nav2 separately. |
| `use_rviz` | `true` | Opens RViz. Plain bringup uses the robot display config; `start_localisation:=true` or `start_nav2:=true` uses the Nav2 RViz config. |
| `use_lidar` | `true` | Starts the physical RPLidar driver. |
| `config_file` | `amr_driver.yaml` | Parameter file for `amr_driver`. Contains serial port, wheel geometry, encoder ticks/rev, etc. |
| `map` | `LakecityFlat4AMap.yaml` | Map used if `start_localisation` or `start_nav2` is enabled inside bringup. |
| `nav2_params_file` | `nav2_params_real.yaml` | Real-robot Nav2 parameter file if `start_nav2:=true`. |
| `lidar_serial_port` | `/dev/ttyUSB0` | RPLidar USB serial device. |
| `lidar_serial_baudrate` | `460800` | RPLidar C1 baud rate. |
| `lidar_frame_id` | `lidar_scan_link` | LaserScan frame. |
| `lidar_scan_mode` | empty | Optional RPLidar scan mode. Empty lets the driver choose. |
| `bypass_twist_mux` | `false` | Diagnostic option: makes `amr_driver` listen directly to `/cmd_vel_nav` instead of `/cmd_vel`. |
| `teleop_speed_ticks_per_second` | `100.0` | Full-stick forward command used by `joy_teleop`. |
| `teleop_turn_ticks_per_second` | `100.0` | Full-stick in-place turn command used by `joy_teleop`. |

Example:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py \
  use_lidar:=true \
  use_rviz:=true \
  start_joy_teleop:=false \
  start_keyboard_teleop:=false \
  lidar_serial_port:=/dev/ttyUSB0
```

### Separate localization launch

| Parameter | Typical real value | Typical sim value | Purpose |
| --- | --- | --- | --- |
| `use_sim_time` | `false` | `true` | Selects real clock or Gazebo clock. |
| `use_rviz` | `false` | `false` | Opens localization RViz if needed. Usually keep false if another RViz is already open. |
| `map` | `LakecityFlat4AMap.yaml` | map for current sim world | Occupancy-grid map YAML loaded by map server. |
| `scan_topic` | `/scan` | `/scan` | LaserScan topic consumed by AMCL. |

### Separate Nav2 launch

| Parameter | Typical real value | Typical sim value | Purpose |
| --- | --- | --- | --- |
| `use_sim_time` | `false` | `true` | Selects real clock or Gazebo clock. |
| `use_rviz` | `true` | `true` | Opens Nav2 RViz for sending goals and visualizing costmaps/plans. |
| `params_file` | `nav2_params_real.yaml` | `nav2_params.yaml` | Nav2 tuning file. Real robot and simulation use different velocity/control profiles. |
| `autostart` | `true` | `true` | Automatically activates Nav2 lifecycle nodes. |
| `log_level` | `info` | `info` | Nav2 console verbosity. |

## Useful checks

Check final velocity command:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 topic echo /cmd_vel
```

Check Nav2 velocity command before mux:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 topic echo /cmd_vel_nav
```

Check STM32 driver command input topic:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 param get /amr_driver_node cmd_vel_topic
```

Check LiDAR scan:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 topic hz /scan
```

Check odometry:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 topic echo /odom
```
