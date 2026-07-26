"""Unit test for the telemetry regex against a real line format from
robot_control.c's RobotControl_SendTelemetry(). No serial port required."""

from amr_driver.stm32_transport import _TELEMETRY_RE


def test_parses_real_firmware_telemetry_line():
    line = (
        'LTicks:1024        LPWM:512      LCTPS:180      '
        'RTicks:1030        RPWM:-200     RCTPS:-60     '
    )
    match = _TELEMETRY_RE.search(line)
    assert match is not None
    l_ticks, l_pwm, l_ctps, r_ticks, r_pwm, r_ctps = (
        int(g) for g in match.groups())
    assert l_ticks == 1024
    assert l_pwm == 512
    assert l_ctps == 180
    assert r_ticks == 1030
    assert r_pwm == -200
    assert r_ctps == -60


def test_ignores_non_telemetry_lines():
    assert _TELEMETRY_RE.search('OK,SAVE') is None
    assert _TELEMETRY_RE.search('PID,3.000,0.500,0.000') is None
