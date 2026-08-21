"""Tests for the desktop-launcher installer."""

from amr_operator_gui.desktop_launcher import install_launcher


def test_install_launcher_creates_entries(tmp_path, monkeypatch):
    prefix = tmp_path / "install" / "amr_operator_gui"
    executable = prefix / "lib" / "amr_operator_gui" / "operator_gui"
    package_setup = prefix / "share" / "amr_operator_gui" / "package.bash"
    executable.parent.mkdir(parents=True)
    package_setup.parent.mkdir(parents=True)
    executable.touch()
    package_setup.touch()

    icon = tmp_path / "amr_operator_gui.svg"
    icon.touch()
    monkeypatch.setattr(
        "amr_operator_gui.desktop_launcher.APPLICATION_ICON_PATH",
        icon,
    )

    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    installed = install_launcher(prefix, home)

    wrapper = home / ".local" / "bin" / "amr-operator-gui"
    menu_entry = (
        home
        / ".local"
        / "share"
        / "applications"
        / "amr-operator-gui.desktop"
    )
    desktop_entry = home / "Desktop" / "AMR Operator.desktop"
    assert installed == [wrapper, menu_entry, desktop_entry]
    assert "source /opt/ros/humble/setup.bash" in wrapper.read_text()
    assert str(executable) in wrapper.read_text()
    assert 'Name=AMR Operator' in menu_entry.read_text()
    assert str(wrapper) in desktop_entry.read_text()
