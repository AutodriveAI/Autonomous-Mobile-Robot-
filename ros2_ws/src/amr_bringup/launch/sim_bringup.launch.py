import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def _is_true(value: str) -> bool:
    return value.lower() in ('true', '1', 'yes', 'on')


def _select_rviz(context):
    """Start one RViz config appropriate for the selected sim bringup mode."""
    if not _is_true(LaunchConfiguration('use_rviz').perform(context)):
        return []

    start_nav2 = _is_true(LaunchConfiguration('start_nav2').perform(context))
    start_localisation = _is_true(
        LaunchConfiguration('start_localisation').perform(context))

    if start_nav2 or start_localisation:
        return [
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2_nav2',
                output='screen',
                arguments=[
                    '-d',
                    os.path.join(
                        get_package_share_directory('amr_navigation'),
                        'rviz',
                        'nav2_real_robot.rviz',
                    ),
                ],
            )
        ]

    return [
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2_sim_bringup',
            output='screen',
            arguments=[
                '-d',
                os.path.join(
                    get_package_share_directory('amr_description'),
                    'rviz',
                    'display.rviz',
                ),
            ],
        )
    ]


def generate_launch_description():
    start_joy_teleop = LaunchConfiguration('start_joy_teleop')
    start_keyboard_teleop = LaunchConfiguration('start_keyboard_teleop')
    start_localisation = LaunchConfiguration('start_localisation')
    start_nav2 = LaunchConfiguration('start_nav2')
    use_rviz = LaunchConfiguration('use_rviz')
    world = LaunchConfiguration('world')
    map_file = LaunchConfiguration('map')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    joy_dev = LaunchConfiguration('joy_dev')
    joy_deadzone = LaunchConfiguration('joy_deadzone')
    joy_autorepeat_rate = LaunchConfiguration('joy_autorepeat_rate')
    joy_enable_button = LaunchConfiguration('joy_enable_button')
    teleop_speed_ticks_per_second = LaunchConfiguration('teleop_speed_ticks_per_second')
    teleop_turn_ticks_per_second = LaunchConfiguration('teleop_turn_ticks_per_second')
    extra_gazebo_model_path = LaunchConfiguration('extra_gazebo_model_path')

    amr_description_share = get_package_share_directory('amr_description')
    amr_localisation_share = get_package_share_directory('amr_localisation')
    amr_navigation_share = get_package_share_directory('amr_navigation')
    amr_slam_share = get_package_share_directory('amr_slam')

    localisation_active = PythonExpression([
        "'", start_localisation, "' == 'true' or '", start_nav2, "' == 'true'"
    ])

    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_description_share, 'launch', 'sim.launch.py')
        ),
        launch_arguments={
            'world': world,
            'extra_gazebo_model_path': extra_gazebo_model_path,
        }.items(),
    )

    twist_mux_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_navigation_share, 'launch', 'twist_mux.launch.py')
        ),
        launch_arguments={
            'output_topic': '/cmd_vel',
        }.items(),
    )

    localisation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_localisation_share, 'launch', 'localisation.launch.py')
        ),
        launch_arguments={
            'map': map_file,
            'use_sim_time': 'true',
            'scan_topic': '/scan',
            'use_rviz': 'false',
        }.items(),
        condition=IfCondition(localisation_active),
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_navigation_share, 'launch', 'nav2.launch.py')
        ),
        launch_arguments={
            'params_file': nav2_params_file,
            'use_sim_time': 'true',
            # sim_bringup owns the one-RViz policy. When localization/Nav2 is
            # active, _select_rviz starts the Nav2 RViz config.
            'use_rviz': 'false',
        }.items(),
        condition=IfCondition(start_nav2),
    )

    selected_rviz = OpaqueFunction(function=_select_rviz)

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
            'enable_button': joy_enable_button,
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
            'start_nav2',
            default_value='false',
            description=(
                'Start AMCL localization and Nav2 autonomous navigation for Gazebo. '
                'Nav2 publishes to /cmd_vel_nav, then twist_mux outputs /cmd_vel.'
            ),
        ),
        DeclareLaunchArgument(
            'start_localisation',
            default_value='false',
            description=(
                'Start AMCL localization and map server for Gazebo without '
                'starting Nav2.'
            ),
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='Start RViz with Gazebo joint states instead of fake joints.',
        ),
        DeclareLaunchArgument(
            'use_nav2_rviz',
            default_value='false',
            description=(
                'Deprecated/no-op. RViz is selected by use_rviz plus '
                'start_localisation/start_nav2.'
            ),
        ),
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(amr_description_share, 'worlds', 'simple_home.world'),
            description='Gazebo world file to load.',
        ),
        DeclareLaunchArgument(
            'extra_gazebo_model_path',
            default_value='',
            description=(
                'Optional extra Gazebo model directory for external worlds, '
                'for example turtlebot3_gazebo/models when using '
                'turtlebot3_house.world.'
            ),
        ),
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(
                amr_slam_share,
                'maps',
                'LakecityFlat4AMap.yaml',
            ),
            description='Saved map YAML used by AMCL when start_nav2 is true.',
        ),
        DeclareLaunchArgument(
            'nav2_params_file',
            default_value=os.path.join(amr_navigation_share, 'config', 'nav2_params.yaml'),
            description='Nav2 navigation parameter YAML.',
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
            'joy_enable_button',
            default_value='4',
            description=(
                'Deadman button index used by joy_teleop. The Logitech left '
                'bumper is normally button 4; use -1 to disable the deadman.'
            ),
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
        selected_rviz,
        sim_launch,
        twist_mux_launch,
        localisation_launch,
        nav2_launch,
        keyboard_teleop,
        joy_node,
        joy_teleop,
    ])
