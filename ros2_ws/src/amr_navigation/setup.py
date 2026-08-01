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
        ]),
        ('share/' + package_name + '/config', [
            'config/twist_mux.yaml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Nilkontha Das',
    maintainer_email='you@example.com',
    description='Navigation command arbitration and future Nav2 configuration for the AMR.',
    license='MIT',
)
