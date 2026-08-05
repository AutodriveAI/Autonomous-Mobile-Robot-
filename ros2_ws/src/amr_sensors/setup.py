from setuptools import setup

package_name = 'amr_sensors'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name, ['README.md']),
        ('share/' + package_name + '/launch', [
            'launch/realsense_d435i.launch.py',
            'launch/rplidar_a1.launch.py',
            'launch/rplidar_c1.launch.py',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='Sensor launch files for the AMR real robot.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'remote_rgb_viewer = amr_sensors.remote_rgb_viewer:main',
        ],
    },
)
