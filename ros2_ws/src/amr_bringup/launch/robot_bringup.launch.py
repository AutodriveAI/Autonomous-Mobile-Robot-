import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_rviz = LaunchConfiguration('use_rviz')
    use_lidar = LaunchConfiguration('use_lidar')
    start_joy_teleop = LaunchConfiguration('start_joy_teleop')
    start_keyboard_teleop = LaunchConfiguration('start_keyboard_teleop')
    config_file = LaunchConfiguration('config_file')
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
    amr_sensors_share = get_package_share_directory('amr_sensors')

    driver_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_driver_share, 'launch', 'amr_driver.launch.py')
        ),
        launch_arguments={
            'config_file': config_file,
        }.items(),
    )

    description_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_description_share, 'launch', 'display.launch.py')
        ),
        launch_arguments={
            'use_gui': 'false',
            'use_rviz': use_rviz,
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
        condition=IfCondition(start_keyboard_teleop),
    )

    return LaunchDescription([
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
            'use_rviz',
            default_value='true',
            description='Start RViz with encoder-derived joint states.',
        ),
        DeclareLaunchArgument(
            'use_lidar',
            default_value='true',
            description='Start the physical RPLidar driver and publish /scan.',
        ),
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(amr_driver_share, 'config', 'amr_driver.yaml'),
            description='Path to the amr_driver parameter YAML file.',
        ),
        DeclareLaunchArgument(
            'lidar_serial_port',
            default_value='/dev/ttyUSB0',
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
            description='Optional RPLidar scan mode. Empty lets the driver choose the typical mode.',
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
        driver_launch,
        lidar_launch,
        description_launch,
        joy_node,
        joy_teleop,
        keyboard_teleop,
    ])
