# AMR SLAM

`amr_slam` contains the occasional mapping setup for the real AMR. It is kept
separate from `amr_bringup` because mapping is not something we want to launch
every time the robot boots.

## What must already be running

Before starting SLAM, the robot should already publish:

- `/scan` from the physical RPLidar, with frame `lidar_scan_link`
- `/odom` from wheel encoder odometry
- TF from `odom` to `base_link`
- TF from `base_link` to `lidar_scan_link`
- `/robot_description` from `robot_state_publisher`

The normal way to provide those is:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py
```

## Start mapping

In another terminal:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_slam mapping.launch.py
```

## Saved maps

Saved maps belong in this package's `maps/` folder:

```text
src/amr_slam/maps/
```

Current saved map:

```text
maps/LakecityFlat4AMap.yaml
maps/LakecityFlat4AMap.pgm
```

If you save a new map from Slam Toolbox, save it into that folder instead of
the workspace root. Keeping maps inside `amr_slam` makes them easier to install,
commit, and launch later for localization.

## Map resolution

The current mapping config uses:

```text
resolution: 0.03
```

That means each map cell/pixel represents 3 cm in the real world.

Older saved maps do not automatically become sharper when this value changes.
To get a 3 cm/cell map, run mapping again and save/serialize a new map.

## Important frame chain

During mapping, Slam Toolbox needs this TF chain:

```text
map -> odom -> base_link -> lidar_link -> lidar_scan_link
```

- `odom -> base_link` comes from our wheel encoder odometry.
- `base_link -> lidar_link -> lidar_scan_link` comes from the URDF.
- `map -> odom` is published by Slam Toolbox.

Wheel odometry gives Slam Toolbox the robot's short-term motion estimate. The
laser scan then corrects drift by matching walls and obstacles over time.
