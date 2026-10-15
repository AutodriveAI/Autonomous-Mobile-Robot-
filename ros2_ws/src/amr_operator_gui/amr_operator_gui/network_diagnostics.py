"""Read-only LAN and internet diagnostic command helpers."""

import re
import shlex
from typing import Dict, List

from amr_operator_gui.ssh_connection import SshSettings


_SAFE_PEER = re.compile(r"^[A-Za-z0-9_.:\-\[\]]*$")


def diagnostic_probe_command(peer_wifi_host: str = "") -> str:
    """Return a read-only shell probe with stable machine-readable markers."""
    peer = peer_wifi_host.strip()
    if not _SAFE_PEER.fullmatch(peer):
        raise ValueError("Diagnostic peer contains unsupported characters.")
    return _diagnostic_probe_lines([
        "peer={}".format(shlex.quote(peer)),
    ])


def local_diagnostic_probe_command(settings: SshSettings) -> str:
    """Build a local probe that resolves an SSH alias to its real hostname."""
    settings.validate()
    target = shlex.quote(settings.target)
    fallback_host = shlex.quote(settings.host)
    assignment = (
        "peer=$(ssh -G -p {port} {target} 2>/dev/null | "
        "awk '$1==\"hostname\" {{print $2; exit}}')"
    ).format(port=settings.port, target=target)
    return _diagnostic_probe_lines([
        assignment,
        '[ -n "$peer" ] || peer={}'.format(fallback_host),
    ])


def _diagnostic_probe_lines(prefix: List[str]) -> str:
    """Assemble a probe after initializing its peer shell variable."""
    return "\n".join(prefix + [
        'echo "HOST=$(hostname)"',
        'echo "ADDRESSES=$(hostname -I 2>/dev/null | xargs)"',
        'internet_route=$(ip -4 route get 1.1.1.1 2>/dev/null | head -n 1)',
        'echo "INTERNET_ROUTE=${internet_route:-unavailable}"',
        'gateway=$(printf "%s\\n" "$internet_route" | '
        "awk '{for(i=1;i<=NF;i++) if ($i==\"via\") {print $(i+1); exit}}')",
        'source_ip=$(printf "%s\\n" "$internet_route" | '
        "awk '{for(i=1;i<=NF;i++) if ($i==\"src\") {print $(i+1); exit}}')",
        'if [ -n "$peer" ]; then',
        '  peer_route=$(ip -4 route get "$peer" 2>/dev/null | head -n 1)',
        '  echo "PEER_ROUTE=${peer_route:-unavailable}"',
        '  peer_source=$(printf "%s\\n" "$peer_route" | '
        "awk '{for(i=1;i<=NF;i++) if ($i==\"src\") {print $(i+1); exit}}')",
        '  [ -n "$peer_source" ] && source_ip="$peer_source"',
        '  if ping -n -c 1 -W 2 "$peer" >/dev/null 2>&1; then',
        '    echo "PEER_WIFI=PASS"',
        '  else echo "PEER_WIFI=FAIL"; fi',
        'else',
        '  echo "PEER_ROUTE=not-tested"',
        '  echo "PEER_WIFI=SKIP"',
        'fi',
        'echo "SOURCE_IP=${source_ip:-unknown}"',
        'if [ -n "$gateway" ]; then',
        '  if ping -n -c 1 -W 2 "$gateway" >/dev/null 2>&1; then',
        '    echo "GATEWAY=PASS"',
        '  else echo "GATEWAY=FAIL"; fi',
        'else echo "GATEWAY=SKIP"; fi',
        'if ping -n -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then',
        '  echo "INTERNET_IP=PASS"',
        'else echo "INTERNET_IP=FAIL"; fi',
        'if getent ahostsv4 example.com >/dev/null 2>&1; then',
        '  echo "DNS=PASS"',
        'else echo "DNS=FAIL"; fi',
    ])


def parse_probe_output(output: str) -> Dict[str, str]:
    """Parse uppercase marker lines from one diagnostic probe."""
    values = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.isupper():
            values[key] = value.strip()
    return values


def diagnostic_summary(
    local_output: str, remote_output: str, active_route: str
) -> List[str]:
    """Summarize which side or shared network segment appears unhealthy."""
    local = parse_probe_output(local_output)
    remote = parse_probe_output(remote_output)
    messages = ["Active SSH route: {}.".format(active_route)]

    local_peer = local.get("PEER_WIFI")
    remote_peer = remote.get("PEER_WIFI")
    if local_peer == "PASS" and remote_peer == "PASS":
        messages.append("Wi-Fi LAN reachability works in both directions.")
    elif local_peer == "FAIL" and remote_peer == "FAIL":
        messages.append(
            "Wi-Fi peer reachability fails in both directions; inspect the "
            "Jetson Wi-Fi association, access point, and Wi-Fi subnet."
        )
    elif local_peer == "FAIL" and remote_peer == "PASS":
        messages.append(
            "Only development-machine → Jetson Wi-Fi fails; inspect the "
            "development-machine route/firewall and Jetson inbound Wi-Fi."
        )
    elif local_peer == "PASS" and remote_peer == "FAIL":
        messages.append(
            "Only Jetson → development-machine Wi-Fi fails; inspect the "
            "Jetson route and development-machine inbound firewall."
        )

    local_internet = local.get("INTERNET_IP") == "PASS"
    remote_internet = remote.get("INTERNET_IP") == "PASS"
    if local_internet and remote_internet:
        messages.append("Both machines can reach an internet IP address.")
    elif local_internet and not remote_internet:
        messages.append("Internet failure is isolated to the Jetson side.")
    elif remote_internet and not local_internet:
        messages.append(
            "Internet failure is isolated to the development-machine side."
        )
    else:
        messages.append(
            "Neither machine reached the internet probe; inspect the shared "
            "router/uplink (ICMP filtering can also cause this result)."
        )

    local_dns = local.get("DNS") == "PASS"
    remote_dns = remote.get("DNS") == "PASS"
    if local_dns != remote_dns:
        side = "Jetson" if local_dns else "development machine"
        messages.append("DNS resolution appears broken on the {}.".format(side))
    elif not local_dns and not remote_dns:
        messages.append("DNS resolution failed on both machines.")
    return messages
