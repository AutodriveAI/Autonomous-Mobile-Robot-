import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = get_package_share_directory('amr_cad_description')
    urdf_path = os.path.join(package_share, 'urdf', 'robot.urdf.xacro')
    rviz_config_path = os.path.join(package_share, 'rviz', 'display.rviz')
    robot_description = ParameterValue(Command(['xacro ', urdf_path]), value_type=str)

    use_gui = LaunchConfiguration('use_gui')
    use_rviz = LaunchConfiguration('use_rviz')
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher')

    use_gui_joint_publisher = PythonExpression([
        "'", use_joint_state_publisher, "' == 'true' and '", use_gui, "' == 'true'",
    ])
    use_headless_joint_publisher = PythonExpression([
        "'", use_joint_state_publisher, "' == 'true' and '", use_gui, "' != 'true'",
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_gui',
            default_value='true',
            description='Start joint_state_publisher_gui for movable joints.',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='Start RViz2.',
        ),
        DeclareLaunchArgument(
            'use_joint_state_publisher',
            default_value='true',
            description='Publish demo joint states for visual inspection.',
        ),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen',
            condition=IfCondition(use_gui_joint_publisher),
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            condition=IfCondition(use_headless_joint_publisher),
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='map_to_base_link',
            arguments=[
                '--x', '0', '--y', '0', '--z', '0.034410',
                '--roll', '0', '--pitch', '0', '--yaw', '0',
                '--frame-id', 'map', '--child-frame-id', 'base_link',
            ],
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config_path],
            condition=IfCondition(use_rviz),
        ),
    ])
