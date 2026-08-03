import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    """Launch the Nav2 navigation nodes for the AMR.

    This launch file starts the path-planning and path-following part of Nav2:

      - planner_server        : makes a global path from the map
      - controller_server     : converts the path into local velocity commands
      - velocity_smoother     : smooths those commands before they hit the robot
      - behavior_server       : recovery behaviors such as spin/back-up/wait
      - bt_navigator          : the high-level behavior-tree coordinator
      - waypoint_follower     : optional waypoint-following action server

    It does not start localization. Localization is owned by amr_localisation
    because we want to use the same AMCL/map setup for both manual driving and
    autonomous navigation.
    """
    package_share = get_package_share_directory('amr_navigation')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    use_rviz = LaunchConfiguration('use_rviz')
    rviz_config = LaunchConfiguration('rviz_config')
    bt_xml_file = LaunchConfiguration('bt_xml_file')
    log_level = LaunchConfiguration('log_level')
    is_foxy = os.environ.get('ROS_DISTRO') == 'foxy'

    # Nav2's lifecycle manager brings these managed nodes from "unconfigured"
    # to "active" automatically when autostart is true.
    if is_foxy:
        lifecycle_nodes = [
            'controller_server',
            'planner_server',
            'recoveries_server',
            'bt_navigator',
            'waypoint_follower',
        ]
    else:
        lifecycle_nodes = [
            'controller_server',
            'smoother_server',
            'planner_server',
            'behavior_server',
            'bt_navigator',
            'waypoint_follower',
            'velocity_smoother',
        ]

    # Single-robot physical bringup: use the global /tf and /tf_static topics
    # directly. Relative TF remaps can make nested costmap nodes listen on
    # namespaced topics such as /global_costmap/tf, leaving them unable to see
    # map/odom/base_link even though standalone tf2_echo can.
    remappings = []

    # RewrittenYaml lets launch arguments override values inside the YAML file
    # without maintaining separate "simulation" and "real robot" YAML copies.
    configured_params = RewrittenYaml(
        source_file=params_file,
        root_key='',
        param_rewrites={
            'use_sim_time': use_sim_time,
            'autostart': autostart,
            'default_bt_xml_filename': bt_xml_file,
        },
        convert_types=True,
    )

    controller_server = Node(
        package='nav2_controller',
        executable='controller_server',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings + [
            # Humble smooths raw controller output. Foxy has no velocity_smoother,
            # so send Nav2's candidate command directly to twist_mux.
            ('cmd_vel', 'cmd_vel_nav' if is_foxy else 'cmd_vel_nav_raw'),
        ],
    )

    smoother_server = Node(
        package='nav2_smoother',
        executable='smoother_server',
        name='smoother_server',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings,
    )

    planner_server = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings,
    )

    behavior_server = Node(
        package='nav2_recoveries' if is_foxy else 'nav2_behaviors',
        executable='recoveries_server' if is_foxy else 'behavior_server',
        name='recoveries_server' if is_foxy else 'behavior_server',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings + (
            [('cmd_vel', 'cmd_vel_nav')] if is_foxy else []
        ),
    )

    bt_navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings,
    )

    waypoint_follower = Node(
        package='nav2_waypoint_follower',
        executable='waypoint_follower',
        name='waypoint_follower',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings,
    )

    velocity_smoother = Node(
        package='nav2_velocity_smoother',
        executable='velocity_smoother',
        name='velocity_smoother',
        output='screen',
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings + [
            # Input: raw Nav2 controller command.
            ('cmd_vel', 'cmd_vel_nav_raw'),
            # Output: Nav2 candidate command for twist_mux.
            # twist_mux then decides whether Nav2, joystick, or keyboard wins.
            ('cmd_vel_smoothed', 'cmd_vel_nav'),
        ],
    )

    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': autostart},
            {'node_names': lifecycle_nodes},
        ],
        arguments=['--ros-args', '--log-level', log_level],
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_nav2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'),
        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(package_share, 'config', 'nav2_params.yaml'),
            description='Full path to AMR Nav2 parameter YAML.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use Gazebo simulation clock.',
        ),
        DeclareLaunchArgument(
            'autostart',
            default_value='true',
            description='Automatically activate Nav2 lifecycle nodes.',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Open RViz with the standard Nav2 panel/view.',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=os.path.join(
                nav2_bringup_share,
                'rviz',
                'nav2_default_view.rviz',
            ),
            description='RViz config used for Nav2 goal setting and monitoring.',
        ),
        DeclareLaunchArgument(
            'bt_xml_file',
            default_value=os.path.join(
                package_share,
                'behavior_trees',
                'navigate_w_slow_replanning_and_recovery.xml',
            ),
            description=(
                'Behavior tree XML. The default keeps recovery behavior but '
                'slows replanning to once every 20 seconds for Jetson bringup.'
            ),
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Nav2 node log level.',
        ),
        controller_server,
        *([] if is_foxy else [smoother_server]),
        planner_server,
        behavior_server,
        bt_navigator,
        waypoint_follower,
        *([] if is_foxy else [velocity_smoother]),
        lifecycle_manager,
        rviz,
    ])
