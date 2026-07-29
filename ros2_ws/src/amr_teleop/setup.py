from setuptools import find_packages, setup

package_name = 'amr_teleop'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='Keyboard teleoperation for the autonomous mobile robot.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # Keep the project-specific command name and use the standard ROS 2
            # teleop implementation, but inject AMR-specific default speed/turn
            # parameters before handing control to teleop_twist_keyboard.
            'keyboard_teleop = amr_teleop.keyboard_teleop:main',
            'cmd_vel_timeout = amr_teleop.cmd_vel_timeout:main',
        ],
    },
)
