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
    # \s+ accepts the deliberately wide fixed-width spacing printed by STM32.
    # Parentheses capture the six numeric fields in their on-wire order.
    r'LTicks:(\d+)\s+LPWM:(-?\d+)\s+LCTPS:(-?\d+)\s+'
    r'RTicks:(\d+)\s+RPWM:(-?\d+)\s+RCTPS:(-?\d+)'
)


@dataclass
class Telemetry:
    """One complete measurement line received from the STM32.

    ``stamp`` is assigned by this computer, at the moment the serial line is
    decoded.  The firmware does not currently send its own timestamp, so this
    local monotonic time is used to calculate the interval for odometry.
    """

    # Raw counters are useful for diagnostics and reset verification.  They
    # are unsigned and do not themselves indicate wheel direction.
    left_ticks: int
    left_pwm: int
    left_ticks_per_s: int
    right_ticks: int
    right_pwm: int
    right_ticks_per_s: int
    stamp: float


class Stm32Transport:
    """Owns the serial port and a background reader thread.

    All writes happen on the caller's thread (they are short, non-blocking
    HAL_UART_Transmit calls on the firmware side). All reads happen on a
    dedicated thread so a slow/blocked caller never delays parsing telemetry.
    """

    def __init__(self, port: str, baud: int,
                 on_telemetry: Optional[Callable[[Telemetry], None]] = None,
                 on_reply: Optional[Callable[[str], None]] = None,
                 timeout: float = 0.2):
        # Save callbacks before opening the port: the reader thread may
        # receive data immediately after it starts.
        self._on_telemetry = on_telemetry
        self._on_reply = on_reply

        # pyserial opens the device now. timeout prevents read() from waiting
        # forever, allowing close() to stop the reader promptly.
        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout)

        # A ROS timer and a shutdown handler could both write at once.  A lock
        # ensures bytes from two commands never become one malformed line.
        self._write_lock = threading.Lock()

        # Event is shared with the background reader as its clean stop signal.
        self._stop_event = threading.Event()

        # daemon=True means this thread cannot keep Python alive if a fatal
        # error occurs elsewhere. close() still joins it during normal exit.
        self._reader_thread = threading.Thread(
            target=self._read_loop, name='stm32_transport_reader', daemon=True)
        self._reader_thread.start()

    def close(self) -> None:
        """Stop serial reception, then release the operating-system device."""
        self._stop_event.set()
        self._reader_thread.join(timeout=1.0)
        if self._serial.is_open:
            self._serial.close()

    # -- outgoing commands, one per firmware command letter -----------------

    def send_velocity(self, left_ticks_per_s: int, right_ticks_per_s: int) -> None:
        """Select firmware PID mode and set signed wheel targets in ticks/s."""
        self._send_line(f'V,{int(left_ticks_per_s)},{int(right_ticks_per_s)}')

    def send_raw_pwm(self, left_pwm: int, right_pwm: int) -> None:
        """Bypass PID for a bench test; values are clamped by firmware."""
        self._send_line(f'C,{int(left_pwm)},{int(right_pwm)}')

    def set_pid_gains(self, kp: float, ki: float, kd: float) -> None:
        # Three decimals are enough for the firmware's simple text protocol
        # and avoid sending an unnecessarily long Python float representation.
        self._send_line(f'P,{kp:.3f},{ki:.3f},{kd:.3f}')

    def save_pid_gains(self) -> None:
        self._send_line('SAVE')

    def request_pid_gains(self) -> None:
        self._send_line('G')

    def reset_encoders(self) -> None:
        self._send_line('R')

    def stop(self) -> None:
        # Use a V command instead of raw C so the firmware also clears PID
        # history and returns to a predictable stopped controller state.
        self.send_velocity(0, 0)

    # -- internals ------------------------------------------------------

    def _send_line(self, line: str) -> None:
        """Encode exactly one newline-terminated ASCII command and transmit it."""
        # STM32 receives individual bytes and processes a command only after
        # '\n'.  ASCII keeps both ends simple and deterministic.
        payload = (line + '\n').encode('ascii')
        with self._write_lock:
            self._serial.write(payload)

    def _read_loop(self) -> None:
        """Collect arbitrary serial chunks and reconstruct complete text lines."""
        # Serial reads have no message boundaries: a read may contain half a
        # line, one line, or several lines. buffer retains incomplete bytes.
        buffer = b''
        while not self._stop_event.is_set():
            try:
                chunk = self._serial.read(256)
            except serial.SerialException:
                # Port unplugged or the OS reclaimed it. Back off rather than
                # busy-looping and let the ROS node continue reporting errors.
                time.sleep(0.5)
                continue

            if not chunk:
                # A normal read timeout; check stop_event again at loop top.
                continue

            buffer += chunk
            while b'\n' in buffer:
                # split(..., 1) removes only the first complete line and
                # leaves any following complete/partial line for the loop.
                raw_line, buffer = buffer.split(b'\n', 1)
                # errors='ignore' prevents one noisy byte from killing the
                # reader thread. strip() removes firmware '\r' before '\n'.
                self._handle_line(raw_line.decode('ascii', errors='ignore').strip())

    def _handle_line(self, line: str) -> None:
        """Classify one completed firmware line as telemetry or a reply."""
        if not line:
            return

        match = _TELEMETRY_RE.search(line)
        if match:
            if self._on_telemetry is not None:
                # Regex groups are strings. Convert all six once, then assign
                # them by name so downstream code cannot confuse field order.
                (l_ticks, l_pwm, l_ctps,
                 r_ticks, r_pwm, r_ctps) = (int(g) for g in match.groups())
                self._on_telemetry(Telemetry(
                    left_ticks=l_ticks, left_pwm=l_pwm,
                    left_ticks_per_s=l_ctps,
                    right_ticks=r_ticks, right_pwm=r_pwm,
                    right_ticks_per_s=r_ctps,
                    # monotonic() is unaffected by wall-clock/NTP changes.
                    stamp=time.monotonic(),
                ))
            return

        # Everything else is a command reply: OK,x / ERR,x / PID,kp,ki,kd.
        # Keeping replies as text preserves future firmware reply types too.
        if self._on_reply is not None:
            self._on_reply(line)
