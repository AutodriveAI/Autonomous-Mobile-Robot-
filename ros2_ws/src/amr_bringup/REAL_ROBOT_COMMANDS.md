# Real Robot Command Reference

These commands run the physical robot on the Jetson Nano with ROS 2 Foxy and
display/control Nav2 from the development machine with ROS 2 Humble. Run each
command in a separate terminal, in the order shown.

Both machines must be on the same network and use matching ROS domain settings.
`ROS_LOCALHOST_ONLY=0` permits ROS discovery beyond the local machine.

## LCD navigation messages

With `use_lcd:=true`, the persistent LCD node shows the idle mark at startup,
then watches `/navigate_to_pose/_action/status`. A newly accepted Nav2 goal
shows `New goal received!` and `Heading to destination...` for 10 seconds.
Successful completion shows `Goal reached!` and `Please collect your items! :)`.
The completion message remains visible for 20 seconds, then the idle mark
returns.

Override the durations through the physical bringup launch if needed:

```bash
ros2 launch amr_bringup robot_bringup.launch.py lcd_goal_received_duration_s:=10.0 lcd_goal_reached_duration_s:=20.0
```

Setting `lcd_goal_reached_duration_s:=0.0` keeps the collection message visible.

## 1. Jetson: robot, lidar, RGB camera, localization, joystick, and twist mux

This starts the real hardware and AMCL with the Lakecity Flat 4A map. It keeps
keyboard teleop and local RViz disabled; joystick teleop remains available as a
higher-priority override through `twist_mux`. The RealSense publishes RGB-only
camera data on `/camera_rgb` and `/camera_rgb/compressed`; depth remains off.

```bash
cd ~/Autonomous_Mobile_Robot/Autonomous-Mobile-Robot-/ros2_ws && source /opt/ros/foxy/setup.bash && source install/setup.bash && export ROS_LOCALHOST_ONLY=0 && ros2 launch amr_bringup robot_bringup.launch.py use_rviz:=false use_lcd:=true use_lidar:=true use_realsense:=true start_joy_teleop:=true start_keyboard_teleop:=false start_localisation:=true start_nav2:=false bypass_twist_mux:=false map:=$(ros2 pkg prefix amr_slam)/share/amr_slam/maps/LakecityFlat4AMap.yaml
```

## 2. Jetson: Nav2

Run this after the robot bringup is active. Nav2 uses wall time, the physical
robot parameters, and the branch's slow-replanning behavior tree.

```bash
cd ~/Autonomous_Mobile_Robot/Autonomous-Mobile-Robot-/ros2_ws && source /opt/ros/foxy/setup.bash && source install/setup.bash && export ROS_LOCALHOST_ONLY=0 && ros2 launch amr_navigation nav2.launch.py params_file:=$(ros2 pkg prefix amr_navigation)/share/amr_navigation/config/nav2_params_real.yaml use_sim_time:=false use_rviz:=false
```

## 3. Development machine: Humble RViz

This opens the standard Nav2 view locally, without SSH X forwarding.

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export ROS_LOCALHOST_ONLY=0 && rviz2 -d $(ros2 pkg prefix nav2_bringup)/share/nav2_bringup/rviz/nav2_default_view.rviz
```

If sourcing the development workspace reports a missing file such as
`install/sllidar_ros2/share/sllidar_ros2/local_setup.bash`, that workspace's
install overlay is incomplete or stale; it is not an RViz configuration error.
If `colcon list` shows `sllidar_ros2`, rebuild that package before sourcing the
workspace again:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --symlink-install --packages-select sllidar_ros2
```
