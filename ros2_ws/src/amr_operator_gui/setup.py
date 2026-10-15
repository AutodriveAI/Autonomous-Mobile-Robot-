from setuptools import find_packages, setup


package_name = "amr_operator_gui"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    package_data={package_name: ["icons/*.svg"]},
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml", "README.md"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Nilkontha Das",
    maintainer_email="you@example.com",
    description="Desktop GUI for starting, monitoring, and debugging the AMR.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "install_desktop_launcher = "
            "amr_operator_gui.desktop_launcher:main",
            "nav2_health_probe = amr_operator_gui.nav2_health_probe:main",
            "operator_gui = amr_operator_gui.main:main",
            "system_health_probe = amr_operator_gui.system_health_probe:main",
        ],
    },
)
