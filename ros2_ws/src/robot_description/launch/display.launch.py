"""Launch the Onshape-exported robot model in ROS 2 / RViz.

The URDF and its STL meshes are installed with this package, so the model can
be found by package:// URIs regardless of the workspace's source location.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    """Create the ROS 2 equivalent of the old ROS 1 XML launch file."""
    # Locate the installed package, not the source checkout. This makes the
    # launch work after `colcon build` and `source install/setup.bash`.
    package_share = get_package_share_directory('robot_description')
    urdf_path = os.path.join(package_share, 'urdf', 'robot.urdf')

    # robot_state_publisher expects the complete XML text as a parameter.
    # The URDF is static, so reading it once while the launch starts is enough.
    with open(urdf_path, 'r', encoding='utf-8') as urdf_file:
        robot_description = urdf_file.read()

    # These arguments let a headless robot start the description publishers
    # without trying to open GUI applications.
    use_gui = LaunchConfiguration('use_gui')
    use_rviz = LaunchConfiguration('use_rviz')
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher')

    # A physical motor bridge publishes encoder-driven /joint_states itself.
    # These expressions ensure the demo joint publisher is then completely
    # absent, rather than becoming a second conflicting publisher.
    use_gui_joint_publisher = PythonExpression([
        "'", use_joint_state_publisher, "' == 'true' and '", use_gui, "' == 'true'",
    ])
    use_headless_joint_publisher = PythonExpression([
        "'", use_joint_state_publisher, "' == 'true' and '", use_gui, "' != 'true'",
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_gui', default_value='true',
            description='Start joint_state_publisher_gui instead of its non-GUI version.'),
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='Start RViz2 for visual inspection of the URDF.'),
        DeclareLaunchArgument(
            'use_joint_state_publisher', default_value='true',
            description=(
                'Publish demo wheel states. Set false when amr_driver is '
                'publishing real encoder-driven /joint_states.'
            )),

        # Publishes the fixed and moving transforms declared by the URDF.
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),

        # The GUI is convenient on a desktop. On a headless Jetson, pass
        # use_gui:=false to launch the non-graphical publisher instead.
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen',
            # In Humble this program reads its URDF as a positional file path;
            # that gives the GUI sliders for the model's movable joints.
            arguments=[urdf_path],
            condition=IfCondition(use_gui_joint_publisher),
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            arguments=[urdf_path],
            condition=IfCondition(use_headless_joint_publisher),
        ),

        # Place the exported CAD model in ROS's world frame. This Onshape URDF
        # uses Y as its CAD-up axis, whereas ROS uses Z-up. A +90 degree roll
        # about X maps CAD +Y onto ROS +Z, making the deck horizontal and the
        # wheels vertical. The original +90 degree yaw retains the requested
        # robot-forward direction after this axis conversion.
        #
        # After the roll, ROS Z equals original URDF Y. The lowest mesh point
        # is at Y=+0.7372923 m relative to `root`, so move root down by that
        # exact amount to place the model on the RViz z=0 ground grid.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='map_to_root',
            # Named ROS 2 arguments avoid the old positional syntax warning.
            arguments=[
                '--x', '0', '--y', '0', '--z', '-0.7372923',
                '--roll', '1.57079632679', '--pitch', '0', '--yaw', '1.57079632679',
                '--frame-id', 'map', '--child-frame-id', 'root',
            ],
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            condition=IfCondition(use_rviz),
        ),
    ])
