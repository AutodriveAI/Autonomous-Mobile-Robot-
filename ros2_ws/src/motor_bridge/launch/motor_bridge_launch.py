import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_config = os.path.join(
        get_package_share_directory('motor_bridge'), 'config', 'motor_bridge.yaml')

    config_arg = DeclareLaunchArgument(
        'config_file',
        default_value=default_config,
        description='Path to the motor_bridge parameter YAML file',
    )

    motor_bridge_node = Node(
        package='motor_bridge',
        executable='motor_bridge_node',
        name='motor_bridge_node',
        output='screen',
        parameters=[LaunchConfiguration('config_file')],
    )

    return LaunchDescription([config_arg, motor_bridge_node])
