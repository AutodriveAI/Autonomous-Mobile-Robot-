"""Draw the AMR startup mark on the Jetson's I2C character LCD."""

import sys
from time import sleep


I2C_ADDRESS = 0x27
I2C_PORT = 0
DISPLAY_COLUMNS = 20
DISPLAY_ROWS = 4


def draw_startup_mark() -> None:
    """Clear the LCD and draw the four-line block startup mark."""
    # Import here so a missing optional hardware dependency produces a clear
    # message without preventing the rest of amr_bringup from being imported.
    from RPLCD.i2c import CharLCD

    lcd = CharLCD(
        i2c_expander='PCF8574',
        address=I2C_ADDRESS,
        port=I2C_PORT,
        cols=DISPLAY_COLUMNS,
        rows=DISPLAY_ROWS,
        charmap='A00',
        auto_linebreaks=False,
    )

    lcd.clear()
    sleep(0.2)

    for row in range(DISPLAY_ROWS):
        lcd.cursor_pos = (row, 0)
        lcd.write_string(' ' * DISPLAY_COLUMNS)

    sleep(0.1)

    full_cell = (
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
        0b11111,
    )
    lcd.create_char(0, full_cell)
    block = chr(0)

    cells = [
        (0, 0),
        (1, 1),
        (2, 2),
        *((3, column) for column in range(4, 13)),
        (2, 13),
        (1, 14),
        (0, 15),
    ]

    for row, column in cells:
        lcd.cursor_pos = (row, column)
        lcd.write_string(block)


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
