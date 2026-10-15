"""Tests for read-only network diagnostic helpers."""

import pytest

from amr_operator_gui.network_diagnostics import (
    diagnostic_probe_command,
    diagnostic_summary,
    local_diagnostic_probe_command,
    parse_probe_output,
)
from amr_operator_gui.ssh_connection import SshSettings


def test_probe_command_contains_expected_checks():
    command = diagnostic_probe_command("10.206.146.161")

    assert "ip -4 route get" in command
    assert "PEER_WIFI=PASS" in command
    assert "INTERNET_IP=PASS" in command
    assert "DNS=PASS" in command


def test_probe_rejects_shell_metacharacters():
    with pytest.raises(ValueError):
        diagnostic_probe_command("host; reboot")


def test_local_probe_resolves_ssh_alias():
    command = local_diagnostic_probe_command(
        SshSettings(host="nano_wifi", username="jetson")
    )

    assert "ssh -G -p 22 jetson@nano_wifi" in command
    assert "peer=nano_wifi" in command


def test_parse_probe_output_ignores_non_marker_lines():
    parsed = parse_probe_output("noise\nHOST=nano\nPEER_WIFI=PASS\n")

    assert parsed == {"HOST": "nano", "PEER_WIFI": "PASS"}


def test_summary_isolates_remote_internet_failure():
    local = "PEER_WIFI=PASS\nINTERNET_IP=PASS\nDNS=PASS\n"
    remote = "PEER_WIFI=PASS\nINTERNET_IP=FAIL\nDNS=FAIL\n"

    summary = diagnostic_summary(local, remote, "Ethernet fallback")

    assert any("isolated to the Jetson" in line for line in summary)
    assert any("DNS resolution" in line for line in summary)
