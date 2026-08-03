from setuptools import setup

package_name = 'amr_navigation'

setup(
    name=package_name,
    version='0.1.0',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, [
            'package.xml',
            'README.md',
        ]),
        ('share/' + package_name + '/launch', [
            'launch/twist_mux.launch.py',
            'launch/nav2.launch.py',
        ]),
        ('share/' + package_name + '/config', [
            'config/twist_mux.yaml',
            'config/nav2_params.yaml',
            'config/nav2_params_real.yaml',
        ]),
        ('share/' + package_name + '/behavior_trees', [
            'behavior_trees/navigate_w_slow_replanning_and_recovery.xml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='Navigation command arbitration and future Nav2 configuration for the AMR.',
    license='MIT',
)
