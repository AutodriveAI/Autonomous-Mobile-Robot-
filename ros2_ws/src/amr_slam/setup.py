from setuptools import setup

package_name = 'amr_slam'

setup(
    name=package_name,
    version='0.1.0',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/mapping.launch.py',
        ]),
        ('share/' + package_name + '/config', [
            'config/mapper_params_online_sync.yaml',
        ]),
        ('share/' + package_name + '/rviz', [
            'rviz/mapping.rviz',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='Occasional mapping launch/configuration package for the AMR.',
    license='MIT',
)
