from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    channel_type = LaunchConfiguration('channel_type')
    serial_port = LaunchConfiguration('serial_port')
    serial_baudrate = LaunchConfiguration('serial_baudrate')
    frame_id = LaunchConfiguration('frame_id')
    inverted = LaunchConfiguration('inverted')
    angle_compensate = LaunchConfiguration('angle_compensate')
    scan_mode = LaunchConfiguration('scan_mode')

    rplidar_node = Node(
        package='rplidar_ros',
        executable='rplidar_node',
        name='rplidar_node',
        output='screen',
        parameters=[{
            'channel_type': channel_type,
            'serial_port': serial_port,
            'serial_baudrate': serial_baudrate,
            'frame_id': frame_id,
            'inverted': inverted,
            'angle_compensate': angle_compensate,
            # Empty string means: let the RPLidar driver choose its typical scan mode.
            # This is the most reliable default for the A1 because supported scan mode
            # names can vary across firmware/SDK versions.
            'scan_mode': scan_mode,
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'channel_type',
            default_value='serial',
            description='RPLidar communication channel type.',
        ),
        DeclareLaunchArgument(
            'serial_port',
            default_value='/dev/ttyUSB0',
            description='Linux device path for the physical RPLidar USB adapter.',
        ),
        DeclareLaunchArgument(
            'serial_baudrate',
            default_value='115200',
            description='RPLidar A1 serial baud rate.',
        ),
        DeclareLaunchArgument(
            'frame_id',
            default_value='lidar_scan_link',
            description='TF frame used in the LaserScan message header.',
        ),
        DeclareLaunchArgument(
            'inverted',
            default_value='false',
            description='Invert scan direction if the lidar is mounted upside down.',
        ),
        DeclareLaunchArgument(
            'angle_compensate',
            default_value='true',
            description='Ask the driver to fill/regularize scan angle bins.',
        ),
        DeclareLaunchArgument(
            'scan_mode',
            default_value='',
            description='Optional RPLidar scan mode. Leave empty for typical mode.',
        ),
        rplidar_node,
    ])
