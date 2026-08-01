import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory('amr_navigation')

    config_file = LaunchConfiguration('config_file')
    output_topic = LaunchConfiguration('output_topic')

    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        output='screen',
        parameters=[config_file],
        # twist_mux publishes on cmd_vel_out by convention. We remap that to
        # the command topic consumed by the robot/simulator.
        remappings=[
            ('cmd_vel_out', output_topic),
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(package_share, 'config', 'twist_mux.yaml'),
            description='Path to twist_mux parameter YAML.',
        ),
        DeclareLaunchArgument(
            'output_topic',
            default_value='/cmd_vel',
            description='Final selected velocity command topic.',
        ),
        twist_mux_node,
    ])
