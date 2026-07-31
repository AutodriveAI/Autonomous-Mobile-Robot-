# STM32 Differential-Drive Robot Firmware

Firmware for an STM32 NUCLEO-F401RE differential-drive robot. Build and flash
it with STM32CubeIDE. Serial communication uses USART2 through the ST-LINK
virtual COM port at **115200 baud**.

## Serial commands

Set the serial monitor line ending to **Newline** or **Both NL & CR**. Commands
are processed only after the terminating newline.

| Command | Meaning | Response |
| --- | --- | --- |
| `C,<left_pwm>,<right_pwm>` | Drive wheels in raw PWM mode; bypasses speed PID. | No acknowledgement; encoder telemetry continues. |
| `V,<left_ticks_s>,<right_ticks_s>` | Set wheel-speed targets and enable speed PID mode. | No acknowledgement; encoder telemetry continues. |
| `P,<kp>,<ki>,<kd>` | Change both left and right PID gains immediately in RAM. Does **not** save them across reset. | `OK,P` or `ERR,P` |
| `PL,<kp>,<ki>,<kd>` | Change only the left wheel PID gains in RAM. | `OK,PL` or `ERR,P` |
| `PR,<kp>,<ki>,<kd>` | Change only the right wheel PID gains in RAM. | `OK,PR` or `ERR,P` |
| `G` | Print the active left and right PID gains. Telemetry pauses for 3 seconds. | `PID,L,<kp>,<ki>,<kd>,R,<kp>,<ki>,<kd>` |
| `R` | Reset both encoder totals to zero. PID gains and requested speeds are unchanged; telemetry pauses for 1 second. | `OK,R` |
| `SAVE` | Stop the motors and save the active PID gains permanently. | `OK,SAVE` or `ERR,SAVE` |

Examples:

```text
C,300,300
V,25,25
P,3.0,0.5,0.0
PL,3.5,0.5,0.0
PR,2.8,0.4,0.0
G
R
SAVE
```

## Limits and conventions

- Raw PWM values are clamped to **-999 through +999**.
- PID speed targets are clamped to **-60 through +60 ticks/second**.
- PID gains `Kp`, `Ki`, and `Kd` must each be in the range **0 through 100**.
- The left and right wheels now have separate PID gain sets. Use `P` when you
  want both wheels to use the same gains, `PL` for left-only tuning, and `PR`
  for right-only tuning.
- After a successful `P`, `PL`, or `PR` command, encoder telemetry pauses for
  **1 second** so the acknowledgement reply can be read without intervening
  encoder lines.
- Positive and negative wheel commands follow the motor direction convention
  configured in `motor.c` (positive means robot-forward in the current setup).
- In `V` PID mode, a positive target can command only positive PWM (or zero),
  and a negative target only negative PWM (or zero). An overspeeding wheel
  coasts rather than being actively driven in the opposite direction.
- Each wheel encoder uses one debounced rising-edge channel from the HC-020K
  module and has **20 ticks per wheel revolution** with the present 20-slit
  disk.
- Encoder telemetry is sent every **50 ms**, as one compact line:

  ```text
  E,<time_ms>,<signed_left_ticks>,<signed_right_ticks>
  ```

  Example:

  ```text
  E,12345,1436,1224
  ```

  These are signed total encoder positions. ROS calculates tick deltas, wheel
  speed, wheel angle, and odometry from these totals.

## PID persistence

The STM32F401 has no EEPROM. `SAVE` stores the current gains in the final
128 KiB internal Flash sector (sector 7). The linker script reserves that
sector, so normal firmware programming cannot overwrite the saved gains.

Saved gains are read automatically at boot. Do not use `SAVE` repeatedly while
tuning: Flash sectors have finite erase endurance. Adjust values with `P`,
`PL`, or `PR`, test them, then use `SAVE` only after choosing values to keep.
