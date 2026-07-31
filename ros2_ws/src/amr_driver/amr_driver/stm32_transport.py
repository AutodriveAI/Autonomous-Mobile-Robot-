"""Serial transport for the STM32 differential-drive firmware.

Mirrors MyProject/Core/Src/robot_control.c exactly:
  - USART2, 115200 8N1, '\\n'-terminated ASCII lines.
  - Outgoing commands:
      V,<left_ticks_per_s>,<right_ticks_per_s>   speed-PID mode (int, +/-1000)
      C,<left_pwm>,<right_pwm>                   raw PWM mode   (int, +/-999)
      P,<kp>,<ki>,<kd>                           live-tune both PID gain sets
      PL,<kp>,<ki>,<kd>                          live-tune left PID gains
      PR,<kp>,<ki>,<kd>                          live-tune right PID gains
      SAVE                                       persist gains to flash
      G                                          request current gains
      R                                          reset encoder counters
  - Incoming telemetry (sent every 50 ms unless paused by the firmware):
      E,<time_ms>,<signed_left_ticks>,<signed_right_ticks>
  - Incoming replies: OK,<cmd> / ERR,<cmd> /
      PID,L,<kp>,<ki>,<kd>,R,<kp>,<ki>,<kd>

The STM32 still has single-channel encoders, but it now reports signed total
tick positions. It assigns the sign from the current wheel command direction.
When the wheel is hand-rotated with no command active, new ticks count positive.
"""

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import serial

_TELEMETRY_RE = re.compile(r'^E,(\d+),(-?\d+),(-?\d+)$')

# Temporary compatibility for older firmware prints.  The driver no longer
# relies on these fields for odometry, but accepting the line lets tests and
# logs fail softly if an old firmware image is still flashed.
_OLD_TELEMETRY_RE = re.compile(
    r'LTicks:(\d+)\s+LPWM:(-?\d+)\s+LCTPS:(-?\d+)\s+'
    r'RTicks:(\d+)\s+RPWM:(-?\d+)\s+RCTPS:(-?\d+)'
)


@dataclass
class Telemetry:
    """One complete measurement line received from the STM32.

    ``stamp`` is assigned by this computer, at the moment the serial line is
    decoded.  ``time_ms`` is the STM32 millisecond tick carried in the telemetry
    line.  Odometry prefers ``time_ms`` because it measures when the firmware
    sampled the encoder counts, not when USB delivered the text to Linux.
    """

    time_ms: int
    # Signed total encoder positions.  These are the source of truth for wheel
    # animation and odometry; ROS computes deltas between consecutive samples.
    left_ticks: int
    right_ticks: int
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
        self._warned_old_telemetry = False

        # pyserial opens the device now. timeout prevents read() from waiting
        # forever, allowing close() to stop the reader promptly.
        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._write_failed = False
        self._read_failed = False

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
        try:
            if self._serial.is_open:
                self._serial.close()
        except (OSError, serial.SerialException):
            # If the USB serial device was unplugged/reset, close() can also
            # fail because the file descriptor no longer maps to a live device.
            # During shutdown there is nothing useful to recover here.
            pass

    # -- outgoing commands, one per firmware command letter -----------------

    def send_velocity(self, left_ticks_per_s: int, right_ticks_per_s: int) -> None:
        """Select firmware PID mode and set signed wheel targets in ticks/s."""
        self._send_line(f'V,{int(left_ticks_per_s)},{int(right_ticks_per_s)}')

    def send_raw_pwm(self, left_pwm: int, right_pwm: int) -> None:
        """Bypass PID for a bench test; values are clamped by firmware."""
        self._send_line(f'C,{int(left_pwm)},{int(right_pwm)}')

    def set_pid_gains(self, kp: float, ki: float, kd: float) -> None:
        """Set both wheels to the same PID gains."""
        # Three decimals are enough for the firmware's simple text protocol
        # and avoid sending an unnecessarily long Python float representation.
        self._send_line(f'P,{kp:.3f},{ki:.3f},{kd:.3f}')

    def set_left_pid_gains(self, kp: float, ki: float, kd: float) -> None:
        """Set only the left wheel PID gains."""
        self._send_line(f'PL,{kp:.3f},{ki:.3f},{kd:.3f}')

    def set_right_pid_gains(self, kp: float, ki: float, kd: float) -> None:
        """Set only the right wheel PID gains."""
        self._send_line(f'PR,{kp:.3f},{ki:.3f},{kd:.3f}')

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
            if not self._serial.is_open:
                self._report_serial_write_failure('serial port is closed')
                return
            try:
                self._serial.write(payload)
            except (OSError, serial.SerialException) as exc:
                self._report_serial_write_failure(str(exc))

    def _report_serial_write_failure(self, reason: str) -> None:
        """Report a lost STM32 serial device once, without crashing the node."""
        if not self._write_failed:
            self._write_failed = True
            if self._on_reply is not None:
                self._on_reply(f'ERR,SERIAL_WRITE_FAILED,{reason}')
        self._stop_event.set()

    def _read_loop(self) -> None:
        """Collect arbitrary serial chunks and reconstruct complete text lines."""
        # Serial reads have no message boundaries: a read may contain half a
        # line, one line, or several lines. buffer retains incomplete bytes.
        buffer = b''
        while not self._stop_event.is_set():
            try:
                chunk = self._serial.read(256)
            except (OSError, serial.SerialException) as exc:
                # Port unplugged, STM32 reset, cable/power issue, or the OS
                # reclaimed the device. Report once and stop the reader thread
                # instead of busy-looping forever.
                if not self._read_failed:
                    self._read_failed = True
                    if self._on_reply is not None:
                        self._on_reply(f'ERR,SERIAL_READ_FAILED,{exc}')
                self._stop_event.set()
                break

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
                time_ms, left_ticks, right_ticks = (
                    int(g) for g in match.groups())
                self._on_telemetry(Telemetry(
                    time_ms=time_ms,
                    left_ticks=left_ticks,
                    right_ticks=right_ticks,
                    stamp=time.monotonic(),
                ))
            return

        old_match = _OLD_TELEMETRY_RE.search(line)
        if old_match:
            if self._on_reply is not None and not self._warned_old_telemetry:
                self._warned_old_telemetry = True
                self._on_reply(
                    'WARN,OLD_TELEMETRY_FORMAT_FLASH_NEW_STM32_FIRMWARE')
            return

        if line.startswith('E,') or line.startswith('LTicks:'):
            # A telemetry-looking line that reached this point is malformed for
            # the parser.  Drop it instead of forwarding it to the ROS logger;
            # otherwise one bad firmware/host format mismatch can flood the
            # terminal at the telemetry rate.
            return

        # Everything else is a command reply: OK,x / ERR,x / PID,kp,ki,kd.
        # Keeping replies as text preserves future firmware reply types too.
        if self._on_reply is not None:
            self._on_reply(line)
