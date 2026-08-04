from setuptools import setup

package_name = 'amr_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/sim_bringup.launch.py',
            'launch/robot_bringup.launch.py',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='Top-level bringup launch files for the AMR simulation and real robot.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'lcd_startup = amr_bringup.lcd_startup:main',
        ],
    },
)
