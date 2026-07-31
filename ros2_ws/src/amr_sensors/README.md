# AMR Sensors

`amr_sensors` contains launch files and notes for physical sensors on the AMR.
Right now it mainly wraps the physical RPLIDAR A1 driver so the rest of the
robot can use a consistent `/scan` topic and `lidar_scan_link` frame.

## Launch the RPLIDAR A1 only

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_sensors rplidar_a1.launch.py
```

If the lidar appears on a different serial port:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_sensors rplidar_a1.launch.py serial_port:=/dev/ttyUSB1
```

Check that scans are being published:

```bash
ros2 topic hz /scan
```

## Stop and restart the lidar motor

The RPLIDAR A1 motor can be stopped when we are not scanning and restarted when
mapping, localization, or obstacle detection needs scan data again.

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
