import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    start_joy_teleop = LaunchConfiguration('start_joy_teleop')
    start_keyboard_teleop = LaunchConfiguration('start_keyboard_teleop')
    use_rviz = LaunchConfiguration('use_rviz')
    world = LaunchConfiguration('world')
    joy_dev = LaunchConfiguration('joy_dev')
    joy_deadzone = LaunchConfiguration('joy_deadzone')
    joy_autorepeat_rate = LaunchConfiguration('joy_autorepeat_rate')
    teleop_speed_ticks_per_second = LaunchConfiguration('teleop_speed_ticks_per_second')
    teleop_turn_ticks_per_second = LaunchConfiguration('teleop_turn_ticks_per_second')

    amr_description_share = get_package_share_directory('amr_description')
    amr_navigation_share = get_package_share_directory('amr_navigation')

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

    twist_mux_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_navigation_share, 'launch', 'twist_mux.launch.py')
        ),
        launch_arguments={
            'output_topic': '/cmd_vel',
        }.items(),
    )

    keyboard_teleop = Node(
        package='amr_teleop',
        executable='keyboard_teleop',
        name='keyboard_teleop',
        output='screen',
        remappings=[('cmd_vel', '/cmd_vel_keyboard')],
        condition=IfCondition(start_keyboard_teleop),
    )

    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        output='screen',
        parameters=[{
            'dev': joy_dev,
            'deadzone': joy_deadzone,
            'autorepeat_rate': joy_autorepeat_rate,
        }],
        condition=IfCondition(start_joy_teleop),
    )

    joy_teleop = Node(
        package='amr_teleop',
        executable='joy_teleop',
        name='joy_teleop',
        output='screen',
        remappings=[('cmd_vel', '/cmd_vel_joy')],
        parameters=[{
            'speed_ticks_per_second': teleop_speed_ticks_per_second,
            'turn_ticks_per_second': teleop_turn_ticks_per_second,
        }],
        condition=IfCondition(start_joy_teleop),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'start_joy_teleop',
            default_value='true',
            description='Start Logitech-style joystick teleop by default.',
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
            description='Deprecated/no-op. Gazebo and twist_mux own command timeout behavior.',
        ),
        DeclareLaunchArgument(
            'joy_dev',
            default_value='/dev/input/js0',
            description='Linux joystick device for the Logitech gamepad.',
        ),
        DeclareLaunchArgument(
            'joy_deadzone',
            default_value='0.08',
            description='Deadzone applied by the standard joy_node driver.',
        ),
        DeclareLaunchArgument(
            'joy_autorepeat_rate',
            default_value='20.0',
            description='Rate at which joy_node republishes held joystick state.',
        ),
        DeclareLaunchArgument(
            'teleop_speed_ticks_per_second',
            default_value='100.0',
            description='Full-stick forward wheel target used by joy_teleop.',
        ),
        DeclareLaunchArgument(
            'teleop_turn_ticks_per_second',
            default_value='100.0',
            description='Full-stick in-place turn wheel target used by joy_teleop.',
        ),
        sim_launch,
        rviz_launch,
        twist_mux_launch,
        keyboard_teleop,
        joy_node,
        joy_teleop,
    ])
