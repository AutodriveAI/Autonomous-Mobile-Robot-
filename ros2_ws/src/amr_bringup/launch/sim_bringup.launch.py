import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    teleop = LaunchConfiguration('teleop')
    start_keyboard_teleop = LaunchConfiguration('start_keyboard_teleop')
    use_rviz = LaunchConfiguration('use_rviz')
    world = LaunchConfiguration('world')
    timeout_s = LaunchConfiguration('timeout_s')

    amr_description_share = get_package_share_directory('amr_description')

    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_description_share, 'launch', 'sim.launch.py')
        ),
        launch_arguments={
            'world': world,
        }.items(),
    )

    rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_description_share, 'launch', 'display.launch.py')
        ),
        launch_arguments={
            'use_gui': 'false',
            'use_rviz': 'true',
            'use_joint_state_publisher': 'false',
        }.items(),
        condition=IfCondition(use_rviz),
    )

    cmd_vel_timeout = Node(
        package='amr_teleop',
        executable='cmd_vel_timeout',
        name='cmd_vel_timeout',
        output='screen',
        parameters=[{
            'input_topic': '/cmd_vel_raw',
            'output_topic': '/cmd_vel',
            'timeout_s': timeout_s,
        }],
        condition=IfCondition(teleop),
    )

    keyboard_teleop = Node(
        package='amr_teleop',
        executable='keyboard_teleop',
        name='keyboard_teleop',
        output='screen',
        remappings=[('cmd_vel', 'cmd_vel_raw')],
        condition=IfCondition(start_keyboard_teleop),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'teleop',
            default_value='false',
            description='Start the /cmd_vel_raw -> /cmd_vel timeout safety node.',
        ),
        DeclareLaunchArgument(
            'start_keyboard_teleop',
            default_value='false',
            description=(
                'Try to start keyboard teleop inside this launch. Usually leave '
                'false and run keyboard_teleop in a separate terminal instead.'
            ),
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Start RViz with Gazebo joint states instead of fake joints.',
        ),
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(amr_description_share, 'worlds', 'obstacles.world'),
            description='Gazebo world file to load.',
        ),
        DeclareLaunchArgument(
            'timeout_s',
            default_value='0.2',
            description='Simulated command timeout for teleop commands.',
        ),
        sim_launch,
        rviz_launch,
        cmd_vel_timeout,
        keyboard_teleop,
    ])
