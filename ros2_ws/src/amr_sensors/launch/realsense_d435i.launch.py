"""Launch the RealSense D435i as a low-latency RGB camera."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    rgb_topic = LaunchConfiguration('rgb_topic')
    color_profile = LaunchConfiguration('color_profile')
    depth_profile = LaunchConfiguration('depth_profile')
    enable_depth = LaunchConfiguration('enable_depth')
    enable_pointcloud = LaunchConfiguration('enable_pointcloud')
    align_depth = LaunchConfiguration('align_depth')

    camera_node = Node(
        package='realsense2_camera',
        executable='realsense2_camera_node',
        namespace='camera',
        name='camera',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'device_type': 'd435i',
            'enable_color': True,
            'enable_depth': enable_depth,
            # The D435i also contains IMU and infrared sensors. The Foxy
            # wrapper may otherwise start them from its internal defaults,
            # even though this launch only needs RGB and depth. On Jetson the
            # IMU IIO devices additionally require separate sysfs permissions.
            'enable_gyro': False,
            'enable_accel': False,
            'unite_imu_method': 0,
            'enable_infra1': False,
            'enable_infra2': False,
            'rgb_camera.profile': color_profile,
            # Best-effort sensor-data QoS avoids reliable-delivery backlogs
            # when frames cross a slower wireless link. Viewers should also
            # use a keep-last queue of one so a late frame is dropped.
            'color_qos': 'SENSOR_DATA',
            'color_info_qos': 'SENSOR_DATA',
            'depth_qos': 'SENSOR_DATA',
            'depth_info_qos': 'SENSOR_DATA',
            # The Foxy compressed-image plugin derives this parameter name
            # from the RealSense wrapper's original color topic. Quality 70 is
            # a useful bandwidth/detail compromise for remote monitoring.
            '.color.image_raw.jpeg_quality': 70,
            # Wrapper 4.51.1 can select value 3 although this D435i firmware
            # exposes only 0..2. Use 60 Hz anti-flicker explicitly.
            'rgb_camera.power_line_frequency': 2,
            'depth_module.profile': depth_profile,
            'pointcloud.enable': enable_pointcloud,
            'align_depth.enable': align_depth,
            'enable_sync': False,
            'initial_reset': False,
        }],
        # The Foxy RealSense wrapper publishes this stream as
        # /camera/color/image_raw. Give the robot application a short, stable
        # topic while leaving depth and camera-info topics in their native
        # /camera namespace.
        remappings=[
            ('/camera/color/image_raw', rgb_topic),
            # image_transport derives this transport topic before the raw-topic
            # remap is applied, so remap it explicitly to the same stable base.
            ('/camera/color/image_raw/compressed', [rgb_topic, '/compressed']),
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'rgb_topic',
            default_value='/camera_rgb',
            description='Output topic for raw RGB sensor_msgs/Image frames.',
        ),
        DeclareLaunchArgument(
            'color_profile',
            default_value='640x480x15',
            description='RealSense color profile in WIDTHxHEIGHTxFPS form.',
        ),
        DeclareLaunchArgument(
            'depth_profile',
            default_value='640x480x15',
            description='RealSense depth profile in WIDTHxHEIGHTxFPS form.',
        ),
        DeclareLaunchArgument(
            'enable_depth',
            default_value='false',
            description=(
                'Opt in to the native depth stream; disabled for RGB-only '
                'operation.'
            ),
        ),
        DeclareLaunchArgument(
            'enable_pointcloud',
            default_value='false',
            description=(
                'Generate the depth point cloud (computationally expensive).'
            ),
        ),
        DeclareLaunchArgument(
            'align_depth',
            default_value='false',
            description='Publish depth aligned to the RGB optical frame.',
        ),
        camera_node,
    ])
