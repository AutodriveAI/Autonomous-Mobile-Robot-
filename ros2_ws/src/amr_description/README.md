# AMR CAD Description

This package contains the colored OBJ/MTL visual export from Onshape, but the
main URDF is simplified into a small robotics-friendly TF tree.

## Files

- `urdf/robot.urdf.xacro`: active simplified CAD-based robot description used by display and simulation launch files.
- `urdf/gazebo.xacro`: Gazebo-specific contact tuning and plugins.
- `urdf/ros2_control.xacro`: ros2_control wheel-joint interface description.
- `meshes/`: OBJ and MTL files exported from Onshape.

Reference-only description exports are no longer kept inside the active package.
They are preserved at the repository root under:

```text
reference_descriptions/
```

This keeps `ros2_ws/src/amr_description` focused on the model that is
actually launched, while still preserving older/raw exports for comparison.

## Simplified TF Tree

```text
base_link
├── chassis_link
├── left_wheel_link
├── right_wheel_link
├── left_caster_link
├── right_caster_link
├── lidar_link
├── imu_link
└── antenna_link
```

The visual meshes are still detailed and colored, but they are grouped under
these few links so RViz and TF stay readable.

## Collision and inertial model

The active Xacro model uses a deliberately simple physics approximation:

- `chassis_link`: one vertical cylinder collision and approximate body inertia.
  The first-pass body model uses mass `2.0 kg`, diameter `0.20 m`, height
  `0.21 m`, is shifted `0.025 m` in the positive X/red-axis direction, and is
  placed so its bottom is about `0.02 m` above the RViz/Gazebo ground plane.
  This keeps tiny objects below the bottom plate from colliding with the main
  body.
- `left_wheel_link` / `right_wheel_link`: one cylinder collision per wheel.
- `left_caster_link` / `right_caster_link`: one sphere collision per caster.
- `antenna_link`: two cylinder collisions, one for each antenna.
- `lidar_link` and `imu_link`: inertial properties only for now, no collision.

The detailed CAD meshes are only used for `<visual>`. They are not used for
`<collision>`, because detailed CAD collision is computationally heavier and can
make Gazebo physics unstable.

The mass values are first-pass placeholders. Update them later after weighing
the physical robot and the wheel assemblies.

## Gazebo control path

Gazebo simulation currently uses the classic `gazebo_ros_diff_drive` plugin.

We tried the `diff_drive_controller` + `gazebo_ros2_control/GazeboSystem` path,
but for this Gazebo Classic model it behaved too much like an ideal wheel
velocity actuator and could inject unrealistic impulses at higher speeds. The
ros2_control Xacro/config files are still kept in the package for later
hardware-interface work, but they are not the active simulation actuator path.

The simulated command path is:

```text
/cmd_vel
  ↓
gazebo_ros_diff_drive
  ↓
left_wheel_joint + right_wheel_joint
```

The active Gazebo plugin lives in:

```text
urdf/gazebo.xacro
```

Important first-pass values:

- `wheel_separation: 0.175`
- `wheel_diameter: 0.065`
- `max_wheel_torque: 2.0`
- `max_wheel_acceleration: 1.0`
- physical testing showed about `0.25 m/s` linear command and `2.27 rad/s`
  turn command are useful teleop defaults / minimum meaningful motion values,
  not true maximum robot speeds

## Visualize

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_description display.launch.py
```

## Spawn in Gazebo

The simulation launch file starts Gazebo using this package's local
`worlds/obstacles.world`, publishes this package's active `robot.urdf.xacro`,
and spawns the robot into Gazebo.

The local world also uses primitive obstacle shapes instead of
`model://construction_barrel` or `model://construction_cone`, because missing
Gazebo model assets can leave Gazebo stuck at "Preparing your world...".

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select amr_description --symlink-install
source install/setup.bash
ros2 launch amr_description sim.launch.py
```

The default installed world path is:

```text
install/amr_description/share/amr_description/worlds/obstacles.world
```

You can override it with:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_description sim.launch.py world:=/absolute/path/to/another.world
```
