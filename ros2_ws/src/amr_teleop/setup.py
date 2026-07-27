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
            # Keep the project-specific command name, but run the standard ROS 2
            # teleop_twist_keyboard implementation instead of custom key handling.
            'keyboard_teleop = teleop_twist_keyboard:main',
        ],
    },
)
