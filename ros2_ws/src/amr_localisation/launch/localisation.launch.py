import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _check_map_file(context):
    """Warn clearly if the occupancy-grid map YAML is missing."""
    map_yaml = LaunchConfiguration('map').perform(context)

    if os.path.exists(map_yaml):
        return [LogInfo(msg=f'AMCL localization map found: {map_yaml}')]

    return [
        LogInfo(
            msg=(
                'WARNING: AMCL localization map YAML is missing: '
                f'{map_yaml}. nav2_map_server needs a .yaml file that points '
                'to the matching .pgm image.'
            )
        ),
    ]


def generate_launch_description():
    package_share = get_package_share_directory('amr_localisation')
    slam_share = get_package_share_directory('amr_slam')

    map_yaml = LaunchConfiguration('map')
    amcl_params_file = LaunchConfiguration('amcl_params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    scan_topic = LaunchConfiguration('scan_topic')
    use_rviz = LaunchConfiguration('use_rviz')
    rviz_config = LaunchConfiguration('rviz_config')

    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[
            amcl_params_file,
            {
                'yaml_filename': map_yaml,
                'use_sim_time': ParameterValue(use_sim_time, value_type=bool),
            },
        ],
    )

    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[
            amcl_params_file,
            {
                'use_sim_time': ParameterValue(use_sim_time, value_type=bool),
                'scan_topic': scan_topic,
            },
        ],
        remappings=[
            ('scan', scan_topic),
        ],
    )

    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[
            amcl_params_file,
            {
                'use_sim_time': ParameterValue(use_sim_time, value_type=bool),
                'autostart': True,
                'node_names': ['map_server', 'amcl'],
            },
        ],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_localisation',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(
                slam_share,
                'maps',
                'LakecityFlat4AMap.yaml',
            ),
            description='Saved occupancy-grid map YAML loaded by nav2_map_server.',
        ),
        DeclareLaunchArgument(
            'amcl_params_file',
            default_value=os.path.join(package_share, 'config', 'amcl.yaml'),
            description='AMCL and map server parameter file.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock. Keep false for the physical robot.',
        ),
        DeclareLaunchArgument(
            'scan_topic',
            default_value='/scan',
            description='LaserScan topic consumed by AMCL.',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Open RViz with localization displays.',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=os.path.join(package_share, 'rviz', 'localisation.rviz'),
            description='RViz config for localization.',
        ),
        OpaqueFunction(function=_check_map_file),
        map_server,
        amcl,
        lifecycle_manager,
        rviz_node,
    ])
