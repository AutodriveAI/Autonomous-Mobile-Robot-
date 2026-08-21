"""Install a desktop launcher for the AMR Operator GUI."""

from pathlib import Path
import shlex
import sys


LAUNCHER_NAME = "amr-operator-gui"
APPLICATION_ICON_PATH = (
    Path(__file__).resolve().parent / "icons" / "amr_operator_gui.svg"
)


def package_prefix_from_executable(executable: Path) -> Path:
    """Return the ROS package prefix from a generated console script path."""
    executable = executable.absolute()
    if executable.parent.name != "amr_operator_gui":
        raise ValueError(
            "Run this installer through 'ros2 run amr_operator_gui "
            "install_desktop_launcher'."
        )
    return executable.parent.parent.parent


def install_launcher(package_prefix: Path, home: Path) -> list:
    """Create the user wrapper, menu entry, and desktop shortcut."""
    package_prefix = package_prefix.absolute()
    home = home.absolute()
    operator_executable = (
        package_prefix / "lib" / "amr_operator_gui" / "operator_gui"
    )
    package_setup = (
        package_prefix
        / "share"
        / "amr_operator_gui"
        / "package.bash"
    )
    icon = APPLICATION_ICON_PATH
    missing = [
        path
        for path in (operator_executable, package_setup, icon)
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Build amr_operator_gui first; missing: {}".format(
                ", ".join(str(path) for path in missing)
            )
        )

    bin_directory = home / ".local" / "bin"
    applications_directory = home / ".local" / "share" / "applications"
    bin_directory.mkdir(parents=True, exist_ok=True)
    applications_directory.mkdir(parents=True, exist_ok=True)

    wrapper = bin_directory / LAUNCHER_NAME
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -e\n"
        "source /opt/ros/humble/setup.bash\n"
        "source {}\n"
        "exec {} \"$@\"\n".format(
            shlex.quote(str(package_setup)),
            shlex.quote(str(operator_executable)),
        ),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    desktop_contents = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        "Name=AMR Operator",
        "Comment=Start and monitor the autonomous mobile robot",
        "Exec=\"{}\"".format(wrapper),
        "Icon={}".format(icon),
        "Terminal=false",
        "Categories=Development;",
        "StartupNotify=true",
        "StartupWMClass=amr-operator-gui",
        "",
    ])
    application_entry = applications_directory / "{}.desktop".format(
        LAUNCHER_NAME
    )
    application_entry.write_text(desktop_contents, encoding="utf-8")
    application_entry.chmod(0o755)

    installed = [wrapper, application_entry]
    desktop_directory = home / "Desktop"
    if desktop_directory.is_dir():
        desktop_entry = desktop_directory / "AMR Operator.desktop"
        desktop_entry.write_text(desktop_contents, encoding="utf-8")
        desktop_entry.chmod(0o755)
        installed.append(desktop_entry)
    return installed


def main() -> int:
    """Install the launcher for the current desktop user."""
    try:
        prefix = package_prefix_from_executable(Path(sys.argv[0]))
        installed = install_launcher(prefix, Path.home())
    except (FileNotFoundError, OSError, ValueError) as error:
        print("Could not install AMR Operator launcher: {}".format(error))
        return 1

    print("AMR Operator launcher installed:")
    for path in installed:
        print("  {}".format(path))
    if len(installed) == 2:
        print(
            "No ~/Desktop directory was found; launch it from the application "
            "menu or pin it to the dock."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
