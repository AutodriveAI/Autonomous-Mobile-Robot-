# AMR CAD Description

This package contains the colored OBJ/MTL visual export from Onshape, but the
main URDF is simplified into a small robotics-friendly TF tree.

## Files

- `urdf/robot.urdf.xacro`: active simplified robot description used by the launch file.
- `urdf/robot.urdf`: older plain-URDF copy kept as a fallback/reference.
- `urdf/onshape_raw.urdf`: original Onshape-style export kept as a reference.
- `meshes/`: OBJ and MTL files exported from Onshape.

The previous STL-based `robot_description` package is no longer active inside
`ros2_ws/src`. It is preserved at the repository root under:

```text
reference_descriptions/robot_description_stl_reference
```

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
  The first-pass body model uses mass `1.5 kg`, diameter `0.20 m`, height
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

## Visualize

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch amr_cad_description display.launch.py
```
