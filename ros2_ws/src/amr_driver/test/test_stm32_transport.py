"""Unit tests for STM32 telemetry regexes. No serial port required."""

from amr_driver.stm32_transport import _OLD_TELEMETRY_RE, _TELEMETRY_RE


def test_parses_real_firmware_telemetry_line():
    line = 'E,12345,1024,-1030'
    match = _TELEMETRY_RE.search(line)
    assert match is not None
    time_ms, left_ticks, right_ticks = (int(g) for g in match.groups())
    assert time_ms == 12345
    assert left_ticks == 1024
    assert right_ticks == -1030


def test_detects_old_verbose_telemetry_line():
    line = (
        'LTicks:1024        LPWM:512      LCTPS:180      '
        'RTicks:1030        RPWM:-200     RCTPS:-60     '
    )
    assert _OLD_TELEMETRY_RE.search(line) is not None


def test_ignores_non_telemetry_lines():
    assert _TELEMETRY_RE.search('OK,SAVE') is None
    assert _TELEMETRY_RE.search('PID,3.000,0.500,0.000') is None
