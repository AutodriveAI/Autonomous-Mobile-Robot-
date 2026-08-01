# amr_localisation

This package localizes the real AMR on a previously saved map using the
standard Nav2 AMCL stack.

This follows the same broad pattern as the `Autodrive_F1Tenth` localization
stack:

```text
nav2_map_server -> publishes the saved /map from .yaml/.pgm
nav2_amcl       -> matches live /scan against that static map
RViz            -> provides /initialpose from 2D Pose Estimate
```

Unlike Slam Toolbox localization, AMCL does not extend or edit the map. That
makes it better for this stage, because the robot may start at any place inside
the already-created map.

## Runtime data flow

```text
amr_slam/maps/LakecityFlat4AMap.yaml
        ↓
nav2_map_server
        ↓
/map

/scan + /odom + /map + /initialpose
        ↓
nav2_amcl
        ↓
map -> odom

amr_driver
        ↓
odom -> base_link
```

The full localized robot pose is:

```text
map -> odom -> base_link
```

## Required map files

AMCL uses the normal occupancy-grid map:

```text
LakecityFlat4AMap.yaml
LakecityFlat4AMap.pgm
```

It does not need Slam Toolbox's serialized files:

```text
LakecityFlat4AMap.posegraph
LakecityFlat4AMap.data
```

Those serialized files are still useful if we ever return to Slam Toolbox
localization, but this AMCL stack loads the `.yaml/.pgm` map through
`nav2_map_server`.

## Launch localization

Run the physical robot bringup first, because localization needs `/scan`,
`/odom`, `/tf`, and `/robot_description`.

Terminal 1:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_bringup robot_bringup.launch.py
```

Terminal 2:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_localisation localisation.launch.py
```

If you want RViz to open from this launch:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_localisation localisation.launch.py use_rviz:=true
```

If you want to use a different map:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_localisation localisation.launch.py map:=/absolute/path/to/map.yaml
```

## Set the robot's initial pose

AMCL expects the user to initialize the robot pose.

In RViz:

1. Set Fixed Frame to `map`.
2. Click **2D Pose Estimate**.
3. Click where the robot currently is on the map.
4. Drag the green arrow in the direction the robot is facing.

That publishes:

```text
/initialpose
```

AMCL then uses the particle filter to match the live LiDAR scan against the
saved map and publishes `map -> odom`.

## Why wheel odometry still matters

Wheel odometry gives AMCL the short-term motion estimate:

```text
odom -> base_link
```

AMCL uses that as a prediction, then corrects it using the LiDAR scan and the
saved map. If wheel odometry is poor, AMCL can still work, but it will need more
particles and can become jumpy or slow to recover.

## IMU later

Later we can fuse wheel odometry and IMU with `robot_localization`:

```text
wheel odom + IMU -> robot_localization EKF -> odom -> base_link
LiDAR + map      -> AMCL                   -> map -> odom
```

The IMU can improve heading stability, but it does not replace the map-based
localizer.
