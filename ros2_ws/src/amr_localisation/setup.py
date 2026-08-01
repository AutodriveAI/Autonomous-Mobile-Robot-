from setuptools import setup

package_name = 'amr_localisation'

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
            'launch/localisation.launch.py',
        ]),
        ('share/' + package_name + '/config', [
            'config/amcl.yaml',
        ]),
        ('share/' + package_name + '/rviz', [
            'rviz/localisation.rviz',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='AMCL saved-map localization launch/configuration package for the AMR.',
    license='MIT',
)
