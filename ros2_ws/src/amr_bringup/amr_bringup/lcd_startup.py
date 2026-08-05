"""Backward-compatible one-shot renderer for the AMR LCD idle mark."""

import sys

from amr_bringup.lcd_display import LcdDisplay


def draw_startup_mark() -> None:
    """Clear the LCD and draw the four-line block startup mark."""
    display = LcdDisplay()
    try:
        display.show_idle_mark()
    finally:
        display.close()


def main() -> int:
    """Console entry point used by the real-robot bringup launch."""
    try:
        draw_startup_mark()
    except ImportError:
        print(
            'LCD startup skipped: install RPLCD with '
            '`sudo python3 -m pip install RPLCD`.',
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # Hardware absence must not stop robot bringup.
        print(f'LCD startup skipped: {exc}', file=sys.stderr)
        return 1

    print('LCD startup mark displayed on I2C bus 0 at address 0x27.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
