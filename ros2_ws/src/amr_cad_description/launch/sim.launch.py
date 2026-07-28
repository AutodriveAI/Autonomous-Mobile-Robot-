import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = get_package_share_directory('amr_cad_description')
    gazebo_ros_share = get_package_share_directory('gazebo_ros')
    package_share_parent = os.path.dirname(package_share)

    robot_xacro_path = os.path.join(package_share, 'urdf', 'robot.urdf.xacro')
    default_world_path = os.path.join(package_share, 'worlds', 'obstacles.world')

    robot_description = ParameterValue(
        Command(['xacro ', robot_xacro_path]),
        value_type=str,
    )

    world = LaunchConfiguration('world')
    use_sim_time = LaunchConfiguration('use_sim_time')

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros_share, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'world': world,
        }.items(),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            {
                'robot_description': robot_description,
                'use_sim_time': use_sim_time,
            }
        ],
    )

    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_amr',
        output='screen',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'amr',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.03441',
        ],
    )

    return LaunchDescription([
        SetEnvironmentVariable(
            name='GAZEBO_MODEL_DATABASE_URI',
            value='',
        ),
        SetEnvironmentVariable(
            name='GAZEBO_MODEL_PATH',
            value=[
                package_share_parent,
                ':',
                EnvironmentVariable('GAZEBO_MODEL_PATH', default_value=''),
            ],
        ),
        DeclareLaunchArgument(
            'world',
            default_value=default_world_path,
            description='Gazebo world file to load.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use Gazebo simulation time.',
        ),
        gazebo,
        robot_state_publisher,
        spawn_robot,
    ])
