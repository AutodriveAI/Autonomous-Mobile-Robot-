"""Install the Onshape URDF, meshes, and ROS 2 launch file as ament resources."""

import os
from glob import glob

from setuptools import setup


package_name = 'robot_description'


setup(
    name=package_name,
    version='0.1.0',
    # This is a data-only package: it installs no importable Python modules.
    packages=[],
    data_files=[
        # Required marker so `ros2 pkg` and get_package_share_directory() can
        # discover this package after colcon installs it.
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Install the launch file, URDF, and every flat STL mesh at the paths
        # referenced by package://robot_description/... URDF URI values.
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*')),
        (os.path.join('share', package_name, 'meshes'), glob('meshes/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='ROS 2 URDF and mesh description of the full robot assembly.',
    license='MIT',
)
