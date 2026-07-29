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
    use_rviz = LaunchConfiguration('use_rviz')
    use_lidar = LaunchConfiguration('use_lidar')
    config_file = LaunchConfiguration('config_file')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')
    lidar_scan_mode = LaunchConfiguration('lidar_scan_mode')

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

    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(amr_sensors_share, 'launch', 'rplidar_a1.launch.py')
        ),
        launch_arguments={
            'serial_port': lidar_serial_port,
            'frame_id': lidar_frame_id,
            'scan_mode': lidar_scan_mode,
        }.items(),
        condition=IfCondition(use_lidar),
    )

    keyboard_teleop = Node(
        package='amr_teleop',
        executable='keyboard_teleop',
        name='keyboard_teleop',
        output='screen',
        condition=IfCondition(teleop),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'teleop',
            default_value='false',
            description='Start keyboard teleop. The STM32 firmware already has command timeout.',
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
            'lidar_frame_id',
            default_value='lidar_link',
            description='TF frame used by physical LaserScan messages.',
        ),
        DeclareLaunchArgument(
            'lidar_scan_mode',
            default_value='',
            description='Optional RPLidar scan mode. Empty lets the driver choose the typical mode.',
        ),
        driver_launch,
        lidar_launch,
        rviz_launch,
        keyboard_teleop,
    ])
