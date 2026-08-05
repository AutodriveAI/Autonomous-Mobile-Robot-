# AMR Sensors

`amr_sensors` contains launch files and notes for physical sensors on the AMR.
Right now it mainly wraps the physical RPLIDAR C1 driver so the rest of the
robot can use a consistent `/scan` topic and `lidar_scan_link` frame.

## Launch the RealSense D435i for remote RGB viewing

The RealSense launch enables only RGB at 640x480 and 15 Hz. Depth, infrared,
IMU, alignment, and point-cloud processing are off by default. Raw color is
available as `/camera_rgb`; when `compressed_image_transport` is installed,
the same camera publisher provides JPEG frames on `/camera_rgb/compressed` to
compressed-transport subscribers. Sensor-data QoS is used so network delays
drop old frames instead of building a reliable-delivery backlog.
JPEG quality is set to 70; a typical frame is around 70--80 KB rather than the
900 KB raw RGB frame (scene complexity changes the exact compressed size).

```bash
cd ~/Autonomous_Mobile_Robot/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/foxy/setup.bash
source install/setup.bash
ros2 launch amr_sensors realsense_d435i.launch.py
```

Confirm that RGB frames and the compressed transport are available:

```bash
ros2 topic hz /camera_rgb
ros2 run image_transport list_transports
```

On the Humble development machine, build the workspace copy of `amr_sensors`
once (or rebuild it after pulling this change):

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select amr_sensors
```

Then view the stream locally on that machine without X forwarding:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=0
ros2 run amr_sensors remote_rgb_viewer
```

This viewer subscribes directly to `/camera_rgb/compressed` with best-effort,
volatile QoS and a keep-last queue depth of one. Decoding is performed on the
development machine, and a delayed frame is overwritten by the newest frame.
Press `q`, `Esc`, or Ctrl-C to close it.

### View the remote RGB stream in RViz

The custom viewer is optional. RViz can subscribe through image transport
directly. On the Humble development machine, RViz itself does not require the
robot workspace overlay:

```bash
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=0
rviz2
```

In RViz, add an **Image** display and configure it as follows:

- Topic: `/camera_rgb`
- Transport Hint: `compressed`
- Reliability Policy: `Best Effort`
- Durability Policy: `Volatile`
- Queue Size: `1`

Select the base topic `/camera_rgb`, not `/camera_rgb/compressed`.
`image_transport` adds the `/compressed` suffix after the transport hint is
selected. If `compressed` is missing from the Transport Hint choices, install
the Humble decoder and restart RViz:

```bash
sudo apt install ros-humble-compressed-image-transport
```

The one-frame queue and best-effort QoS allow delayed frames to be discarded
instead of shown later.

Depth can still be enabled explicitly for a later task:

```bash
ros2 launch amr_sensors realsense_d435i.launch.py enable_depth:=true
```

## RealSense in the physical robot bringup

`amr_bringup/robot_bringup.launch.py` starts this RGB-only RealSense launch by
default. Disable it when the camera is disconnected or not required:

```bash
ros2 launch amr_bringup robot_bringup.launch.py use_realsense:=false
```

## Launch the RPLIDAR C1 only

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_sensors rplidar_c1.launch.py
```

If the lidar appears on a different serial port:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_sensors rplidar_c1.launch.py serial_port:=/dev/ttyUSB1
```

Check that scans are being published:

```bash
ros2 topic hz /scan
```

## Important C1 defaults

The active launch file uses these defaults:

- serial port: `/dev/ttyUSB0`
- baud rate: `460800`
- LaserScan topic: `/scan`
- LaserScan frame: `lidar_scan_link`
- angle compensation: enabled
- scan mode: empty string, meaning the driver chooses the typical supported mode

Override the baud rate only if the physical driver/documentation for your exact
unit says to:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_sensors rplidar_c1.launch.py serial_baudrate:=460800
```

## Stop and restart the lidar motor

The RPLidar ROS driver may expose start/stop motor services while the node is
running. Use them when the services are available and you want to pause scanning
without closing the whole driver.

While the ROS 2 lidar node is running, stop both rotation and useful scan output:

```bash
ros2 service call /stop_motor std_srvs/srv/Empty "{}"
```

Restart the motor and scanning:

```bash
ros2 service call /start_motor std_srvs/srv/Empty "{}"
```

Confirm that the services exist:

```bash
ros2 service list | grep motor
```

Expected services:

```text
/start_motor
/stop_motor
```

## Expected motor behavior

If the lidar starts spinning only after launching `rplidar_ros`, that is normal.
The driver starts the motor and scan process during initialization.

If the lidar starts spinning immediately after connecting power, before any ROS
node is launched, something else may be opening the serial port or the adapter
may be holding the motor-enable signal active.

Check whether a process is using the lidar port:

```bash
sudo lsof /dev/ttyUSB0
```

or:

```bash
sudo fuser -v /dev/ttyUSB0
```

Check for an already-running lidar node:

```bash
ps aux | grep -E "rplidar|sllidar"
```

If nothing is accessing `/dev/ttyUSB0` but the motor still spins immediately,
the likely cause is the USB adapter, clone adapter, or motor-control wiring.
