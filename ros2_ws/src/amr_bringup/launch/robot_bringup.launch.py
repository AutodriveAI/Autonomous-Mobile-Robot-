import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def _is_true(value: str) -> bool:
    return value.lower() in ('true', '1', 'yes', 'on')


def _select_rviz(context):
    """Start exactly one RViz instance for the selected bringup mode."""
    if not _is_true(LaunchConfiguration('use_rviz').perform(context)):
        return []

    start_nav2 = _is_true(LaunchConfiguration('start_nav2').perform(context))
    start_localisation = _is_true(
        LaunchConfiguration('start_localisation').perform(context))

    if start_nav2:
        return [
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2_nav2',
                output='screen',
                arguments=[
                    '-d',
                    os.path.join(
                        get_package_share_directory('nav2_bringup'),
                        'rviz',
                        'nav2_default_view.rviz',
                    ),
                ],
            )
        ]

    if start_localisation:
        return [
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2_localisation',
                output='screen',
                arguments=[
                    '-d',
                    os.path.join(
                        get_package_share_directory('amr_localisation'),
                        'rviz',
                        'localisation.rviz',
                    ),
                ],
            )
        ]

    return [
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2_bringup',
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
    use_lcd = LaunchConfiguration('use_lcd')
    use_lidar = LaunchConfiguration('use_lidar')
    use_realsense = LaunchConfiguration('use_realsense')
    lcd_goal_received_duration_s = LaunchConfiguration(
        'lcd_goal_received_duration_s'
    )
    lcd_goal_reached_duration_s = LaunchConfiguration(
        'lcd_goal_reached_duration_s'
    )
    start_joy_teleop = LaunchConfiguration('start_joy_teleop')
    start_keyboard_teleop = LaunchConfiguration('start_keyboard_teleop')
    start_localisation = LaunchConfiguration('start_localisation')
    start_nav2 = LaunchConfiguration('start_nav2')
    bypass_twist_mux = LaunchConfiguration('bypass_twist_mux')
    config_file = LaunchConfiguration('config_file')
    twist_mux_config_file = LaunchConfiguration('twist_mux_config_file')
    map_file = LaunchConfiguration('map')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_serial_baudrate = LaunchConfiguration('lidar_serial_baudrate')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')
    lidar_scan_mode = LaunchConfiguration('lidar_scan_mode')
    joy_dev = LaunchConfiguration('joy_dev')
    joy_deadzone = LaunchConfiguration('joy_deadzone')
    joy_autorepeat_rate = LaunchConfiguration('joy_autorepeat_rate')
    teleop_speed_ticks_per_second = LaunchConfiguration('teleop_speed_ticks_per_second')
    teleop_turn_ticks_per_second = LaunchConfiguration('teleop_turn_ticks_per_second')

    amr_description_share = get_package_share_directory('amr_description')
    amr_driver_share = get_package_share_directory('amr_driver')
    amr_localisation_share = get_package_share_directory('amr_localisation')
    amr_navigation_share = get_package_share_directory('amr_navigation')
    amr_sensors_share = get_package_share_directory('amr_sensors')
    amr_slam_share = get_package_share_directory('amr_slam')

    localisation_active = PythonExpression([
        "'", start_localisation, "' == 'true' or '", start_nav2, "' == 'true'"
    ])
    driver_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_driver_share, 'launch', 'amr_driver.launch.py')
        ),
        launch_arguments={
            'config_file': config_file,
            'cmd_vel_topic': PythonExpression([
                "'/cmd_vel_nav' if '", bypass_twist_mux, "' == 'true' else '/cmd_vel'"
            ]),
        }.items(),
    )

    description_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_description_share, 'launch', 'display.launch.py')
        ),
        launch_arguments={
            'use_gui': 'false',
            # robot_bringup owns the "exactly one RViz" policy below.
            'use_rviz': 'false',
            'use_joint_state_publisher': 'false',
        }.items(),
    )

    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_sensors_share, 'launch', 'rplidar_c1.launch.py')
        ),
        launch_arguments={
            'serial_port': lidar_serial_port,
            'serial_baudrate': lidar_serial_baudrate,
            'frame_id': lidar_frame_id,
            'scan_mode': lidar_scan_mode,
        }.items(),
        condition=IfCondition(use_lidar),
    )

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                amr_sensors_share,
                'launch',
                'realsense_d435i.launch.py',
            )
        ),
        condition=IfCondition(use_realsense),
    )

    twist_mux_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_navigation_share, 'launch', 'twist_mux.launch.py')
        ),
        launch_arguments={
            'config_file': twist_mux_config_file,
            'output_topic': '/cmd_vel',
        }.items(),
        condition=UnlessCondition(bypass_twist_mux),
    )

    localisation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_localisation_share, 'launch', 'localisation.launch.py')
        ),
        launch_arguments={
            'map': map_file,
            'use_sim_time': 'false',
            'scan_topic': '/scan',
            # robot_bringup owns the "exactly one RViz" policy below.
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
            'use_sim_time': 'false',
            # robot_bringup owns the "exactly one RViz" policy below.
            'use_rviz': 'false',
        }.items(),
        condition=IfCondition(start_nav2),
    )

    selected_rviz = OpaqueFunction(function=_select_rviz)

    lcd_status = Node(
        package='amr_bringup',
        executable='lcd_status',
        name='lcd_status',
        output='screen',
        parameters=[{
            'goal_received_duration_s': lcd_goal_received_duration_s,
            'goal_reached_duration_s': lcd_goal_reached_duration_s,
        }],
        condition=IfCondition(use_lcd),
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

    keyboard_teleop = Node(
        package='amr_teleop',
        executable='keyboard_teleop',
        name='keyboard_teleop',
        output='screen',
        remappings=[('cmd_vel', '/cmd_vel_keyboard')],
        condition=IfCondition(start_keyboard_teleop),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_lcd',
            default_value='true',
            description=(
                'Start the physical LCD navigation-status display.'
            ),
        ),
        DeclareLaunchArgument(
            'lcd_goal_received_duration_s',
            default_value='10.0',
            description=(
                'Seconds to show the new-goal message before restoring the '
                'idle mark.'
            ),
        ),
        DeclareLaunchArgument(
            'lcd_goal_reached_duration_s',
            default_value='20.0',
            description=(
                'Seconds to show the goal-reached message. Zero keeps it '
                'visible until another goal is received.'
            ),
        ),
        DeclareLaunchArgument(
            'teleop',
            default_value='false',
            description=(
                'Deprecated/no-op. Use start_joy_teleop or start_keyboard_teleop.'
            ),
        ),
        DeclareLaunchArgument(
            'start_joy_teleop',
            default_value='true',
            description='Start Logitech-style joystick teleop by default.',
        ),
        DeclareLaunchArgument(
            'start_keyboard_teleop',
            default_value='false',
            description=(
                'Try to start keyboard teleop inside this launch. Usually keep '
                'false and run keyboard_teleop in an interactive terminal.'
            ),
        ),
        DeclareLaunchArgument(
            'start_localisation',
            default_value='false',
            description=(
                'Start physical robot localization only. If use_rviz is true '
                'and start_nav2 is false, this opens the localization RViz config.'
            ),
        ),
        DeclareLaunchArgument(
            'start_nav2',
            default_value='false',
            description=(
                'Start AMCL localization and Nav2 autonomous navigation for '
                'the physical robot. Nav2 publishes to /cmd_vel_nav, then '
                'twist_mux outputs /cmd_vel for amr_driver.'
            ),
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='Start RViz with encoder-derived joint states.',
        ),
        DeclareLaunchArgument(
            'use_nav2_rviz',
            default_value='false',
            description=(
                'Deprecated/no-op. RViz is now selected by use_rviz plus '
                'start_nav2/start_localisation priority.'
            ),
        ),
        DeclareLaunchArgument(
            'bypass_twist_mux',
            default_value='false',
            description=(
                'Diagnostic mode: do not launch twist_mux, and make amr_driver '
                'subscribe directly to /cmd_vel_nav from Nav2 velocity_smoother.'
            ),
        ),
        DeclareLaunchArgument(
            'use_lidar',
            default_value='true',
            description='Start the physical RPLidar driver and publish /scan.',
        ),
        DeclareLaunchArgument(
            'use_realsense',
            default_value='true',
            description=(
                'Start the physical RealSense D435i RGB-only stream on '
                '/camera_rgb and /camera_rgb/compressed.'
            ),
        ),
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(amr_driver_share, 'config', 'amr_driver.yaml'),
            description='Path to the amr_driver parameter YAML file.',
        ),
        DeclareLaunchArgument(
            'twist_mux_config_file',
            default_value=os.path.join(amr_navigation_share, 'config', 'twist_mux.yaml'),
            description='Path to the twist_mux parameter YAML file.',
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
            default_value=os.path.join(amr_navigation_share, 'config', 'nav2_params_real.yaml'),
            description='Nav2 navigation parameter YAML.',
        ),
        DeclareLaunchArgument(
            'lidar_serial_port',
            default_value='/dev/rplidar',
            description='Linux device path for the physical RPLidar.',
        ),
        DeclareLaunchArgument(
            'lidar_serial_baudrate',
            default_value='460800',
            description='Physical RPLidar serial baud rate. C1 uses 460800.',
        ),
        DeclareLaunchArgument(
            'lidar_frame_id',
            default_value='lidar_scan_link',
            description='TF frame used by physical LaserScan messages.',
        ),
        DeclareLaunchArgument(
            'lidar_scan_mode',
            default_value='',
            description=(
                'Optional RPLidar scan mode. Empty lets the driver choose '
                'the typical mode.'
            ),
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
        lcd_status,
        selected_rviz,
        driver_launch,
        lidar_launch,
        realsense_launch,
        description_launch,
        twist_mux_launch,
        localisation_launch,
        nav2_launch,
        joy_node,
        joy_teleop,
        keyboard_teleop,
    ])
