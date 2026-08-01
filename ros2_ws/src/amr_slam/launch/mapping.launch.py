import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory('amr_slam')

    slam_params_file = LaunchConfiguration('slam_params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    use_rviz = LaunchConfiguration('use_rviz')
    rviz_config = LaunchConfiguration('rviz_config')

    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='sync_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            slam_params_file,
            {'use_sim_time': use_sim_time},
        ],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_mapping',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'slam_params_file',
            default_value=os.path.join(
                package_share,
                'config',
                'mapper_params_online_sync.yaml',
            ),
            description='Full path to Slam Toolbox mapping parameters.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock. Keep false for the physical robot.',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Open RViz with AMR mapping displays and Slam Toolbox panel.',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=os.path.join(package_share, 'rviz', 'mapping.rviz'),
            description='RViz config for mapping.',
        ),
        slam_toolbox_node,
        rviz_node,
    ])
