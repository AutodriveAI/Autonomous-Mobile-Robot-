"""Single-owner interface for the AMR's 20x4 I2C character LCD."""

from threading import Lock
from time import sleep


I2C_ADDRESS = 0x27
I2C_PORT = 0
DISPLAY_COLUMNS = 20
DISPLAY_ROWS = 4


class LcdDisplay:
    """Render complete screens without exposing the underlying I2C device."""

    def __init__(self):
        # Keep this optional hardware dependency out of package import paths.
        from RPLCD.i2c import CharLCD

        self._lock = Lock()
        self._lcd = CharLCD(
            i2c_expander='PCF8574',
            address=I2C_ADDRESS,
            port=I2C_PORT,
            cols=DISPLAY_COLUMNS,
            rows=DISPLAY_ROWS,
            charmap='A00',
            auto_linebreaks=False,
        )

    def show_lines(self, lines):
        """Clear the display and render up to four padded 20-column lines."""
        with self._lock:
            self._clear_unlocked()
            for row, line in enumerate(lines[:DISPLAY_ROWS]):
                text = str(line)[:DISPLAY_COLUMNS]
                self._lcd.cursor_pos = (row, 0)
                self._lcd.write_string(text.ljust(DISPLAY_COLUMNS))

    def show_idle_mark(self):
        """Draw the original block smile/startup mark."""
        with self._lock:
            self._clear_unlocked()

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
            self._lcd.create_char(0, full_cell)
            block = chr(0)

            cells = [
                (0, 3),
                (1, 4),
                (2, 5),
                *((3, column) for column in range(6, 15)),
                (2, 15),
                (1, 16),
                (0, 17),
            ]

            for row, column in cells:
                self._lcd.cursor_pos = (row, column)
                self._lcd.write_string(block)

    def close(self):
        """Release the I2C handle while leaving the final screen visible."""
        with self._lock:
            self._lcd.close(clear=False)

    def _clear_unlocked(self):
        self._lcd.clear()
        sleep(0.02)
        for row in range(DISPLAY_ROWS):
            self._lcd.cursor_pos = (row, 0)
            self._lcd.write_string(' ' * DISPLAY_COLUMNS)
