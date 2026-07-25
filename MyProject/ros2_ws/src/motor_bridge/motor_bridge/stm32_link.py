"""Serial transport for the STM32 differential-drive firmware.

Mirrors MyProject/Core/Src/robot_control.c exactly:
  - USART2, 115200 8N1, '\\n'-terminated ASCII lines.
  - Outgoing commands:
      V,<left_ticks_per_s>,<right_ticks_per_s>   speed-PID mode (int, +/-1000)
      C,<left_pwm>,<right_pwm>                   raw PWM mode   (int, +/-999)
      P,<kp>,<ki>,<kd>                           live-tune PID gains
      SAVE                                       persist gains to flash
      G                                          request current gains
      R                                          reset encoder counters
  - Incoming telemetry (sent every 50 ms unless paused by the firmware):
      LTicks:<u32>   LPWM:<int>   LCTPS:<int>    RTicks:<u32>   RPWM:<int>   RCTPS:<int>
  - Incoming replies: OK,<cmd> / ERR,<cmd> / PID,<kp>,<ki>,<kd>

Encoder counts are raw, monotonically-increasing pulse totals with no
direction sense built into the firmware (see encoder.c) -- direction must be
inferred on this side from the sign of the reported PWM.
"""

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import serial

_TELEMETRY_RE = re.compile(
    r'LTicks:(\d+)\s+LPWM:(-?\d+)\s+LCTPS:(-?\d+)\s+'
    r'RTicks:(\d+)\s+RPWM:(-?\d+)\s+RCTPS:(-?\d+)'
)


@dataclass
class Telemetry:
    left_ticks: int
    left_pwm: int
    left_ticks_per_s: int
    right_ticks: int
    right_pwm: int
    right_ticks_per_s: int
    stamp: float


class Stm32Link:
    """Owns the serial port and a background reader thread.

    All writes happen on the caller's thread (they are short, non-blocking
    HAL_UART_Transmit calls on the firmware side). All reads happen on a
    dedicated thread so a slow/blocked caller never delays parsing telemetry.
    """

    def __init__(self, port: str, baud: int,
                 on_telemetry: Optional[Callable[[Telemetry], None]] = None,
                 on_reply: Optional[Callable[[str], None]] = None,
                 timeout: float = 0.2):
        self._on_telemetry = on_telemetry
        self._on_reply = on_reply
        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._write_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._reader_thread = threading.Thread(
            target=self._read_loop, name='stm32_link_reader', daemon=True)
        self._reader_thread.start()

    def close(self) -> None:
        self._stop_event.set()
        self._reader_thread.join(timeout=1.0)
        if self._serial.is_open:
            self._serial.close()

    # -- outgoing commands, one per firmware command letter -----------------

    def send_velocity(self, left_ticks_per_s: int, right_ticks_per_s: int) -> None:
        self._send_line(f'V,{int(left_ticks_per_s)},{int(right_ticks_per_s)}')

    def send_raw_pwm(self, left_pwm: int, right_pwm: int) -> None:
        self._send_line(f'C,{int(left_pwm)},{int(right_pwm)}')

    def set_pid_gains(self, kp: float, ki: float, kd: float) -> None:
        self._send_line(f'P,{kp:.3f},{ki:.3f},{kd:.3f}')

    def save_pid_gains(self) -> None:
        self._send_line('SAVE')

    def request_pid_gains(self) -> None:
        self._send_line('G')

    def reset_encoders(self) -> None:
        self._send_line('R')

    def stop(self) -> None:
        self.send_velocity(0, 0)

    # -- internals ------------------------------------------------------

    def _send_line(self, line: str) -> None:
        payload = (line + '\n').encode('ascii')
        with self._write_lock:
            self._serial.write(payload)

    def _read_loop(self) -> None:
        buffer = b''
        while not self._stop_event.is_set():
            try:
                chunk = self._serial.read(256)
            except serial.SerialException:
                # Port unplugged or the OS reclaimed it; back off and retry
                # the read rather than crashing the whole node.
                time.sleep(0.5)
                continue

            if not chunk:
                continue

            buffer += chunk
            while b'\n' in buffer:
                raw_line, buffer = buffer.split(b'\n', 1)
                self._handle_line(raw_line.decode('ascii', errors='ignore').strip())

    def _handle_line(self, line: str) -> None:
        if not line:
            return

        match = _TELEMETRY_RE.search(line)
        if match:
            if self._on_telemetry is not None:
                (l_ticks, l_pwm, l_ctps,
                 r_ticks, r_pwm, r_ctps) = (int(g) for g in match.groups())
                self._on_telemetry(Telemetry(
                    left_ticks=l_ticks, left_pwm=l_pwm,
                    left_ticks_per_s=l_ctps,
                    right_ticks=r_ticks, right_pwm=r_pwm,
                    right_ticks_per_s=r_ctps,
                    stamp=time.monotonic(),
                ))
            return

        # Everything else is a command reply: OK,x / ERR,x / PID,kp,ki,kd
        if self._on_reply is not None:
            self._on_reply(line)
